"""The goal and its factual history read the same selected revisions."""

from importlib import import_module

import pytest
from comeni_core.goal.asked import Goal
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope, transaction
from mendel_api.models import PipelineDraft
from mendel_api.services import drafts
from mendel_postgres import reachable

pytestmark = pytest.mark.skipif(not reachable(), reason="needs throwaway Postgres")


def _service():
    return import_module("mendel_api.services.decisions")


def test_corrected_fact_is_the_current_goal_and_has_both_values_in_history():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.import_goal(draft, Goal.model_validate({"profile": {"read_length": 150}}), who="ana")
    service.set_fact(draft, "read_length", 100, who="ana")
    assert service.goal(draft).profile.get("read_length") == 100
    history = service.history(draft, "read_length")
    assert [entry["value"] for entry in history if entry["selected"]] == [150, 100]
    assert history[-1]["origin"] == "person_said"


def test_unused_measurement_is_visible_without_replacing_a_told_fact():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    observed = service.observe(draft, "read_length", 100, origin="measured")
    assert service.goal(draft).profile.get("read_length") == 150
    [unused] = [entry for entry in service.history(draft, "read_length") if not entry["selected"]]
    assert unused["value"] == 100 and unused["observation_id"] == observed
    service.select_observation(draft, "read_length", observed, who="ana")
    [fact] = service.goal(draft).profile.measurements
    assert fact.value == 100 and fact.source.value == "measured"


def test_retraction_removes_current_value_without_erasing_history():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    service.set_fact(draft, "read_length", None, who="ana")
    assert service.goal(draft).profile.get("read_length") is None
    assert [entry["value"] for entry in service.history(draft, "read_length")
            if entry["selected"]] == [150, None]


def test_bad_correction_and_transaction_failure_leave_goal_and_history_unchanged():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    with pytest.raises(ValueError):
        service.set_fact(draft, "read_length", "nonsense", who="ana")
    with pytest.raises(RuntimeError), transaction():
        service.set_fact(draft, "read_length", 100, who="ana")
        raise RuntimeError("late failure")
    assert service.goal(draft).profile.get("read_length") == 150
    assert len([e for e in service.history(draft, "read_length") if e["selected"]]) == 1


def test_one_action_changes_the_decision_revision_once_and_stale_answer_is_refused():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    with transaction():
        service.set_fact(draft, "read_length", 150, who="ana")
        service.set_fact(draft, "paired", True, who="ana")
    with session_scope() as db:
        assert db.get(PipelineDraft, draft).decision_revision == 1
    with pytest.raises(ValueError, match="MI0201"):
        service.set_fact(draft, "read_length", 100, who="ana", expected_revision=0)
    assert service.goal(draft).profile.get("read_length") == 150


def test_a_draft_cannot_select_another_drafts_ungranted_evidence():
    service = _service()
    first = drafts.create(DraftGraph(), "one", "ana")
    second = drafts.create(DraftGraph(), "two", "ana")
    observation = service.observe(first, "read_length", 100, origin="measured")
    with pytest.raises(ValueError, match="evidence"):
        service.select_observation(second, "read_length", observation, who="ana")
    assert service.goal(second).profile.measurements == []


def test_keeping_current_value_records_an_answer_without_changing_goal_revision():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    service.retain_fact(draft, "read_length", who="ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    with session_scope() as db:
        assert db.get(PipelineDraft, draft).decision_revision == 1
    history = service.history(draft, "read_length")
    assert [e["action"] for e in history] == ["select", "retain", "retain"]
    assert [e["current"] for e in history] == [False, False, True]


def test_unknown_can_be_explicitly_replaced_by_sample_evidence():
    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", None, who="ana")
    observed = service.observe(draft, "read_length", 100)
    assert service.assess_observation(draft, observed).value == "unknown"
    service.select_observation(draft, "read_length", observed, who="ana")
    assert service.goal(draft).profile.get("read_length") == 100
    disagreeing = service.observe(draft, "read_length", 150)
    assert service.assess_observation(draft, disagreeing).value == "disagreement"
    agreeing = service.observe(draft, "read_length", 100)
    assert service.assess_observation(draft, agreeing).value == "agreement"


def test_concurrent_answers_with_the_same_revision_cannot_overwrite_each_other():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    service = _service()
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    gate = Barrier(2)

    def answer(value):
        gate.wait(timeout=5)
        try:
            service.set_fact(draft, "read_length", value, who="ana", expected_revision=1)
            return "selected"
        except ValueError as exc:
            assert "MI0201" in str(exc)
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(answer, [100, 200]))
    assert sorted(results) == ["selected", "stale"]
    assert len(service.history(draft, "read_length")) == 2


