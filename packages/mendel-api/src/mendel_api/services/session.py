"""Where an authoring session rests, and the one place it moves (14.7.8.1).

**The diagram is the program.** A session sits on a node of `mendel_authoring.protocol.PROTOCOL`
(`at`); a command is an arrow out of it; entering an acting node runs its handler
(`mendel_api.stages`), whose outcome names the arrow on. Nothing else in the shell writes `at`
or the phase: the phase is read off the node the session reaches.
"""

from sqlalchemy import select

from mendel_api.authoring.types import Phase, ProposalState, TurnState
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
)

_BY_PHASE = {
    Phase.UNDERSTANDING: "say",
    Phase.GATHERING: "list_needs",
    Phase.GOAL_REVIEW: "card",
    Phase.RESOLVING: "resolve",
    Phase.BUILDING: "offer",
    Phase.COMPLETE: "done",
    Phase.FAILED: "failed",
    Phase.STOPPED: "stopped",
}
"""The node a row from before `at` rests on, when nothing pending says more (ruling 4)."""

_BY_TIER = {1: "step_settled", 2: "step_settled", 3: "step_rule", 4: "step_choice"}


def rests_at(db, row: PipelineAuthoringSession) -> str:
    """The node `row` rests on: stored, or derived from its phase and what is pending."""
    if row.at is not None:
        return row.at
    phase = Phase(row.phase)
    if phase is Phase.UNDERSTANDING:
        turn = db.scalar(
            select(PipelineAuthoringTurn.seq).where(
                PipelineAuthoringTurn.session_id == row.id,
                PipelineAuthoringTurn.role == "assistant",
                PipelineAuthoringTurn.state == TurnState.PENDING.value,
            )
        )
        return "family" if turn is not None else "say"
    pending = db.scalar(
        select(PipelineAuthoringProposal).where(
            PipelineAuthoringProposal.session_id == row.id,
            PipelineAuthoringProposal.state == ProposalState.PENDING.value,
        )
    )
    if phase is Phase.GATHERING and pending is not None and pending.kind == "gap":
        return "reply"
    if phase is Phase.BUILDING and pending is not None and pending.kind == "step":
        return _BY_TIER[int(pending.payload["block"]["tier"])]
    return _BY_PHASE[phase]
