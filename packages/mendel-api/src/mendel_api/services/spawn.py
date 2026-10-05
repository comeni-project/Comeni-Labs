"""**Deleted in part 3 of the consultant build** (spec §11.1): Build/Spawn and `Mode` are
retired. Until then Spawn lives here, fenced off from the stages: the same proposals as Build,
accepted by policy where that is safe.

**Spawn bypasses the facade's transaction** (ruling 3 of plan 1c): its blueprint is resolved
with a model, and nothing that calls a model runs inside a transaction. `start` and `build` call
the building stage with their own scopes, as before; each step it accepts is one command.
"""

from typing import NamedTuple

from comeni_core.plan.draft import DraftGraph
from mendel_authoring import commands as c
from sqlalchemy import select

from mendel_api.authoring.types import Mode, Phase, ProposalState
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineDraft,
)
from mendel_api.services import blueprint as bp
from mendel_api.services import session
from mendel_api.stages import building


def start(session_id: str, *, client) -> str | None:
    """Resolve a Spawn blueprint and offer its first step, **outside any transaction**: the
    resolver may put tier-4 questions to the model."""
    ctx = session.Ctx(session_id, None)
    first = building.start(ctx, session_id, client=client)
    if ctx.raised is not None:
        raise ctx.raised
    return first


def build(session_id: str, client) -> None:
    """The Spawn build job's work: the blueprint, then every step the policy may accept."""
    start(session_id, client=client)
    spawn_forward(session_id)


SPAWN_STOP = frozenset({"MI0201", "MI0202", "MI0203", "MI0206"})
"""Refusals that end an automatic run with the proposal left for a person."""


class SpawnStop(NamedTuple):
    """Why an automatic run stopped, or `None` for a pipeline that completed."""

    node: str | None
    reason: str | None


def spawn_forward(session_id: str, *, limit: int = 200) -> SpawnStop:
    """Accept every step Spawn may accept, in order, until one needs a person or none is left.

    **The same `settle_step` Build uses, one proposal at a time** — an idempotent sequence rather
    than a second commit path, so a Spawn pipeline and a Build pipeline are made by the same code
    and every proposal stays in history, answered, with its author. §1.2's two policies over one
    engine is this function being a loop and nothing else.

    **What Spawn accepts:** a step the resolver settled at tiers 1 to 3, and a tier-4 step a model
    chose from its candidates (`source: model`). **Where it stops**, leaving the proposal pending
    for exactly the card Build would show: a tier-4 step the flag settled — no model, a refusal, or
    no candidate the model could take — an illegal graph after the step, and any refusal from the
    commit itself, including a registry that moved.

    The acceptance is recorded against the author the policy relied on — `resolver` or `model` —
    never against *spawn*: the policy decided nothing, it only declined to ask.
    """
    from mendel_api.services import validate as validation

    for _ in range(limit):
        with session_scope() as db:
            row = db.get(PipelineAuthoringSession, session_id)
            if row is None:
                raise KeyError(session_id)
            if Mode(row.mode) is not Mode.SPAWN or Phase(row.phase) is not Phase.BUILDING:
                return SpawnStop(None, None)
            pending = db.scalar(
                select(PipelineAuthoringProposal).where(
                    PipelineAuthoringProposal.session_id == session_id,
                    PipelineAuthoringProposal.state == ProposalState.PENDING.value,
                )
            )
            if pending is None or pending.kind != building.STEP:
                return SpawnStop(None, None)
            blueprint = bp.Blueprint.model_validate(row.blueprint)
            draft = db.get(PipelineDraft, row.draft_id)
            node = pending.payload["node"]
            step = blueprint.step(node)
            proposal_id = pending.id
            revision = draft.revision
            present = DraftGraph.model_validate(draft.graph)

        from comeni_core.plan.tiers import Tier, ValueSource

        if step.why.tier is Tier.AMBIGUOUS and step.why.source is not ValueSource.MODEL:
            return SpawnStop(node, "a choice no rule settled and no model made")

        after = present.model_copy(
            update={
                "nodes": [
                    *present.nodes,
                    {"id": node, "contract_id": step.module.contract_id, "params": []},
                ]
            }
        )
        if validation.of(DraftGraph.model_validate(after.model_dump())).illegal:
            return SpawnStop(node, "the pipeline would not be legal with this step")

        author = "model" if step.why.source is ValueSource.MODEL else "resolver"
        outcome = session.perform(
            c.SettleStep(proposal_id, ProposalState.ACCEPTED.value, revision, author)
        ).result
        if outcome.settlement.refusal is not None:
            code = outcome.settlement.refusal.split(":", 1)[0]
            return SpawnStop(node, code if code in SPAWN_STOP else outcome.settlement.refusal)
        if outcome.next_proposal is None:
            return SpawnStop(None, None)
    return SpawnStop(None, "stopped after the step limit")


def mode_of(session_id: str) -> Mode:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        return Mode(row.mode)

