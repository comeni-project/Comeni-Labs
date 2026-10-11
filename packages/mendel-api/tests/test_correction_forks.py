"""A corrected authored fork preserves manual work and references its original evidence."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft, PipelineObservation
from mendel_api.services import decisions, drafts, session
from mendel_authoring import commands as c
from sqlalchemy import func, select
from test_authoring_building import _answer_all, _resolving, authoring_setup
from test_authoring_building import clean as clean
from test_fact_corrections import _correct


def _manual():
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    graph = DraftGraph.model_validate(session.read(sid)["graph"])
    removed = graph.nodes[-1].id
    graph = graph.model_copy(
        update={
            "nodes": graph.nodes[:-1],
            "edges": [e for e in graph.edges if e.from_node != removed and e.to_node != removed],
        }
    )
    session.perform(c.RecordEdit(sid, graph.model_dump(mode="json"), "ana"))
    return sid


def _command(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        return c.ForkCorrection(
            sid, "read_length", 50, "ana", draft.decision_revision, draft.revision, row.row_version
        )


def test_correcting_manual_work_returns_a_linked_new_authored_walk_and_preserves_original(clean):
    sid = _manual()
    before = session.read(sid)
    with session_scope() as db:
        parent = db.get(PipelineDraft, before["draft_id"])
        assert parent.ownership == "manual"
        history = decisions.history(parent.id, "read_length")
    changed = _correct(sid, "read_length", 50)
    assert changed["session_id"] != sid and changed["draft_id"] != before["draft_id"]
    assert changed["phase"] == "building"
    assert session.read(sid) == before
    assert decisions.history(before["draft_id"], "read_length") == history
    with session_scope() as db:
        child = db.get(PipelineDraft, changed["draft_id"])
        assert child.forked_from == before["draft_id"] and child.ownership == "authored"
        assert (
            next(f.value for f in decisions.read(child.id).facts if f.subject == "read_length")
            == 50
        )
    assert any(
        "manual" in b.get("summary", "").lower()
        for t in session.read(changed["session_id"])["turns"]
        for b in t["blocks"]
    )


def test_a_double_fork_delivery_returns_the_same_child_without_more_rows(clean):
    sid = _manual()
    command = _command(sid)
    first = session.perform(command).result
    second = session.perform(command).result
    assert second["session_id"] == first["session_id"]
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(PipelineDraft)) == 2


def test_fork_inherits_evidence_access_and_original_attribution_without_copying_observations(clean):
    from mendel_api.models import PipelineEvidenceAccess, PipelineFact, PipelineFactRevision

    sid = _manual()
    with session_scope() as db:
        parent_id = db.get(PipelineAuthoringSession, sid).draft_id
        count = db.scalar(select(func.count()).select_from(PipelineObservation))
        parent_revision = db.scalar(
            select(PipelineFactRevision)
            .join(PipelineFact, PipelineFact.current_id == PipelineFactRevision.id)
            .where(PipelineFact.draft_id == parent_id, PipelineFact.subject_key == "paired")
        )
        observed_id = parent_revision.observation_id
    changed = _correct(sid, "read_length", 50)
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(PipelineObservation)) == count + 1
        assert db.get(PipelineEvidenceAccess, (changed["draft_id"], observed_id)).inherited
        revision = db.scalar(
            select(PipelineFactRevision)
            .join(PipelineFact, PipelineFact.current_id == PipelineFactRevision.id)
            .where(
                PipelineFact.draft_id == changed["draft_id"], PipelineFact.subject_key == "paired"
            )
        )
        assert (
            revision.actor_kind == parent_revision.actor_kind
            and revision.who == parent_revision.who
        )
        assert revision.observation_id == observed_id and revision.action == "inherit"
    history = decisions.history(changed["draft_id"], "read_length")
    assert any(h["value"] == 150 and h.get("inherited") for h in history)


def test_unexpected_failure_creates_neither_draft_nor_evidence(clean, monkeypatch):
    from mendel_api.services import blueprint

    sid = _manual()
    before = session.read(sid)
    with session_scope() as db:
        count = db.scalar(select(func.count()).select_from(PipelineObservation))

    def crash(*args, **kw):
        raise RuntimeError("failed fork")

    monkeypatch.setattr(blueprint, "resolve", crash)
    with pytest.raises(RuntimeError, match="failed fork"):
        _correct(sid, "read_length", 50)
    assert session.read(sid) == before
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(PipelineDraft)) == 1
        assert db.scalar(select(func.count()).select_from(PipelineObservation)) == count


def test_an_honest_unbuildable_fork_keeps_truth_and_leaves_original_unchanged(clean, monkeypatch):
    from mendel_api.services import blueprint
    from mendel_resolver.router import UnroutableError

    sid = _manual()
    before = session.read(sid)

    def blocked(*args, **kw):
        raise UnroutableError("needs something not here")

    monkeypatch.setattr(blueprint, "resolve", blocked)
    changed = _correct(sid, "read_length", 50)
    assert changed["phase"] == "stopped" and not changed["projection_current"]
    assert session.read(sid) == before


def test_rename_only_does_not_fork_an_authored_pipeline(clean):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    view = session.read(sid)
    drafts.update(view["draft_id"], DraftGraph.model_validate(view["graph"]), name="Renamed")
    changed = _correct(sid, "read_length", 50)
    assert changed["session_id"] == sid


def test_parent_history_added_after_the_fork_is_not_visible_in_child(clean):
    sid = _manual()
    before = session.read(sid)
    changed = _correct(sid, "read_length", 50)
    history = decisions.history(changed["draft_id"], "read_length")
    decisions.set_fact(before["draft_id"], "read_length", 75, who="later")
    assert decisions.history(changed["draft_id"], "read_length") == history


@pytest.mark.parametrize("option", ["keep_current", "use_measurement", "correct", "unknown"])
def test_a_manual_disagreement_forks_without_settling_the_parent_question(clean, option):
    from test_fact_disagreements import _answer, _conflict

    sid = _conflict()
    with session_scope() as db:
        db.get(PipelineDraft, session.read(sid)["draft_id"]).ownership = "manual"
    before = session.read(sid)
    changed = _answer(sid, option, False if option == "correct" else None)
    assert changed["session_id"] != sid
    assert session.read(sid) == before
    assert session.read(changed["session_id"])["pending_proposal"]["kind"] != "disagreement"


def test_inherited_evidence_cannot_be_selected_by_an_unrelated_draft(clean):
    from comeni_core.plan.draft import DraftGraph
    from mendel_api.models import PipelineEvidenceAccess

    sid = _manual()
    changed = _correct(sid, "read_length", 50)
    with session_scope() as db:
        observed = db.scalar(
            select(PipelineEvidenceAccess.observation_id).where(
                PipelineEvidenceAccess.draft_id == changed["draft_id"]
            )
        )
    unrelated = drafts.create(DraftGraph(), "Other", "ana")
    with pytest.raises(ValueError, match="access"):
        decisions.select_observation(unrelated, "paired", observed, who="ana")
