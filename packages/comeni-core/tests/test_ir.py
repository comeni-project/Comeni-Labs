from comeni_core.plan.ir import (
    IREdge,
    IRNode,
    PipelineIR,
    ResolvedValue,
    ReviewLevel,
    Tier,
    review_level_for,
)


def test_review_level_mapping_is_fixed():
    assert review_level_for(Tier.STRUCTURAL) is ReviewLevel.NONE
    assert review_level_for(Tier.CONVENTION) is ReviewLevel.NONE
    assert review_level_for(Tier.DATA_PROFILED) is ReviewLevel.ADVISORY
    assert review_level_for(Tier.AMBIGUOUS) is ReviewLevel.REQUIRED


def test_resolved_value_derives_its_review_level():
    value = ResolvedValue(value=2, tier=Tier.DATA_PROFILED, reason="rule strandedness-reverse")
    assert value.review_level is ReviewLevel.ADVISORY


def test_a_resolved_value_accepts_its_serialized_review_level():
    value = ResolvedValue(value=2, tier=Tier.DATA_PROFILED, reason="rule strandedness-reverse")

    assert ResolvedValue.model_validate_json(value.model_dump_json()) == value


def test_needs_review_lists_only_required_items():
    ir = PipelineIR(
        nodes=[
            IRNode(
                id="featurecounts",
                contract_id="nf-core/subread/featurecounts@2.1.1",
                params={
                    "strandedness": ResolvedValue(
                        value=2, tier=Tier.DATA_PROFILED, reason="rule"
                    ),
                    "seq_platform": ResolvedValue(
                        value="illumina", tier=Tier.AMBIGUOUS, reason="no rule"
                    ),
                },
            )
        ],
        edges=[],
    )
    assert ir.needs_review() == ["featurecounts.seq_platform"]


def test_ir_is_deterministically_serialisable():
    ir = PipelineIR(
        nodes=[],
        edges=[
            IREdge(
                from_node="star",
                from_port="bam",
                to_node="sort",
                to_port="bam",
                type_id="alignment.bam",
                states=frozenset({"b", "a"}),
            )
        ],
    )
    once = ir.model_dump_json()
    assert once == PipelineIR.model_validate_json(once).model_dump_json()


def test_a_goal_supplied_value_records_its_source():
    """Resolution quality and the source that supplied a value remain independent."""
    from comeni_core.plan.tiers import ValueSource

    derived = ResolvedValue(value=2, tier=Tier.DATA_PROFILED, reason="rule")
    pinned = ResolvedValue(
        value="illumina", tier=Tier.STRUCTURAL, source=ValueSource.SAID, reason="goal"
    )
    assert derived.source is ValueSource.RESOLVER
    assert pinned.source is ValueSource.SAID