def test_releasing_choices_and_withdrawing_input_changes_composed_goal():
    service = _service()
    draft = drafts.create(DraftGraph(), "choices", "ana")
    goal = Goal.model_validate({
        "have": [{"type_id": "reads.fastq", "name": "reads"}],
        "want": ["reads.fastq"],
        "constraints": {"params": [{"name": "threads", "value": 4}],
                        "producers": [{"site": {"type_id": "reads.fastq"},
                                       "contract": "lab/trim@1.0.0"}]},
    })
    service.import_goal(draft, goal, who="ana")
    service.withdraw_input(draft, "reads", who="ana")
    service.release_parameter(draft, "threads", who="ana")
    service.release_producer(draft, goal.constraints.producers[0].site, who="ana")
    current = service.goal(draft)
    assert not current.have and not current.constraints.params and not current.constraints.producers
    service.import_goal(draft, goal, who="ana")
    assert service.goal(draft) == goal


def test_history_is_ordered_by_sequence_even_when_operation_times_are_equal(monkeypatch):
    from datetime import UTC, datetime

    service = _service()

    class FixedClock:
        @staticmethod
        def now(_tz):
            return datetime(2026, 10, 11, tzinfo=UTC)

    monkeypatch.setattr(service, "datetime", FixedClock)
    draft = drafts.create(DraftGraph(), "facts", "ana")
    service.set_fact(draft, "read_length", 150, who="ana")
    service.observe(draft, "read_length", 100)
    service.set_fact(draft, "read_length", None, who="ana")
    history = service.history(draft, "read_length")
    assert [e["value"] for e in history] == [150, 100, None]
    assert len({e["at"] for e in history}) == 1


def test_reordering_selected_inputs_updates_goal_and_decision_revision():
    service = _service()
    draft = drafts.create(DraftGraph(), "order", "ana")
    first = Goal.model_validate({"have": [{"type_id": "reads.fastq", "name": "a"},
                                        {"type_id": "reads.fastq", "name": "b"}]})
    service.import_goal(draft, first, who="ana")
    second = first.model_copy(update={"have": list(reversed(first.have))})
    service.import_goal(draft, second, who="ana")
    assert service.goal(draft) == second
    with session_scope() as db:
        assert db.get(PipelineDraft, draft).decision_revision == 2


def test_gathering_records_selected_inputs_and_uses_a_corrected_row_value():
    from mendel_api.services import session
    from mendel_api.stages import gathering
    from mendel_authoring import commands as c

    service = _service()
    sid = session.perform(c.Begin("counts", "ana")).result[0]
    session.perform(c.Understood(sid, {"want": ["counts.matrix"]}))
    offered = session.read(sid)["pending_proposal"]
    subject = offered["payload"]["subject"]
    session.perform(c.AnswerGap(offered["id"], "have_it", None, "ana"))
    draft = session.read(sid)["draft_id"]
    assert any(i.type_id == subject for i in service.read(draft).inputs)
    service.set_fact(draft, "read_length", 100, who="ana")
    assert gathering.compose_goal(sid).profile.get("read_length") == 100
    current = next(f for f in session.read(sid)["facts"] if f["subject"] == "read_length")
    assert current["value"] == 100


def test_model_extraction_stays_separate_from_accepted_goal_and_fact_rows():
    from mendel_api.models import PipelineAuthoringSession
    from mendel_api.services import session
    from mendel_authoring import commands as c

    service = _service()
    sid = session.perform(c.Begin("counts from paired reads", "ana")).result[0]
    session.perform(c.Understood(sid, {"want": ["counts.matrix"], "stated": [
        {"kind": "measurement", "subject": "paired", "value": True}]}))
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        assert row.extraction["stated"][0]["value"] is True
        assert row.goal is None
    assert not service.read(session.read(sid)["draft_id"]).facts
