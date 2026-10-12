"""Recorded, real-database scenarios and query capture for Part G."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import authoring_setup
from comeni_core import yaml_strict
from comeni_core.goal.asked import Goal, ProducerPin, Site
from comeni_core.plan.draft import DraftGraph
from mendel_api.authoring.envelopes import OfferContext
from mendel_api.db import engine, session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import drafts
from mendel_api.services import session as facade
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_authoring.amend import ChooseTool
from sqlalchemy import event
from support.paths import ROOT

HISAT2 = "nf-core/hisat2/align@2.2.2"


@dataclass(frozen=True)
class Case:
    session_id: str
    proposal_id: str
    option_id: str
    goal: Goal
    context: OfferContext


def _accepted(pacing: str, goal: Goal | None = None) -> tuple[str, Goal]:
    goal = goal or Goal.model_validate(yaml_strict.load(ROOT / "examples/rnaseq-goal.yml"))
    draft = drafts.create(DraftGraph(), "rnaseq", "ana")
    sid = facade.perform(commands.OpenSession(draft, "ana")).result
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.move(sid, st.Event.NOTHING_MISSING, row_version=2)
    authoring_setup.move(sid, st.Event.GOAL_ACCEPTED, row_version=3,
                         goal=goal.model_dump(mode="json"))
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        row.pacing, row.show_gaps = pacing, False
    return sid, goal


def placed_quietly() -> str:
    """A session whose whole walk was placed without stopping: nothing is pending. Pacing is
    read from `COMENI_BUILD_PACING`, so the caller sets it to `stop_where_needed`."""
    sid, _ = _accepted("stop_where_needed")
    authoring_setup.start_building(sid)
    assert facade.read(sid)["pending_proposal"] is None, "the quiet walk stopped"
    return sid


def with_hisat2() -> str:
    """A session whose accepted goal already pins HISAT2, walked together from its first step."""
    goal = Goal.model_validate(yaml_strict.load(ROOT / "examples/rnaseq-goal.yml"))
    pinned = ChooseTool(pin=ProducerPin(site=Site(type_id="alignment.bam"), contract=HISAT2))
    sid, _ = _accepted("together", pinned.apply(goal))
    authoring_setup.start_building(sid)
    return sid


def at_aligner(pacing: str = "together") -> Case:
    sid, goal = _accepted(pacing)
    proposal = authoring_setup.start_building(sid)
    for _ in range(20):
        picture = facade.read(sid)
        pending = picture["pending_proposal"]
        assert pending is not None, "walk ended before offering the aligner"
        if pending["payload"]["node"] == "star_align":
            options = pending["payload"]["options"]
            assert options, "aligner offered no options"
            option = next(k for k, value in options.items() if value == HISAT2)
            with session_scope() as db:
                digest = db.get(PipelineAuthoringSession, sid).registry_digest
            return Case(sid, proposal, option, goal, OfferContext(
                draft_revision=picture["revision"], decision_revision=picture["decision_revision"],
                session_version=picture["row_version"], registry=digest))
        proposal = facade.perform(
            commands.SettleStep(proposal, picture["revision"], "ana")
        ).result.next_proposal
    raise AssertionError("walk did not reach the aligner within 20 proposals")


@contextmanager
def captured_sql() -> Iterator[list[str]]:
    statements: list[str] = []

    def record(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)
