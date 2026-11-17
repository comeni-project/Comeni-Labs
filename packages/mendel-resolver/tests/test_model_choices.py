"""The AI's choices are the AI's: tier 4, source model, flagged, the rule kept beside them
(#463, the builder agent)."""

from comeni_core.goal.asked import ParamOverride, ProducerPin
from comeni_core.plan.ir import Tier
from comeni_core.plan.tiers import ValueSource

HISAT2_ALIGN = "nf-core/hisat2/align@2.2.2"


def _node(ir, node_id):
    return next(n for n in ir.nodes if n.id == node_id)


def test_a_model_pin_is_the_ais_choice_and_stays_flagged(resolve_rnaseq):
    star = _node(resolve_rnaseq(), "star_align")
    ir = resolve_rnaseq(pins=[ProducerPin(site=star.site, contract=HISAT2_ALIGN, by="model",
                                          because="less memory")])
    aligner = _node(ir, "hisat2_align")
    assert aligner.selection.source is ValueSource.MODEL
    assert aligner.selection.tier is Tier.AMBIGUOUS
    assert "the AI chose" in aligner.selection.reason
    assert "less memory" in aligner.selection.reason
    assert star.contract_id in aligner.selection.reason, "the engine's pick is kept beside it"
    assert any("hisat2_align" in key for key in ir.needs_review())


GENOME = {"genome_length": 3_100_000_000}
"""A stated genome length: the index-building rule then decides `sa_index_nbases`."""


def test_a_model_setting_over_a_rule_keeps_the_rules_value_beside_it(resolve_rnaseq):
    ruled = next(b for b in _node(resolve_rnaseq(profile=GENOME), "star_genomegenerate").params
                 if b.name == "sa_index_nbases")
    assert ruled.value.tier is Tier.DATA_PROFILED
    ir = resolve_rnaseq(profile=GENOME, params=[ParamOverride(
        name="sa_index_nbases", value=12, by="model", because="testing a smaller index")])
    set_ = next(b for b in _node(ir, "star_genomegenerate").params
                if b.name == "sa_index_nbases")
    assert set_.value.value == 12
    assert set_.value.source is ValueSource.MODEL
    assert set_.value.tier is Tier.AMBIGUOUS
    assert set_.value.overrode is not None
    assert set_.value.overrode.value == ruled.value.value
    assert "testing a smaller index" in set_.value.reason


def test_a_persons_pin_reads_as_before(resolve_rnaseq):
    star = _node(resolve_rnaseq(), "star_align")
    pin = ProducerPin(site=star.site, contract=HISAT2_ALIGN)
    assert "by" not in pin.model_dump(mode="json") and "because" not in pin.model_dump()
    aligner = _node(resolve_rnaseq(pins=[pin]), "hisat2_align")
    assert aligner.selection.reason.startswith("you chose")
    assert aligner.selection.source is ValueSource.HUMAN
