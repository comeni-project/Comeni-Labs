"""IR serialization retains registry layers and displacement provenance."""

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
    """Add an explicit declaration kind and ID to a fixture body, if absent."""
    path = pathlib.Path(path)
    # Fixtures may nest files below their kind directory, so inspect every ancestor.
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

# The resolved spine requires all three declared input types.
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
    """Contract displacement remains visible in the artifact."""
    base = ROOT / "registry"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = base / "tools/nf-core/samtools/sort/contract.yml"
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
    """Published provenance uses portable layer names and never local paths."""
    base = ROOT / "registry"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = base / "tools/nf-core/samtools/sort/contract.yml"
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
    """Layer order is retained because later entries have higher precedence."""
    ir = PipelineIR(registry_layers=["a", "b"])
    assert ir.registry_layers == ["a", "b"]


def test_the_ir_round_trips_with_its_provenance(tmp_path):
    """Serialized provenance is accepted when an IR is loaded again."""
    base = ROOT / "registry"
    overlay = tmp_path / "lab"
    (overlay / "contracts").mkdir(parents=True)
    sort = base / "tools/nf-core/samtools/sort/contract.yml"
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
