"""Truthful corrections commit independently of routing; unrelated failures roll back."""

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import decisions, drafts, session
from mendel_authoring import commands as c
from mendel_authoring.types import Phase
from test_authoring_building import (  # noqa: F401
    _answer_all,
    _draft,
    _phase,
    _proposal,
    _resolving,
    authoring_setup,
)
from test_authoring_building import clean as clean


def _correct(sid, subject, value, *, kind="measurement"):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        command = c.CorrectFact(
            sid,
            subject,
            value,
            "ana",
            draft.decision_revision,
            draft.revision,
            row.row_version,
            kind,
        )
    return session.perform(command).result


def test_correction_changes_current_value_and_reoffers_affected_reviews(clean):
    sid = _resolving()
    first = authoring_setup.start_building(sid)
    _answer_all(sid, first)
    result = _correct(sid, "read_length", 50)
    assert result["phase"] == "building"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        current = decisions.read(row.draft_id)
        assert next(f.value for f in current.facts if f.subject == "read_length") == 50
        assert _proposal(result["next_proposal"]).payload["node"] == "hisat2_build"
        assert db.get(PipelineDraft, row.draft_id).projection_current
    assert any(
        "Your correction" in b.get("summary", "")
        for t in session.read(sid)["turns"]
        for b in t["blocks"]
    )


