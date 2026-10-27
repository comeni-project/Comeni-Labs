"""A structural change (A1) arrives as a `DecisionChange`, like every other change, and is written
through `services.changes`: a role switched off, a tool excluded at a site, a port's source."""

import pytest
from comeni_core.goal.asked import ProducerExclusion, RoleAbsence, Site, SourcePin
from comeni_core.plan.draft import DraftGraph, DraftNode
from mendel_api.services import changes, decisions, drafts, registry
from mendel_api_tests.database import reachable
from mendel_authoring.intent import read_edit
from mendel_authoring.payloads import DecisionChange

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")

STAR = "nf-core/star/align@2.7.11b"
COUNTS = "nf-core/subread/featurecounts@2.1.1"
SORT = "nf-core/samtools/sort@1.24"
FASTQC = "nf-core/fastqc@0.12.1"
SITE = Site(type_id="alignment.bam")


def _draft():
    return drafts.create(DraftGraph(), "intent changes", "ana")


def _constraints(draft):
    return decisions.goal(draft).constraints


def test_a_role_change_switches_it_off_and_back_on():
    draft = _draft()
    assert changes.apply(draft, DecisionChange(kind="role", subject="trimming"), who="ana")
    assert _constraints(draft).absent_roles == [RoleAbsence(role="trimming")]
    assert changes.apply(draft, DecisionChange(kind="role", subject="trimming", retract=True),
                         who="ana")
    assert _constraints(draft).absent_roles == []


def test_an_exclude_change_excludes_at_the_site():
    draft = _draft()
    changes.apply(draft, DecisionChange(kind="exclude", subject="alignment.bam", value=STAR),
                  who="ana")
    assert _constraints(draft).exclusions == [ProducerExclusion(site=SITE, contract=STAR)]


def test_a_source_change_pins_the_port():
    draft = _draft()
    subject = decisions.source_key(COUNTS, "bam")
    changes.apply(draft, DecisionChange(kind="source", subject=subject, value=SORT), who="ana")
    assert _constraints(draft).sources == [SourcePin(consumer=COUNTS, port="bam", producer=SORT)]
    assert changes.describe(DecisionChange(kind="source", subject=subject, value=SORT)) == (
        "SUBREAD_FEATURECOUNTS reads its bam from SAMTOOLS_SORT")


@pytest.mark.parametrize("change", [
    DecisionChange(kind="role", subject="no_such_role"),
    DecisionChange(kind="exclude", subject="alignment.bam", value="nf-core/nothing@0.0.0"),
    DecisionChange(kind="source", subject=f"{COUNTS}|no_such_port", value=SORT),
    DecisionChange(kind="source", subject=f"{COUNTS}|bam", value="nf-core/nothing@0.0.0"),
])
def test_an_undeclared_role_tool_or_port_is_refused_with_MI0204(change):
    with pytest.raises(ValueError, match="MI0204"):
        changes.check(change)


def test_reading_change_round_trips():
    """Every kind a canvas edit is read as reaches the goal through the one writer."""
    stack = registry.stack()
    before = DraftGraph(nodes=[DraftNode(id="star_align", contract_id=STAR),
                               DraftNode(id="sort", contract_id=SORT)])
    after = DraftGraph(nodes=[DraftNode(id="sort", contract_id=SORT),
                              DraftNode(id="qc", contract_id=FASTQC)])
    readings = read_edit(before, after, {"star_align": SITE}, stack.registry)
    assert {r.kind for r in readings} >= {"want", "pin"}
    draft = _draft()
    for reading in readings:
        changes.apply(draft, reading.change(), who="ana")
    goal = decisions.goal(draft)
    assert "qc.report" in goal.want
    assert any(p.contract == FASTQC for p in goal.constraints.producers)
