from pathlib import Path

from comeni_core.review import ValueSource
from mendel_forge.assemble import scaffold_for
from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]


def _scaffold():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), ROOT / "registry")
    return scaffold_for(
        obs, layers.load(ROOT / "registry"), ident="nf-core/fastqc", version="0.12.1"
    )


def test_the_process_name_arrives_filled_and_derived():
    filled = _scaffold().filled["nf_process"]
    assert filled.value == "FASTQC"
    assert filled.how is ValueSource.DERIVED
    assert filled.by == "nf-core"
    assert filled.why, "a derived value still has to say why — the evidence locator"


def test_semantic_fields_arrive_as_holes():
    open_fields = {h.subject for h in _scaffold().holes}
    assert "roles" in open_fields
    assert any(f.endswith("type_id") for f in open_fields)


def test_every_hole_says_why_it_is_open():
    for hole in _scaffold().holes:
        assert hole.why_open, f"{hole.subject} is open with no stated reason"


def test_a_type_id_hole_carries_the_declared_types_as_candidates():
    hole = next(h for h in _scaffold().holes if h.subject.endswith("type_id"))
    assert "qc.report" in [c.value for c in hole.candidates]


def test_a_hole_carries_the_prose_that_bears_on_it():
    hole = next(h for h in _scaffold().holes if h.subject == "produces[0].type_id")
    assert hole.evidence, "meta.yml's description of the output should reach the hole"


def test_the_target_path_follows_the_registry_convention():
    assert _scaffold().target == "tools/nf-core/fastqc/contract.yml"


def test_a_multi_segment_tool_does_not_double_its_name():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:samtools/sort"), ROOT / "registry")
    scaffold = scaffold_for(
        obs, layers.load(ROOT / "registry"), ident="nf-core/samtools/sort", version="1.21.0"
    )
    assert scaffold.target == "tools/nf-core/samtools/sort/contract.yml"


def test_a_source_with_no_module_holes_everything_the_module_would_have_given():
    from .opaque_source import OpaqueSource

    fixtures = Path(__file__).parent / "fixtures" / "opaque"
    obs = OpaqueSource().ingest(ToolRef.parse("opaque:widget"), fixtures)
    scaffold = scaffold_for(
        obs, layers.load(ROOT / "registry"), ident="opaque/widget", version="1.4.0"
    )
    open_fields = {h.subject for h in scaffold.holes}
    assert "nf_process" in open_fields
    assert "container" not in open_fields, "the container WAS derivable from tool.yml"
