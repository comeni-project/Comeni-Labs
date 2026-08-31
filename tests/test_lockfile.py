"""What a pipeline was built against, pinned by content — and how it notices drift.

Federation §4.1. Two hard rules are tested rather than asserted in prose: a lockfile holds
no filesystem path, and it holds no timestamp. Both are easy to satisfy on the day and easy
to break later, which is what makes them tests.
"""

import pathlib

import pytest
import yaml
from comeni_core.artifact.lockfile import Lockfile
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
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

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def built():
    loaded = layers.load(ROOT / "registry")
    goal = Goal(
        # `genome.fasta` is not optional: Plan 1.5 made the reference a declared type
        # precisely because the aligner index builders were being handed an empty tuple
        # where a genome belongs. Without it here the spine is unroutable, which is the
        # correct behaviour and the reason the plan's own fixture no longer worked.
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
    """A path is meaningless on another machine, and invariant 15 keeps them out.

    Layers are identified by name and digest. `Lockfile.of` is handed absolute paths and
    must reduce them to basenames before anything is stored.
    """
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
    sort = next(layer.rglob("sort/contract.yml"))
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
    next(layer.rglob("sort/contract.yml")).unlink()
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("no longer in the registry" in line for line in drift)


def _empty_layer(path):
    for name in ("contracts", "rules", "vocabularies", "measurements"):
        (path / name).mkdir(parents=True)
    return path


def test_reordering_the_layer_stack_is_drift(built, tmp_path):
    """A registry is a stack and its order is semantic.

    Invariant 11: a higher layer shadows every lower-layer contract for a module key. So
    inverting the stack can change which contract wins while every layer digest stays
    identical. Comparing layers as a name-keyed mapping reported no drift at all for this.
    """
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
    """Two layers can still share a name, so the comparison stays positional.

    Written for the day-one case: Task 8 named the public layer `registry/`, so a
    laboratory stacking it over their own `registry/` got two entries with one name. Audit
    A12 removed *that* collision — the public layer declares `comeni-registry-examples` in
    its manifest and a hand-made overlay falls back to its basename, so the two no longer
    match. It did not remove the class. Two manifest-less overlays with the same basename
    collide exactly as before, and so would two layers declaring the same name, which is
    what this now builds.
    """
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

    # **Each layer separately, and exactly one line each.** Both halves are load-bearing
    # and neither is enough alone — established by reverting `drift_against` to two
    # different wrong implementations and watching which tests noticed:
    #
    #   fully name-keyed ({name: digest} both sides)  — caught only by changing the FIRST
    #     layer. The mapping is last-wins, so the pinned and current entries both collapse
    #     to the second layer, which did not change, and no drift is reported at all.
    #   positional names, name-keyed digests          — caught only by changing the SECOND
    #     layer. Both current layers are compared against one pinned digest, so the
    #     unchanged first layer reports a spurious line beside the real one.
    #
    # Until 2026-08-06 this changed the first layer and asserted merely that *some* line
    # mentioned the layer. That passed against both wrong implementations, because both do
    # report drift here — just for the wrong reason, or one time too many. A guard that
    # cannot fail is not a guard; it took reverting the code to find that out.
    # Only the first layer.
    (first / "rules" / "extra.yml").write_text(
        _declared(first / "rules" / "extra.yml", "decisions: []\n")
    )
    changed = layers.load([first, second])
    assert lock.drift_against(ir, changed.registry, changed.paths) == [
        "layer lab has changed since it was locked"
    ]

    # Only the second. Changing *both* would report two lines under either implementation
    # and prove nothing, which is the trap the first attempt at this fell into.
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
