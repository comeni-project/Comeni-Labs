"""A small RNA-seq blueprint and a fake registry, so the pure tests never run the resolver.

Four steps in the blueprint's order — fastqc, star_align, featurecounts, multiqc — with the
aligner either settled by a measured read length (tier 3) or waiting on it (tier 4, `unknown`).
MultiQC has no tool description on purpose: a card leaves *does* out rather than inventing it.
"""

import pytest
from comeni_core.artifact.pipeline import Channel, ModuleRef, Pipeline, Setting, Step, Why
from comeni_core.goal.asked import Goal
from comeni_core.goal.premise import PremiseOrigin, PremiseRecord
from comeni_core.plan.decision import ParamDecision, ProducerDecision
from comeni_core.plan.tiers import Tier, ValueSource
from mendel_authoring.blueprint import Blueprint

DIGEST = "sha256:" + "0" * 64
FASTQC = "nf-core/fastqc@0.12.1"
STAR = "nf-core/star/align@2.7.11b"
HISAT2 = "nf-core/hisat2/align@2.2.2"
COUNTS = "nf-core/subread/featurecounts@2.1.1"
MULTIQC = "nf-core/multiqc@1.25.1"


class FakeDeclared:
    OUTPUTS = {
        FASTQC: ["qc.report"],
        STAR: ["alignment.bam", "alignment.bai"],
        HISAT2: ["alignment.bam"],
        COUNTS: ["counts.matrix"],
        MULTIQC: ["qc.report"],
    }
    TOOLS = {
        "nf-core/fastqc": "FastQC checks the quality of raw reads.",
        "nf-core/star": "STAR aligns RNA-seq reads to a genome, splice-aware.",
        "nf-core/hisat2": "HISAT2 aligns reads to a genome with a small memory footprint.",
        "nf-core/subread": "featureCounts counts reads per gene.",
    }
    FAMILIES = {
        "qc": "quality reports",
        "alignment": "reads placed on a reference",
        "counts": "reads counted per feature",
        "fastq": "raw sequencing reads",
    }

    def outputs(self, contract_id: str) -> list[str]:
        return self.OUTPUTS[contract_id]

    def tool(self, tool_id: str) -> str | None:
        return self.TOOLS.get(tool_id)

    def family(self, family_id: str) -> str | None:
        return self.FAMILIES.get(family_id)


def _step(node: str, contract: str, why: Why, settings: list[Setting] = ()) -> Step:
    return Step(
        id=node,
        module=ModuleRef(contract_id=contract, digest=DIGEST),
        process=node.upper(),
        include=f"./modules/{node}/main.nf",
        why=why,
        settings=list(settings),
    )


def _why(tier: Tier, reason: str, **more) -> Why:
    return Why(tier=tier, source=ValueSource.RESOLVER, reason=reason, **more)



_GOAL = Goal.model_validate({"have": [{"type_id": "fastq.reads"}], "want": ["counts.matrix"]})

@pytest.fixture
def declared() -> FakeDeclared:
    return FakeDeclared()


@pytest.fixture
def rnaseq():
    """`rnaseq(read_length=150)` settles the aligner at tier 3; `read_length=None` leaves it open
    on the fact; `strandedness_open=True` adds a tier-4 setting with no value."""

    def build(read_length: int | None, strandedness_open: bool = False) -> Blueprint:
        if read_length is None:
            star_why = _why(
                Tier.AMBIGUOUS,
                "implementation:aligner could not apply (read_length unknown); "
                "chosen by flag-only: the registry's priority pick",
                axis_reason="read length decides which aligner is appropriate (Dobin et al. 2013)",
            )
            decisions = [
                ProducerDecision(
                    key="producer:alignment.bam",
                    subject="producer:alignment.bam",
                    candidates=[STAR, HISAT2],
                    chosen=STAR,
                    reason="flag-only",
                    resolved_by="flag-only",
                    unknown=["read_length"],
                )
            ]
        else:
            star_why = _why(
                Tier.DATA_PROFILED,
                f"read length {read_length} ≥ 100: STAR",
                axis_reason="read length decides which aligner is appropriate (Dobin et al. 2013)",
                premise=[
                    PremiseRecord(
                        id="read_length",
                        value=read_length,
                        origin=PremiseOrigin.MEASURED,
                        pieces=["fastq@1.1.0", "read_length@1.0.0"],
                    )
                ],
            )
            decisions = []
        counts_settings = []
        if strandedness_open:
            counts_settings = [
                Setting(
                    name="strandedness",
                    value=None,
                    via="ext",
                    why=_why(Tier.AMBIGUOUS, "no rule decides strandedness"),
                )
            ]
            decisions.append(
                ParamDecision(
                    key="featurecounts.strandedness",
                    subject="strandedness",
                    candidates=[0, 1, 2],
                    chosen=None,
                    reason="flag-only",
                    resolved_by="flag-only",
                )
            )
        steps = [
            _step("fastqc", FASTQC, _why(Tier.STRUCTURAL, "the only contract producing qc.report")),
            _step("star_align", STAR, star_why),
            _step(
                "featurecounts", COUNTS, _why(Tier.CONVENTION, "registry priority 10"),
                counts_settings,
            ),
            _step("multiqc", MULTIQC, _why(Tier.CONVENTION, "uncontested")),
        ]
        pipeline = Pipeline(
            intent=_GOAL.intent,
            facts=_GOAL.facts,
            steps=steps,
            channels=[
                Channel(
                    name="reads",
                    param="input",
                    type_id="fastq.reads",
                    expression="Channel.fromPath(params.input)",
                    params=["input"],
                )
            ],
            decisions=decisions,
        )
        return Blueprint(registry=DIGEST, order=[s.id for s in steps], pipeline=pipeline)

    return build


@pytest.fixture
def blueprint_of():
    """`blueprint_of({"node": "contract", …}, sites={"node": Site(…)})`: a blueprint of those
    steps in that order, at tier 2 — for tests about which steps exist, not why."""
    def build(tools: dict[str, str], sites: dict | None = None) -> Blueprint:
        steps = [
            _step(node, contract, _why(Tier.CONVENTION, "x")) for node, contract in tools.items()
        ]
        pipeline = Pipeline(
            intent=_GOAL.intent,
            facts=_GOAL.facts,
            steps=steps,
        )
        return Blueprint(registry=DIGEST, order=list(tools), pipeline=pipeline, sites=sites or {})

    return build
