"""Content pinning, deterministic lockfiles, repository locators, and drift reporting."""

import pathlib

import pytest
import yaml
from comeni_core.artifact.lockfile import Lockfile
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from support.paths import ROOT

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Add an idempotent declaration header inferred from a fixture's parent directory."""
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body



@pytest.fixture
def built():
    loaded = layers.load(ROOT / "registry")
    goal = Goal(
        # The reference is a required declared input for the alignment path.
        have=[
            GoalInput(type_id="fastq.reads"),
            GoalInput(type_id="annotation.gtf"),
            GoalInput(type_id="genome.fasta"),
        ],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    ), loaded


def test_a_lockfile_pins_every_contract_the_pipeline_uses(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert {c.id for c in lock.contracts} == {n.contract_id for n in ir.nodes}


def test_a_lockfile_pins_nothing_the_pipeline_does_not_use(built):
    """The registry has twelve contracts and the spine uses five. Pin what was used."""
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert len(lock.contracts) == len(ir.nodes) < len(loaded.registry.all())


def test_contracts_are_pinned_in_a_stable_order(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert [c.id for c in lock.contracts] == sorted(c.id for c in lock.contracts)


def test_a_lockfile_records_the_container(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    star = next(c for c in lock.contracts if c.id.startswith("nf-core/star/align"))
    assert star.container.startswith("community.wave.seqera.io/")


def test_a_lockfile_holds_no_filesystem_path(built):
    """Absolute build-machine paths are reduced to portable layer identities."""
    ir, loaded = built
    text = Lockfile.of(ir, loaded.registry, loaded.paths).model_dump_json()
    assert "/home" not in text and str(ROOT) not in text
    assert "registry" in text


def test_a_lockfile_has_no_timestamp(built):
    """Determinism is a test. A generated_at field would break it the day it is added."""
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert not any("time" in f or "date" in f or f == "at" for f in type(lock).model_fields)


def test_the_same_build_locks_identically(built):
    ir, loaded = built
    first = Lockfile.of(ir, loaded.registry, loaded.paths)
    second = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert first.model_dump_json() == second.model_dump_json()


def test_drift_is_empty_against_the_registry_that_built_it(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert lock.drift_against(ir, loaded.registry, loaded.paths) == []


def test_an_edited_contract_is_reported_as_drift(built, tmp_path):
    """The property a lockfile exists for: a contract changed underneath you, silently."""
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    sort = layer / "tools/nf-core/samtools/sort/contract.yml"
    sort.write_text(_declared(sort, sort.read_text().replace("priority: 0", "priority: 7")))
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("samtools/sort" in line for line in drift)


def test_a_missing_contract_is_reported_as_drift(built, tmp_path):
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    (layer / "tools/nf-core/samtools/sort/contract.yml").unlink()
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("no longer in the registry" in line for line in drift)


def test_a_newly_used_contract_is_reported_as_drift(built):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    omitted = lock.contracts[0]
    incomplete = lock.model_copy(update={"contracts": lock.contracts[1:]})

    assert f"{omitted.id} is used now but was not locked" in incomplete.drift_against(
        ir, loaded.registry, loaded.paths
    )


def _empty_layer(path):
    for name in ("contracts", "rules", "vocabularies", "measurements"):
        (path / name).mkdir(parents=True)
    return path


def test_reordering_the_layer_stack_is_drift(built, tmp_path):
    """Layer precedence is semantic, so reordering identical layers is drift."""
    import shutil

    ir, _ = built
    base = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", base)
    overlay = _empty_layer(tmp_path / "lab")

    forward = layers.load([base, overlay])
    lock = Lockfile.of(ir, forward.registry, forward.paths)

    backward = layers.load([overlay, base])
    drift = lock.drift_against(ir, backward.registry, backward.paths)
    assert any("layer stack changed" in line for line in drift), drift


def test_two_layers_sharing_a_name_do_not_collapse(built, tmp_path):
    """Equal layer names retain distinct positional identities and digest comparisons."""
    import shutil

    ir, _ = built
    # One layer declares the name, the other falls back to its basename — so this
    # exercises both halves of `layer_name` colliding on the same string.
    first = tmp_path / "one" / "somewhere-else"
    shutil.copytree(ROOT / "registry", first)
    manifest = yaml.safe_load((first / "registry.yml").read_text())
    manifest["name"] = "lab"
    (first / "registry.yml").write_text(_declared(first / "registry.yml", yaml.safe_dump(manifest)))
    second = _empty_layer(tmp_path / "two" / "lab")

    loaded = layers.load([first, second])
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert [layer.name for layer in lock.layers] == ["lab", "lab"]
    assert lock.layers[0].digest != lock.layers[1].digest, "distinct layers, distinct digests"

    # Change each position independently: name-keyed comparison would collapse one or report
    # the unchanged neighbor as drift.
    (first / "rules" / "extra.yml").write_text(
        _declared(first / "rules" / "extra.yml", "decisions: []\n")
    )
    changed = layers.load([first, second])
    assert lock.drift_against(ir, changed.registry, changed.paths) == [
        "layer lab has changed since it was locked"
    ]

    # Only the second position changes.
    (first / "rules" / "extra.yml").unlink()
    (second / "rules" / "extra.yml").write_text(
        _declared(second / "rules" / "extra.yml", "decisions: []\n")
    )
    changed = layers.load([first, second])
    assert lock.drift_against(ir, changed.registry, changed.paths) == [
        "layer lab has changed since it was locked"
    ], "the unchanged first layer must not report a line of its own"


def test_a_changed_layer_is_reported_as_drift(built, tmp_path):
    """Contracts can be unchanged while a rule that chose them moved."""
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    rules = layer / "rules" / "alignment.yml"
    rules.write_text(_declared(rules, rules.read_text().replace('">= 70"', '">= 60"')))
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("layer" in line and "registry" in line for line in drift)


def _changed_layer(tmp_path):
    import shutil

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer, ignore=shutil.ignore_patterns(".git"))
    sort = layer / "tools/nf-core/samtools/sort/contract.yml"
    sort.write_text(_declared(sort, sort.read_text().replace("priority: 0", "priority: 7")))
    return layers.load(layer)


def test_a_changed_layer_names_the_commit_it_was_locked_at(built, tmp_path):
    """A known repository commit is included in actionable drift output."""
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    commit = "c" * 40
    lock = lock.model_copy(update={"layers": [
        layer.model_copy(update={"source": "https://github.com/comeni-project/comeni-registry",
                                 "commit": commit})
        for layer in lock.layers]})
    changed = _changed_layer(tmp_path)
    [name] = [layer.name for layer in lock.layers]
    assert (f"layer {name} has changed since it was locked; it was locked at {commit} of "
            "https://github.com/comeni-project/comeni-registry"
            ) in lock.drift_against(ir, changed.registry, changed.paths)


def test_a_changed_layer_without_a_locator_reads_as_before(built, tmp_path):
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    changed = _changed_layer(tmp_path)
    [name] = [layer.name for layer in lock.layers]
    assert f"layer {name} has changed since it was locked" in lock.drift_against(
        ir, changed.registry, changed.paths)


def test_a_changed_layer_in_a_folder_names_the_folder(built, tmp_path):
    """Drift output includes a repository-relative layer folder when known."""
    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    lock = lock.model_copy(update={"layers": [
        layer.model_copy(update={"source": "https://github.com/x/y", "commit": "c" * 40,
                                 "path": "registry"})
        for layer in lock.layers]})
    drift = lock.drift_against(ir, *_registry_and_paths(_changed_layer(tmp_path)))
    assert any(line.endswith("of https://github.com/x/y, in registry") for line in drift), drift


def _registry_and_paths(changed):
    return changed.registry, changed.paths
