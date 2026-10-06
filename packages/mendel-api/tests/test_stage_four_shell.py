"""Stage ④ through the facade, against the real registry and a real database (spec §13.4).

The pure flow is `packages/mendel-authoring/tests/test_stage_four.py`; this file is the work each
node does with rows: the fact asked once, a choice from the rule's own tools, the pacing honoured,
a registry gap shown or routed around, and the wrap-up at the end.
"""

from pathlib import Path

import authoring_setup
import pytest
from comeni_core import yaml_strict
from comeni_core.plan.draft import DraftGraph
from mendel_api.authoring.types import Phase, ProposalState
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import drafts
from mendel_api.services import session as facade
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_authoring.protocol import PROTOCOL
from mendel_resolver.goal import Goal
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
STAR = "nf-core/star/align@1.11.0"


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def clean():
    """Every table these rows touch, in one statement — `test_authoring_building.py`'s list:
    `forge_message` references `ai_invocation`, and each foreign key here is `RESTRICT`."""
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
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


def _pending(session_id: str) -> dict:
    return facade.read(session_id)["pending_proposal"]


def _accept(session_id: str, option: str | None = None) -> None:
    pending = _pending(session_id)
    revision = facade.read(session_id)["revision"]
    facade.perform(
        commands.SettleStep(pending["id"], ProposalState.ACCEPTED.value, revision, "ana", option)
    )


def _walk_to(session_id: str, kind: str) -> dict:
    """Accept every step card until a proposal of `kind` is pending."""
    for _ in range(50):
        pending = _pending(session_id)
        assert pending is not None, "the walk ended before reaching a " + kind
        if pending["kind"] == kind:
            return pending
        _accept(session_id)
    raise AssertionError("the walk never reached a " + kind)


def _node(proposal_id: str) -> str | None:
    with session_scope() as db:
        return (db.get(PipelineAuthoringProposal, proposal_id).payload or {}).get("node")


# ── the fact first ──────────────────────────────────────────────────────────────────────────


def test_without_a_read_length_the_walk_stops_on_the_fact(clean):
    session_id = _built(_goal(read_length=False))
    fact = _walk_to(session_id, "gap")
    assert fact["payload"]["subject"] == "read_length"
    assert "upload" not in fact["payload"]["options"], "a sample is gathering's, not stage ④'s"
    assert "not_sure" in fact["payload"]["options"]
    assert facade.read(session_id)["phase"] == Phase.BUILDING.value


def test_answering_the_fact_places_the_aligner_at_tier_three(clean):
    session_id = _built(_goal(read_length=False))
    fact = _walk_to(session_id, "gap")
    facade.perform(commands.AnswerGap(fact["id"], "value", 150, "ana"))
    card = _pending(session_id)
    assert card["kind"] == "step" and _node(card["id"]) == "star_align"
    assert card["payload"]["block"]["tier"] == 3
    assert any(
        "read_length is 150" in line["text"] for line in card["payload"]["block"]["brief"]["check"]
    )


def test_a_fact_answered_not_sure_becomes_a_choice_and_is_never_asked_again(clean):
    """Review Focus 2."""
    session_id = _built(_goal(read_length=False))
    fact = _walk_to(session_id, "gap")
    facade.perform(commands.AnswerGap(fact["id"], "not_sure", None, "ana"))
    card = _pending(session_id)
    assert card["kind"] == "step" and _node(card["id"]) == "star_align"
    assert card["payload"]["block"]["alternatives"], "a choice offers the rule's other tool"
    _accept(session_id)
    assert all(p["kind"] != "gap" for p in [_pending(session_id) or {"kind": ""}])


# ── pacing ──────────────────────────────────────────────────────────────────────────────────


def test_together_rests_at_every_step(clean):
    session_id = _built(_goal())
    assert _pending(session_id)["kind"] == "step"
    first = _pending(session_id)["id"]
    _accept(session_id)
    assert _pending(session_id)["id"] != first and _pending(session_id)["kind"] == "step"


def test_stop_where_needed_with_a_read_length_reaches_the_wrap_up(clean, monkeypatch):
    """Review Focus 3, the handler's half: every quiet step placed in one entry of `step`."""
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    session_id = _built(_goal())
    view = facade.read(session_id)
    assert view["phase"] == Phase.COMPLETE.value
    assert view["pending_proposal"] is None
    last = view["turns"][-1]["blocks"][0]
    assert last["kind"] == "receipt" and "You'll get: counts.matrix" in last["summary"]
    assert {n["id"] for n in view["graph"]["nodes"]} >= {"star_align", "subread_featurecounts"}


def test_ask_puts_the_pacing_question_and_the_answer_walks_on(clean, monkeypatch):
    monkeypatch.delenv("COMENI_BUILD_PACING", raising=False)
    session_id = _built(_goal())
    question = _pending(session_id)
    assert question["kind"] == "pacing"
    facade.perform(commands.ChoosePacing(question["id"], "stop_where_needed", "ana"))
    assert facade.read(session_id)["phase"] == Phase.COMPLETE.value


def test_an_env_pinned_pacing_wins_over_the_stored_one(monkeypatch, settings_in_memory):
    """Review Focus 4: the snapshot is the settings resolver's, never the raw stored row."""
    settings_in_memory.rows["building.pacing"] = "ask"
    monkeypatch.setenv("COMENI_BUILD_PACING", "together")
    assert facade.snapshot(PROTOCOL).settings["building.pacing"] == "together"
    monkeypatch.delenv("COMENI_BUILD_PACING")
    assert facade.snapshot(PROTOCOL).settings["building.pacing"] == "ask"


# ── registry gaps and Dev mode ─────────────────────────────────────────────────────────────


def test_dev_mode_on_stops_on_the_gap_and_names_the_file(clean, monkeypatch):
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    monkeypatch.setenv("COMENI_DEV_MODE", "true")
    session_id = _built(_goal())
    card = _pending(session_id)
    assert card is not None and card["kind"] == "step"
    gaps = card["payload"]["block"]["gaps"]
    assert gaps and all(g["fix"].startswith("registry/tools/") for g in gaps)


def test_dev_mode_off_routes_around_every_gap(clean, monkeypatch):
    monkeypatch.setenv("COMENI_BUILD_PACING", "stop_where_needed")
    monkeypatch.setenv("COMENI_DEV_MODE", "false")
    session_id = _built(_goal())
    assert facade.read(session_id)["phase"] == Phase.COMPLETE.value