def test_withdrawing_essential_input_keeps_truth_and_stales_projection_until_restored(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    result = _correct(sid, "genome.fasta", False, kind="input")
    assert result["phase"] == "stopped"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        assert not any(
            i.present for i in decisions.read(row.draft_id).inputs if i.type_id == "genome.fasta"
        )
        assert not db.get(PipelineDraft, row.draft_id).projection_current
        draft_id = row.draft_id
    with pytest.raises(ValueError, match="MI0201"):
        drafts.keep(draft_id)
    assert drafts.preview(draft_id).state == "outdated"
    result = _correct(sid, "genome.fasta", True, kind="input")
    assert result["phase"] == "complete"


def test_unknown_retracts_active_measurement_and_requires_review(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    result = _correct(sid, "read_length", None)
    assert result["phase"] == "building"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        fact = next(f for f in decisions.read(row.draft_id).facts if f.subject == "read_length")
        assert fact.value is None and fact.origin == "open"
        assert len(decisions.history(row.draft_id, "read_length")) >= 2


def test_unexpected_resolver_failure_rolls_back_selection_and_workflow(clean, monkeypatch):
    from mendel_api.services import blueprint

    sid = _resolving()
    authoring_setup.start_building(sid)
    before = session.read(sid)
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, sid).draft_id
    history = decisions.history(draft_id, "read_length")

    def crash(*args, **kw):
        raise RuntimeError("resolver crashed")

    monkeypatch.setattr(blueprint, "resolve", crash)
    with pytest.raises(RuntimeError, match="resolver crashed"):
        _correct(sid, "read_length", 50)
    assert decisions.history(draft_id, "read_length") == history
    assert session.read(sid) == before


def test_a_stale_correction_does_not_append_history(clean):
    sid = _resolving()
    authoring_setup.start_building(sid)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        stale = c.CorrectFact(
            sid, "read_length", 50, "ana", draft.decision_revision, draft.revision, row.row_version
        )
    _correct(sid, "read_length", 100)
    with pytest.raises(ValueError, match="MI0201"):
        session.perform(stale)


def test_before_confirmation_a_correction_updates_the_goal_card(clean):
    from test_authoring_gathering import _gathering

    sid = _gathering(["counts.matrix"])
    result = _correct(sid, "read_length", 50)
    assert result["phase"] in ("gathering", "goal_review")
    assert _phase(sid) is not Phase.BUILDING


def test_http_correction_requires_versions_and_returns_current_authority(clean):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    sid = _resolving()
    authoring_setup.start_building(sid)
    client = TestClient(create_app())
    url = f"/api/pipeline/authoring/{sid}/facts/read_length"
    assert client.post(url, json={"value": 50}).status_code == 422
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        versions = {
            "expected_decision_revision": draft.decision_revision,
            "expected_draft_revision": draft.revision,
            "expected_session_version": row.row_version,
        }
    answer = client.post(url, json={"value": 50, **versions})
    assert answer.status_code == 200, answer.text
    assert answer.json()["projection_current"]


@pytest.mark.parametrize("completed", [False, True])
def test_one_correction_stamps_each_counter_once_and_offers_the_final_versions(clean, completed):
    sid = _resolving()
    first = authoring_setup.start_building(sid)
    if completed:
        _answer_all(sid, first)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        before = (row.row_version, draft.revision, draft.decision_revision)
    changed = _correct(sid, "read_length", 50)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        assert (row.row_version, draft.revision, draft.decision_revision) == tuple(
            v + 1 for v in before
        )
        context = _proposal(changed["next_proposal"]).payload["context"]
        assert context["session_version"] == row.row_version
        assert context["draft_revision"] == draft.revision
        assert context["decision_revision"] == draft.decision_revision


def test_goal_review_correction_replaces_the_card_without_confirming_the_goal(clean):
    from test_authoring_gathering import _gathering, _to_card

    sid = _gathering(["counts.matrix"])
    old = _to_card(sid)
    changed = _correct(sid, "read_length", 50)
    assert changed["phase"] == "goal_review"
    assert changed["next_proposal"] != old
    offered = _proposal(changed["next_proposal"]).payload["goal"]
    assert any(
        m["measurement"] == "read_length" and m["value"] == 50
        for m in offered["profile"]["measurements"]
    )
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        assert decisions.confirmed_goal(row.draft_id) is None


def test_an_unreachable_pin_keeps_the_fact_and_can_be_released_explicitly(clean, monkeypatch):
    from comeni_core.goal.asked import ProducerPin
    from mendel_api.services import blueprint
    from mendel_resolver.router import UnroutablePinError
    from test_authoring_building import _goal

    goal = _goal()
    before, _ = blueprint.resolve(goal)
    site = before.sites["star_align"]
    pin = ProducerPin(site=site, contract=before.step("star_align").module.contract_id)
    goal = goal.model_copy(
        update={"constraints": goal.constraints.model_copy(update={"producers": [pin]})}
    )
    sid = _resolving(goal)
    _answer_all(sid, authoring_setup.start_building(sid))
    real = blueprint.resolve

    def resolve(goal, **kw):
        if goal.constraints.producers and any(
            m.measurement == "read_length" and m.value == 50 for m in goal.profile.measurements
        ):
            raise UnroutablePinError("the chosen index is unreachable")
        return real(goal, **kw)

    monkeypatch.setattr(blueprint, "resolve", resolve)
    assert _correct(sid, "read_length", 50)["phase"] == "stopped"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        release = c.ReleaseProducer(
            sid,
            site.type_id,
            tuple(site.states),
            "ana",
            draft.decision_revision,
            draft.revision,
            row.row_version,
        )
    changed = session.perform(release).result
    assert changed["phase"] == "building"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        assert not decisions.goal(row.draft_id).constraints.producers
        assert (
            next(f.value for f in decisions.read(row.draft_id).facts if f.subject == "read_length")
            == 50
        )


def test_a_missing_requirement_is_asked_by_its_exact_type_and_states(clean, monkeypatch):
    from mendel_api.services import blueprint
    from mendel_resolver.router import UnroutableError

    sid = _resolving()
    authoring_setup.start_building(sid)

    def blocked(goal, **kw):
        raise UnroutableError(
            "no index", missing=("alignment.bam", frozenset({"coordinate_sorted"}))
        )

    monkeypatch.setattr(blueprint, "resolve", blocked)
    changed = _correct(sid, "read_length", 50)
    pending = _proposal(changed["next_proposal"])
    assert changed["phase"] == "gathering"
    assert pending.payload["subject"] == "alignment.bam"
    assert pending.payload["states"] == ["coordinate_sorted"]
    # Part I.1 review: a correction's question explains itself like gathering's.
    assert pending.payload["explain"]["name"] == "aligned reads (BAM)"
    assert (
        next(
            m["value"]
            for m in session.read(sid)["goal"]["profile"]["measurements"]
            if m["measurement"] == "read_length"
        )
        == 50
    )


def test_speculative_impossible_tool_swap_still_changes_nothing(clean, monkeypatch):
    from mendel_api.services import blueprint
    from mendel_resolver.router import UnroutableError
    from test_stage_four_shell import _built, _goal, _hisat2, _walk_to_node

    sid = _built(_goal())
    card = _walk_to_node(sid, "star_align")
    alternative = _hisat2(card)["id"]
    before = session.read(sid)

    def blocked(goal, **kw):
        raise UnroutableError("cannot build this tool")

    monkeypatch.setattr(blueprint, "resolve", blocked)
    with pytest.raises(ValueError, match="MI0207"):
        session.perform(c.Amend(card["id"], alternative, None, "ana"))
    assert session.read(sid) == before


def test_settings_only_correction_receipt_explains_change_with_same_tools(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    with session_scope() as db:
        before = db.get(PipelineAuthoringSession, sid).blueprint
    _correct(sid, "read_length", 100)
    with session_scope() as db:
        after = db.get(PipelineAuthoringSession, sid).blueprint
    assert [s["module"] for s in before["pipeline"]["steps"]] == [
        s["module"] for s in after["pipeline"]["steps"]
    ]
    receipts = [
        b["summary"]
        for t in session.read(sid)["turns"]
        for b in t["blocks"]
        if b["kind"] == "receipt" and b["id"].startswith("correction-")
    ]
    assert "updates" in receipts[-1]
