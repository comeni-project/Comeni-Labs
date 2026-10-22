"""A person's structural intent (A1, the one-builder design), over the shipped registry: a role
switched off, a tool excluded at a site, a port's source pinned. Each is honoured on every
re-plan, and a conflict is raised with a code rather than resolved silently."""

import pytest
from comeni_core.goal.asked import RoleAbsence
from mendel_resolver.router import IntentConflict


def _node(ir, node_id):
    return next(n for n in ir.nodes if n.id == node_id)


def test_switching_trimming_off_routes_the_reads_straight_to_the_aligner(resolve_rnaseq):
    ir = resolve_rnaseq(absent_roles=[RoleAbsence(role="trimming")])
    assert "trimgalore" not in {n.id for n in ir.nodes}
    feeding_star = {e.from_node for e in ir.edges if e.to_node == "star_align"}
    assert feeding_star, "the aligner is fed by something"
    assert "trimgalore" not in feeding_star


def test_switching_off_a_role_the_goal_needs_is_a_coded_conflict(resolve_rnaseq):
    with pytest.raises(IntentConflict, match="MD03") as raised:
        resolve_rnaseq(absent_roles=[RoleAbsence(role="alignment")])
    assert raised.value.intent == RoleAbsence(role="alignment")
    assert "alignment" in str(raised.value)


def test_excluding_star_takes_the_next_aligner_and_says_why(resolve_rnaseq):
    from comeni_core.goal.asked import ProducerExclusion

    star = _node(resolve_rnaseq(), "star_align")
    ir = resolve_rnaseq(exclusions=[ProducerExclusion(site=star.site, contract=star.contract_id)])
    aligner = next(n for n in ir.nodes if n.site == star.site)
    assert aligner.contract_id != star.contract_id
    assert aligner.selection.reason.startswith(f"you excluded {star.contract_id} here; ")


def test_excluding_the_only_producer_is_a_coded_conflict_naming_it(resolve_rnaseq):
    from comeni_core.goal.asked import ProducerExclusion

    sort = _node(resolve_rnaseq(), "samtools_sort")
    exclusion = ProducerExclusion(site=sort.site, contract=sort.contract_id)
    with pytest.raises(IntentConflict, match="MD0320") as raised:
        resolve_rnaseq(exclusions=[exclusion])
    assert raised.value.intent == exclusion
    assert sort.contract_id in str(raised.value)


def test_an_intent_that_applies_nowhere_is_reported(resolve_rnaseq, stack):
    from comeni_core.goal.asked import Constraints, ProducerExclusion, Site, SourcePin
    from mendel_resolver.resolve import inert_intents

    ir = resolve_rnaseq()
    star = _node(ir, "star_align")
    applies = ProducerExclusion(site=star.site, contract="nf-core/hisat2/align@2.2.2")
    unasked = ProducerExclusion(site=Site(type_id="qc.report"), contract=star.contract_id)
    nothing_fills = RoleAbsence(role="no_such_role")
    no_consumer = SourcePin(consumer="nf-core/multiqc@1.25.1", port="reports",
                            producer=star.contract_id)
    constraints = Constraints(exclusions=[applies, unasked], absent_roles=[nothing_fills],
                              sources=[no_consumer])
    assert inert_intents(ir, constraints, stack.registry) == [unasked, nothing_fills, no_consumer]


COUNTS = "nf-core/subread/featurecounts@2.0.6"


def test_without_a_pin_the_extra_tool_is_not_in_the_plan(resolve_with_markdup):
    assert "lab_markdup" not in {n.id for n in resolve_with_markdup().nodes}


def test_a_pinned_source_feeds_the_port_and_is_recorded_as_the_persons(resolve_with_markdup):
    from comeni_core.goal.asked import SourcePin
    from comeni_core.plan.decision import SourceDecision

    pin = SourcePin(consumer=COUNTS, port="bam", producer="lab/markdup@1.0.0")
    ir = resolve_with_markdup(sources=[pin])
    edges = {(e.from_node, e.to_node, e.to_port) for e in ir.edges}
    assert ("samtools_sort", "lab_markdup", "bam") in edges
    assert ("lab_markdup", "subread_featurecounts", "bam") in edges
    assert ("samtools_sort", "subread_featurecounts", "bam") not in edges
    decided = [d for d in ir.decisions if isinstance(d, SourceDecision)]
    assert decided, "the pin is recorded"
    assert decided[0].human_override == "lab_markdup.bam"
    assert decided[0].resolved_by == "person"


def test_a_pin_whose_producer_cannot_feed_the_port_is_a_coded_conflict(resolve_rnaseq):
    from comeni_core.goal.asked import SourcePin

    unsorted = SourcePin(consumer=COUNTS, port="bam", producer="nf-core/star/align@1.11.0")
    with pytest.raises(IntentConflict, match="MD0321") as raised:
        resolve_rnaseq(sources=[unsorted])
    assert raised.value.intent == unsorted


def test_a_re_plan_keeps_intents_and_reports_a_pin_whose_consumer_left(resolve_rnaseq, stack):
    """Review Focus 5: read length 150 → 50 moves the aligner from STAR to HISAT2."""
    from comeni_core.goal.asked import Constraints, SourcePin
    from mendel_resolver.resolve import inert_intents

    off = RoleAbsence(role="trimming")
    on_star = SourcePin(consumer="nf-core/star/align@1.11.0", port="reads",
                        producer="nf-core/trimgalore@0.6.10")
    before = resolve_rnaseq(absent_roles=[off])
    assert "star_align" in {n.id for n in before.nodes}
    after = resolve_rnaseq(absent_roles=[off], profile={"read_length": 50})
    assert "star_align" not in {n.id for n in after.nodes}
    assert "trimgalore" not in {n.id for n in after.nodes}
    constraints = Constraints(absent_roles=[off], sources=[on_star])
    assert inert_intents(after, constraints, stack.registry) == [on_star]
