"""Registry gaps: what a step's declared data lacks, and which file to fix (spec §13.3)."""

from comeni_core.artifact.pipeline import RegistryProvenance
from comeni_core.plan.decision import ParamDecision
from mendel_authoring.gaps import GapKind, gaps_of

STAR = "nf-core/star/align@2.7.11b"


def test_a_setting_with_no_declared_domain_is_a_gap(rnaseq, declared):
    blueprint = rnaseq(150)
    record = ParamDecision(
        key="star_align.seq_platform", subject="seq_platform", candidates=[None],
        chosen=None, reason="flag-only", resolved_by="flag-only",
    )
    pipeline = blueprint.pipeline.model_copy(update={"decisions": [record]})
    found = gaps_of(blueprint.step("star_align"), pipeline, declared)
    assert [(g.kind, g.subject, g.fix) for g in found] == [
        (GapKind.NO_DOMAIN, "seq_platform", "registry/tools/nf-core/star/align/contract.yml")
    ]


def test_a_tool_with_no_description_is_a_gap(rnaseq, declared):
    blueprint = rnaseq(150)
    found = gaps_of(blueprint.step("multiqc"), blueprint.pipeline, declared)
    assert [(g.kind, g.fix) for g in found] == [
        (GapKind.NO_DESCRIPTION, "registry/tools/nf-core/multiqc/tool.yml")
    ]


def test_an_unverified_contract_is_a_gap(rnaseq, declared):
    blueprint = rnaseq(150)
    pipeline = blueprint.pipeline.model_copy(
        update={"registry": RegistryProvenance(unverified=[STAR])}
    )
    found = gaps_of(blueprint.step("star_align"), pipeline, declared)
    assert [g.kind for g in found] == [GapKind.UNVERIFIED]


def test_a_complete_step_has_no_gap(rnaseq, declared):
    blueprint = rnaseq(150)
    assert gaps_of(blueprint.step("fastqc"), blueprint.pipeline, declared) == []
