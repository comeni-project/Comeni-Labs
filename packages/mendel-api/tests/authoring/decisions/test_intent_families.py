"""A person's structural intent (A1) as decision rows: each is the person's, has a history, reaches
the goal, and a later intent on the same subject retracts the earlier one."""

import pytest
from comeni_core.goal.asked import ProducerExclusion, RoleAbsence, Site, SourcePin
from comeni_core.plan.draft import DraftGraph
from mendel_api.services import decisions, drafts
from mendel_api_tests.database import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")

STAR = "nf-core/star/align@1.11.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
SORT = "nf-core/samtools/sort@1.21.0"
SITE = Site(type_id="alignment.bam")


def _draft():
    return drafts.create(DraftGraph(), "intents", "ana")


def test_each_intent_reaches_the_goal():
    draft = _draft()
    decisions.switch_off_role(draft, "trimming", who="ana")
    decisions.exclude_producer(draft, SITE, STAR, who="ana")
    decisions.pin_source(draft, COUNTS, "bam", SORT, who="ana")
    constraints = decisions.goal(draft).constraints
    assert constraints.absent_roles == [RoleAbsence(role="trimming")]
    assert constraints.exclusions == [ProducerExclusion(site=SITE, contract=STAR)]
    assert constraints.sources == [SourcePin(consumer=COUNTS, port="bam", producer=SORT)]


def test_a_released_intent_leaves_the_goal_and_keeps_its_history():
    draft = _draft()
    decisions.switch_off_role(draft, "trimming", who="ana")
    decisions.release_intent(draft, "role", "trimming", who="ana")
    assert decisions.goal(draft).constraints.absent_roles == []
    assert [e["action"] for e in decisions.intent_history(draft, "role", "trimming")] == [
        "select", "retract"]


def test_each_intent_is_attributed():
    draft = _draft()
    decisions.exclude_producer(draft, SITE, STAR, who="ana")
    [entry] = decisions.intent_history(draft, "exclusion", decisions.exclusion_key(SITE, STAR))
    assert (entry["who"], entry["actor_kind"]) == ("ana", "person")
    assert entry["at"] is not None


def test_pinning_a_tool_withdraws_its_exclusion_at_that_site():
    """Review Focus 3: the later intent wins and the earlier is retracted, never both applied."""
    draft = _draft()
    decisions.exclude_producer(draft, SITE, STAR, who="ana")
    decisions.pin_producer(draft, SITE, STAR, who="ana")
    constraints = decisions.goal(draft).constraints
    assert constraints.excluded_at(SITE) == frozenset()
    assert constraints.producer_at(SITE).contract == STAR


def test_excluding_a_tool_withdraws_its_pin_at_that_site():
    draft = _draft()
    decisions.pin_producer(draft, SITE, STAR, who="ana")
    decisions.exclude_producer(draft, SITE, STAR, who="ana")
    constraints = decisions.goal(draft).constraints
    assert constraints.producer_at(SITE) is None
    assert constraints.excluded_at(SITE) == frozenset({STAR})


def test_importing_a_goal_writes_its_intents():
    from comeni_core.goal.asked import Goal

    draft = _draft()
    goal = Goal.model_validate({"constraints": {
        "absent_roles": [{"role": "trimming"}],
        "sources": [{"consumer": COUNTS, "port": "bam", "producer": SORT}]}})
    decisions.import_goal(draft, goal, who="ana")
    assert decisions.goal(draft).constraints == goal.constraints
