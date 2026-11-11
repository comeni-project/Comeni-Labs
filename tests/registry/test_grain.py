"""Grain: one item per study or per sample, for channels, types and ports (#466).

`Scope` (`run`/`sample`) and `Cardinality` (`1`/`*`) said two halves of one thing: how many
items a channel carries relative to the analysis, and whether a port takes one of them or all.
"""

import pytest
from comeni_core.declared.contract import ModuleContract
from comeni_core.plan.tiers import Grain
from mendel_resolver import layers
from support.paths import ROOT


@pytest.fixture(scope="module")
def stack():
    return layers.load(ROOT / "registry")


def test_a_reference_type_is_study_grain(stack):
    assert stack.vocabulary.grains["genome.fasta"] is Grain.STUDY
    assert stack.vocabulary.grains["fastq.reads"] is Grain.SAMPLE


def test_multiqc_gathers_the_study(stack):
    port = next(p for p in stack.registry.get("nf-core/multiqc@1.35").consumes
                if p.name == "reports")
    assert port.grain is Grain.STUDY
    assert port.many is True


def _contract(port: dict) -> dict:
    return {
        "id": "test/tool@1.0", "nf_include": "test/tool", "container": "x:1",
        "consumes": [port], "produces": [{"name": "out", "type_id": "qc.report"}],
    }


def test_cardinality_is_gone():
    with pytest.raises(ValueError, match="cardinality"):
        ModuleContract.model_validate(
            _contract({"name": "reports", "type_id": "qc.report", "cardinality": "*"}))


def test_many_needs_a_finer_grain_to_gather():
    with pytest.raises(ValueError, match="MD0331"):
        ModuleContract.model_validate(
            _contract({"name": "genome", "type_id": "genome.fasta", "grain": "sample",
                       "many": True}))


def test_a_drawn_channel_grain_is_closed_at_the_boundary():
    """A draft arrives as a request body: an old `run` is refused there, not deep in
    materialisation as a bare `ValueError` (Task 1 review)."""
    from comeni_core.plan.draft import DraftChannel

    assert DraftChannel(ports=("a.b",), grain="study").grain is Grain.STUDY
    with pytest.raises(ValueError, match="grain"):
        DraftChannel(ports=("a.b",), grain="run")
