"""Reusable step review scenarios and fixtures for API tests."""

import pytest
from comeni_core import yaml_strict
from comeni_core.plan.draft import DraftGraph
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import drafts
from mendel_api.services import session as facade
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_resolver.goal import Goal
from support.paths import ROOT as REPOSITORY_ROOT

from mendel_api_tests import session_setup as authoring_setup
from mendel_api_tests.database import truncate

ROOT = REPOSITORY_ROOT


@pytest.fixture
def clean():
    """Every table these rows touch, in one statement — `test_authoring_building.py`'s list:
    `forge_message` references `ai_invocation`, and each foreign key here is `RESTRICT`."""
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft, gate_run"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


def _goal(*, read_length: bool = True) -> Goal:
    data = yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml")
    if not read_length:
        data["profile"].pop("read_length")
    return Goal.model_validate(data)


def _built(goal: Goal) -> str:
    """A session confirmed on `goal`, its build started (`resolve` → the walk's first stop)."""
    draft_id = drafts.create(DraftGraph(), "rnaseq", "ana")
    session_id = facade.perform(commands.OpenSession(draft_id, "ana")).result
    authoring_setup.move(session_id, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.move(session_id, st.Event.NOTHING_MISSING, row_version=2)
    authoring_setup.move(
        session_id, st.Event.GOAL_ACCEPTED, row_version=3, goal=goal.model_dump(mode="json")
    )
    authoring_setup.start_building(session_id)
    return session_id


def _pending(session_id: str) -> dict | None:
    return facade.read(session_id)["pending_proposal"]


def _pending_node(session_id: str) -> str | None:
    pending = _pending(session_id)
    return pending["payload"]["node"] if pending and pending["kind"] == "step" else None


def _continue(session_id: str) -> None:
    pending = _pending(session_id)
    facade.perform(commands.SettleStep(pending["id"], facade.read(session_id)["revision"], "ana"))


def _amend(session_id: str, option: str, value=None, *, proposal_id: str | None = None) -> None:
    proposal_id = proposal_id or _pending(session_id)["id"]
    facade.perform(commands.Amend(proposal_id, option, value, "ana"))


def _walk_to_node(session_id: str, node: str) -> dict:
    """Continue every card until the one for `node` is pending."""
    for _ in range(50):
        if _pending_node(session_id) == node:
            return _pending(session_id)
        assert _pending(session_id) is not None, f"the walk ended before reaching {node}"
        _continue(session_id)
    raise AssertionError(f"the walk never reached {node}")


def _walk_to_wrap(session_id: str) -> str:
    """Continue every card to the wrap-up; return the wrap-up's receipt."""
    for _ in range(50):
        view = facade.read(session_id)
        if view["phase"] == Phase.COMPLETE.value:
            return next(
                b["summary"]
                for t in reversed(view["turns"])
                for b in t["blocks"]
                if b["kind"] == "receipt" and b["id"].startswith("wrap-")
            )
        _continue(session_id)
    raise AssertionError("the walk never reached the wrap-up")


def _graph(session_id: str) -> dict:
    return facade.read(session_id)["graph"]


def _ids(session_id: str) -> set[str]:
    return {n["id"] for n in _graph(session_id)["nodes"]}


def _draft(session_id: str) -> PipelineDraft:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        db.expunge(draft)
        return draft


def _no_orphan(session_id: str) -> None:
    graph = _graph(session_id)
    ids = {n["id"] for n in graph["nodes"]}
    assert all(e["from_node"] in ids and e["to_node"] in ids for e in graph["edges"])


def _hisat2(card: dict) -> dict:
    return next(a for a in card["payload"]["block"]["alternatives"] if "hisat2" in a["label"])


# ── the final review of Run 2 ─────────────────────────────────────────────────────────────
def _unbuildable_at(monkeypatch, read_length: int) -> None:
    """The resolver finds no way to build a goal whose read length is `read_length`."""
    from mendel_api.services import blueprint as bp
    from mendel_resolver.router import UnroutableError

    real = bp.resolve

    def resolve(goal, **kw):
        told = {m.measurement: m.value for m in goal.profile.measurements}
        if told.get("read_length") == read_length:
            raise UnroutableError("no index", missing=("genome.index.hisat2", frozenset()))
        return real(goal, **kw)

    monkeypatch.setattr(bp, "resolve", resolve)
