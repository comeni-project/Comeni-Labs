"""Intent and facts carry the person's words when they were heard, what was asked and cannot be
made is kept, and a confirmed goal is recorded rather than inferred (Part I.0 spec §6)."""

import pytest
from comeni_core.goal.asked import Site
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import authoring_decisions, decisions, drafts
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from mendel_authoring.decisions import ActorKind

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _draft() -> str:
    return drafts.create(DraftGraph(), "heard", "ana")


def _decision_revision(draft_id: str) -> int:
    with session_scope() as db:
        return db.get(PipelineDraft, draft_id).decision_revision


def test_a_heard_fact_keeps_its_quote_and_turn(clean):
    draft = _draft()
    decisions.set_fact(
        draft,
        "paired",
        True,
        who="model",
        actor_kind=ActorKind.MODEL,
        heard="paired-end",
        heard_seq=1,
    )
    assert decisions.heard_of(draft)[("fact", "paired")] == ("paired-end", 1)


def test_an_unquoted_write_has_no_words(clean):
    draft = _draft()
    decisions.set_fact(draft, "paired", True, who="ana")
    assert ("fact", "paired") not in decisions.heard_of(draft)


def test_a_want_and_its_retraction(clean):
    draft = _draft()
    decisions.set_want(draft, "counts.matrix", who="ana", heard="gene counts", heard_seq=1)
    assert [w.type_id for w in decisions.read(draft).wants if w.present] == ["counts.matrix"]
    assert decisions.heard_of(draft)[("want", "counts.matrix")] == ("gene counts", 1)
    decisions.retract_want(draft, "counts.matrix", who="ana")
    assert not [w for w in decisions.read(draft).wants if w.present]


def test_required_states_a_pin_and_a_parameter_reach_the_goal(clean):
    draft = _draft()
    decisions.set_want(draft, "counts.matrix", who="ana")
    decisions.require_states(draft, "counts.matrix", ["gene_level"], who="ana")
    decisions.pin_producer(
        draft,
        Site(type_id="alignment.bam", states=frozenset()),
        "nf-core/hisat2/align@2.2.2",
        who="ana",
    )
    decisions.set_parameter(draft, "seq_platform", "ILLUMINA", who="ana")
    goal = decisions.goal(draft)
    assert list(goal.constraints.required_states[0].states) == ["gene_level"]
    assert goal.constraints.producers[0].contract == "nf-core/hisat2/align@2.2.2"
    assert goal.constraints.params[0].value == "ILLUMINA"


def test_requiring_states_of_something_not_wanted_is_refused(clean):
    with pytest.raises(ValueError, match="MI0204"):
        decisions.require_states(_draft(), "counts.matrix", ["gene_level"], who="ana")


def test_asked_is_kept_and_never_reaches_the_goal(clean):
    draft = _draft()
    decisions.set_asked(
        draft,
        "differential expression",
        who="model",
        actor_kind=ActorKind.MODEL,
        heard="differential expression",
        heard_seq=1,
    )
    assert [a.phrase for a in decisions.read_asked(draft)] == ["differential expression"]
    assert "differential" not in decisions.goal(draft).model_dump_json()
    decisions.retract_asked(draft, "differential expression", who="ana")
    assert decisions.read_asked(draft) == []


def test_confirmation_is_recorded_not_inferred(clean):
    draft = _draft()
    decisions.set_want(draft, "counts.matrix", who="model", actor_kind=ActorKind.MODEL)
    assert not authoring_decisions.confirmed(draft)
    assert decisions.confirmed_goal(draft) is None
    decisions.confirm(draft)
    assert authoring_decisions.confirmed(draft)
    assert decisions.confirmed_goal(draft).want == ["counts.matrix"]


def test_retracting_what_was_never_recorded_changes_nothing(clean):
    """Review Focus 5."""
    draft = _draft()
    before = _decision_revision(draft)
    assert decisions.retract_want(draft, "counts.matrix", who="ana") is None
    assert decisions.retract_asked(draft, "anything", who="ana") is None
    assert _decision_revision(draft) == before


def test_deleting_a_draft_takes_what_was_asked_with_it(clean):
    """Part H's deletion covers the new family: nothing names the draft afterwards."""
    from mendel_api.services import deletion
    from sqlalchemy import text

    draft = _draft()
    decisions.set_asked(draft, "differential expression", who="ana")
    deletion.delete_draft(draft)
    with session_scope() as db:
        assert (
            db.scalar(text("SELECT count(*) FROM pipeline_asked WHERE draft_id = :d"), {"d": draft})
            == 0
        )
