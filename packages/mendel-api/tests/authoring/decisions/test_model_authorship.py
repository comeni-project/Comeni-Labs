"""The builder agent's decisions reach the goal as the AI's, with its reason (#463)."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.services import changes, decisions, drafts
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_authoring.payloads import DecisionChange

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

HISAT2 = "nf-core/hisat2/align@2.2.2"


def _draft() -> str:
    return drafts.create(DraftGraph(), "authorship", "ana")


def test_the_decision_records_actor_reaches_the_goal(clean):
    draft = _draft()
    changes.apply(draft, DecisionChange(kind="pin", subject="alignment.bam", value=HISAT2,
                                        actor="model", because="less memory"),
                  who="builder-agent")
    [pin] = decisions.goal(draft).constraints.producers
    assert (pin.contract, pin.by, pin.because) == (HISAT2, "model", "less memory")


def test_a_model_setting_reaches_the_goal_as_the_ais(clean):
    draft = _draft()
    changes.apply(draft, DecisionChange(kind="parameter", subject="sa_index_nbases", value=12,
                                        actor="model", because="a smaller index"),
                  who="builder-agent")
    [override] = decisions.goal(draft).constraints.params
    assert (override.value, override.by, override.because) == (12, "model", "a smaller index")


def test_a_persons_choice_stays_the_persons(clean):
    draft = _draft()
    changes.apply(draft, DecisionChange(kind="pin", subject="alignment.bam", value=HISAT2),
                  who="ana")
    [pin] = decisions.goal(draft).constraints.producers
    assert (pin.by, pin.because) == ("person", "")
