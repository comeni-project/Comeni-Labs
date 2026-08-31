"""The IR records which registry built it.

Federation §8 says the dashboard "renders `registry_layers` and shadow markers, but that is
display of data the IR already carries". It did not carry it. These tests are that sentence
becoming true.
"""

import pathlib

from comeni_core.plan.ir import PipelineIR
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

ROOT = pathlib.Path(__file__).parents[3]

# Plan 1.5 made the reference a declared type, so the spine is unroutable without it.
SPINE_INPUTS = ["fastq.reads", "annotation.gtf", "genome.fasta"]


def test_an_ir_defaults_to_no_layers():
    assert PipelineIR().registry_layers == []
    assert PipelineIR().displaced == []


def test_a_resolved_ir_records_the_layers_it_was_built_from():
    loaded = layers.load(ROOT / "registry")
    ir = resolve(
        Goal(have=[GoalInput(type_id="fastq.reads")], want=["qc.report"]),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        layer_names=[p.name for p in loaded.paths],
    )
    assert ir.registry_layers == ["registry"]


def test_a_resolved_ir_carries_the_displacements(tmp_path):
    """An overlay that displaced a contract must be visible in the artifact, not only
    on stderr at build time. A published pipeline that hid it would be unauditable."""
    base = ROOT / "registry"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = next(base.rglob("sort/contract.yml"))
    (overlay / "contracts" / "sort.yml").write_text(
        _declared(
            overlay / "contracts" / "sort.yml",
            sort.read_text().replace("@1.21.0", "@1.99.0"))
    )
    loaded = layers.load([base, overlay])
    ir = resolve(
        Goal(
            have=[GoalInput(type_id=t) for t in SPINE_INPUTS],
            want=["counts.matrix"],
            constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        ),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        layer_names=[p.name for p in loaded.paths],
    )
    assert ir.registry_layers == ["registry", "lab"]
    assert [d.key for d in ir.displaced] == ["nf-core/samtools/sort"]


def test_a_displacement_names_the_layer_and_never_its_path(tmp_path):
    """`winning_layer` held `str(layer)` — an absolute filesystem path — until
    `PipelineIR.shadowed` made the record reachable from a publish bundle and the egress
    guard walked it for the first time. The record is a `Displacement` now — same rule.

    A path in a published artifact is meaningless on the machine that reads it and says
    more about the machine that wrote it than anyone intended. The lockfile has a dedicated
    test for exactly this rule; this record was going straight past it.
    """
    base = ROOT / "registry"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = next(base.rglob("sort/contract.yml"))
    (overlay / "contracts" / "sort.yml").write_text(
        _declared(
            overlay / "contracts" / "sort.yml",
            sort.read_text().replace("@1.21.0", "@1.99.0"))
    )
    loaded = layers.load([base, overlay])
    ir = resolve(
        Goal(
            have=[GoalInput(type_id=t) for t in SPINE_INPUTS],
            want=["counts.matrix"],
            constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        ),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        layer_names=[p.name for p in loaded.paths],
    )
    assert [d.winning_layer for d in ir.displaced] == ["lab"]

    serialised = ir.model_dump_json()
    assert str(tmp_path) not in serialised
    assert "/contracts" not in serialised


def test_layers_are_recorded_in_stacking_order():
    """Order is meaning: later layers win. A set would lose that."""
    ir = PipelineIR(registry_layers=["a", "b"])
    assert ir.registry_layers == ["a", "b"]


def test_the_ir_round_trips_with_its_provenance(tmp_path):
    """`mendel upgrade` reads a bundle back off disk. A field written on dump and refused
    on load is exactly the defect Plan 1.5 found in `review_level`."""
    base = ROOT / "registry"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = next(base.rglob("sort/contract.yml"))
    (overlay / "contracts" / "sort.yml").write_text(
        _declared(
            overlay / "contracts" / "sort.yml",
            sort.read_text().replace("@1.21.0", "@1.99.0"))
    )
    loaded = layers.load([base, overlay])
    ir = resolve(
        Goal(
            have=[GoalInput(type_id=t) for t in SPINE_INPUTS],
            want=["counts.matrix"],
            constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        ),
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        layer_names=[p.name for p in loaded.paths],
    )
    again = PipelineIR.model_validate_json(ir.model_dump_json())
    assert again.registry_layers == ir.registry_layers
    assert [d.key for d in again.displaced] == [d.key for d in ir.displaced]
