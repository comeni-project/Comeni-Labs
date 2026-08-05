"""What a pipeline was built against, pinned by content — and how it notices drift.

Federation §4.1. Two hard rules are tested rather than asserted in prose: a lockfile holds
no filesystem path, and it holds no timestamp. Both are easy to satisfy on the day and easy
to break later, which is what makes them tests.
"""

import pathlib

import pytest
from comeni_core.lockfile import Lockfile
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

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
    return resolve(goal, loaded.registry, loaded.rules), loaded


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
    sort = next(layer.rglob("samtools-sort.yml"))
    sort.write_text(sort.read_text().replace("priority: 0", "priority: 7"))
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("samtools/sort" in line for line in drift)


def test_a_missing_contract_is_reported_as_drift(built, tmp_path):
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    next(layer.rglob("samtools-sort.yml")).unlink()
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


def test_two_layers_sharing_a_basename_do_not_collapse(built, tmp_path):
    """Not exotic: Task 8 names the public layer `registry/`, so a laboratory stacking it
    over their own `registry/` produces two entries with one name on day one."""
    import shutil

    ir, _ = built
    first = _empty_layer(tmp_path / "one" / "registry").parent / "registry"
    shutil.rmtree(first)
    shutil.copytree(ROOT / "registry", first)
    second = _empty_layer(tmp_path / "two" / "registry")

    loaded = layers.load([first, second])
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)
    assert [layer.name for layer in lock.layers] == ["registry", "registry"]
    assert lock.layers[0].digest != lock.layers[1].digest, "distinct layers, distinct digests"

    # The *first* layer, specifically. A name-keyed mapping is last-wins, so a change to
    # the second stays visible by luck and only the first disappears — which is why this
    # test changes the first. It is also the one that matters: the lower layer is the
    # public registry, and the overlay above it is the small local thing.
    (first / "rules" / "extra.yml").write_text("decisions: []\n")
    changed = layers.load([first, second])
    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("registry" in line for line in drift), drift


def test_a_changed_layer_is_reported_as_drift(built, tmp_path):
    """Contracts can be unchanged while a rule that chose them moved."""
    import shutil

    ir, loaded = built
    lock = Lockfile.of(ir, loaded.registry, loaded.paths)

    layer = tmp_path / "registry"
    shutil.copytree(ROOT / "registry", layer)
    rules = layer / "rules" / "rnaseq.yml"
    rules.write_text(rules.read_text().replace('">= 70"', '">= 60"'))
    changed = layers.load(layer)

    drift = lock.drift_against(ir, changed.registry, changed.paths)
    assert any("layer" in line and "registry" in line for line in drift)
