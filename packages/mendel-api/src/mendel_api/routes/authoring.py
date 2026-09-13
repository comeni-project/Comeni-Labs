"""The living pipeline's HTTP surface. Transport only — every rule is in a service.

**Six operations, and the split between the fast and the slow ones is the design.** Starting a
session and saying something are accepted immediately and answered by the AI worker; the reply
arrives on the next poll. Accepting a goal, accepting or rejecting a step, retrying into a Build
blueprint, and reading the preview are ordinary requests that answer in the response — §2: *do
not put a button click behind the slow queue*.

**The GET is the whole authoritative picture**, so a reload restores the page from one read: the
transcript, the pending proposal, the phase, the draft revision, and whether a model is
configured at all. History is never truncated here — `CHAT_TAIL` bounds what a *model* is shown,
and a person reading their own conversation is shown all of it.

**No provider text crosses this boundary.** A refusal reaches a browser as a `notice` block with
a declared code, written by the job; this file never catches a provider exception and never
formats one.
"""

from typing import Literal

from comeni_core.artifact.pipeline import AiPoint, AiProvenance
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftProvenance
from comeni_core.plan.tiers import ValueSource
from comeni_core.spell.marks import OptionId
from fastapi import APIRouter, status
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict, Field

from mendel_api import identity
from mendel_api.authoring.types import (
    Block,
    Mode,
    Phase,
    ProposalState,
    Prose,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services import authoring, authoring_jobs, drafts
from mendel_api.settings import model_access

router = APIRouter(prefix="/pipeline/authoring", tags=["authoring"])

_FROZEN = ConfigDict(extra="forbid", frozen=True)


# ── what goes in ──────────────────────────────────────────────────────────────────────────


class BeginAuthoring(BaseModel):
    """What somebody wants, in their own words, and how much they want to be asked.

    **Prose and a mode, and nothing else.** No name, no path, no registry, no model id — a body
    that accepted a model id would let a browser choose what a provider is sent to, and that is
    the operator's decision, made in the environment.
    """

    model_config = _FROZEN

    prompt: Prose = Field(min_length=1)
    mode: Mode = Mode.BUILD


class SayToAuthoring(BaseModel):
    """A follow-up. **No revision**: saying something proposes no change, so it cannot conflict."""

    model_config = _FROZEN

    text: Prose = Field(min_length=1)


class DecideProposal(BaseModel):
    """An answer to one proposal, against the draft revision the person was looking at."""

    model_config = _FROZEN

    decision: Literal["accepted", "rejected"]
    expected_revision: int = Field(ge=0)
    option: OptionId | None = None
    """For a step: `keep`, or one of the alternative ids the proposal offered. Ignored for a
    goal. **An id the engine minted, never a contract id** — a value chosen by id cannot be a
    value nobody offered."""


# ── what comes out ────────────────────────────────────────────────────────────────────────


class AuthoringPosition(BaseModel):
    model_config = _FROZEN

    x: int
    y: int


class AuthoringTurnView(BaseModel):
    model_config = _FROZEN

    seq: int
    role: Literal["person", "assistant"]
    state: TurnState
    text: str
    blocks: list[Block]
    base_revision: int
    at: str
    """When it was written, ISO 8601 — so a log can interleave turns and decisions in order."""


class AuthoringDecisionView(BaseModel):
    """A proposal that has been answered — one collapsed row of the decision log."""

    model_config = _FROZEN

    id: str
    kind: Literal["goal", "step"]
    state: ProposalState
    block: Block
    by: str | None
    chosen_option: str | None
    chosen_contract: str | None
    """The contract the chosen option stood for, so a row can name a substitution."""
    at: str


class AuthoringProposalView(BaseModel):
    model_config = _FROZEN

    id: str
    kind: Literal["goal", "step"]
    draft_revision: int
    block: Block
    options: list[str]
    """Every id this proposal accepts. The block renders labels; this is what may be posted."""
    edges: list[DraftEdge] = []
    """The wires accepting it as proposed would add — what an optimistic reveal draws."""


class AuthoringSessionView(BaseModel):
    """Everything needed to restore the page, from one read."""

    model_config = _FROZEN

    id: str
    draft_id: str
    name: str
    mode: Mode
    phase: Phase
    failed_from: Phase | None
    goal: Goal | None
    revision: int
    graph: DraftGraph
    """The draft as the server holds it — the canvas restores from this, not from the transcript."""
    steps_total: int = 0
    """How many steps the resolved pipeline has. `0` until a blueprint exists."""
    placement: dict[str, AuthoringPosition] = {}
    """Where each visible step sits in the finished pipeline, so nothing moves as it grows."""
    row_version: int
    model_configured: bool
    """Whether this installation has a model at all. `False` is the no-AI lane: the page says
    Build and Spawn need one, and why, rather than spinning on a turn nobody will answer."""
    turns: list[AuthoringTurnView]
    history: list[AuthoringDecisionView] = []
    """Every answered proposal, oldest first — the pipeline's provenance, made navigable."""
    pending_proposal: AuthoringProposalView | None


class AuthoringStarted(BaseModel):
    model_config = _FROZEN

    session: AuthoringSessionView
    queued: bool
    """`False` when the queue already held this job — the turn is still pending and will be
    answered once. Reported rather than hidden, because a caller telling a person *sent* must
    know whether that is true."""


class AuthoringSaid(BaseModel):
    model_config = _FROZEN

    seq: int
    queued: bool


class AuthoringDecided(BaseModel):
    model_config = _FROZEN

    phase: Phase
    revision: int
    next_proposal: str | None
    queued: bool
    """Whether a Spawn blueprint was handed to the AI worker. Always `False` for Build, which
    resolves inline and has its first step waiting in `next_proposal`."""


class AuthoringRetried(BaseModel):
    model_config = _FROZEN

    phase: Phase
    queued: bool


class AuthoringPreview(BaseModel):
    model_config = _FROZEN

    revision: int
    text: str
    """`pipeline.yml` as it would read now. Empty while nothing has been accepted."""


# ── operations ────────────────────────────────────────────────────────────────────────────


@router.post(
    "",
    operation_id="beginAuthoring",
    summary="Describe an analysis and start building it",
    status_code=status.HTTP_201_CREATED,
    responses=REFUSES,
)
async def begin(body: BeginAuthoring) -> AuthoringStarted:
    """An empty draft, a session, the first turn, and one queued model call — the pending reply
    is visible in the response, so the page never shows a blank while the worker starts."""
    session_id, seq = authoring.begin(body.prompt, mode=body.mode, who=identity.default_author())
    queued = await authoring_jobs.enqueue_turn(session_id, seq)
    return AuthoringStarted(session=_view(session_id), queued=queued)


@router.get(
    "/{session_id}",
    operation_id="readAuthoring",
    summary="The whole session, as the page restores it",
    responses=REFUSES,
)
def read(session_id: str) -> AuthoringSessionView:
    return _view(session_id)


@router.post(
    "/{session_id}/messages",
    operation_id="sayToAuthoring",
    summary="Say something in the conversation",
    status_code=status.HTTP_202_ACCEPTED,
    responses=REFUSES,
)
async def say(session_id: str, body: SayToAuthoring) -> AuthoringSaid:
    seq = authoring.say(session_id, body.text)
    return AuthoringSaid(seq=seq, queued=await authoring_jobs.enqueue_turn(session_id, seq))


@router.post(
    "/{session_id}/proposals/{proposal_id}/decide",
    operation_id="decideAuthoringProposal",
    summary="Accept or reject a goal or a step",
    responses=REFUSES,
)
async def decide(session_id: str, proposal_id: str, body: DecideProposal) -> AuthoringDecided:
    """A deterministic request: the answer is in the response, never behind the queue.

    A refusal — a stale revision, a moved registry, an option never offered — answers 422 with
    its code, and the session has already recorded whatever the refusal changed (a proposal
    marked stale, a fresh one offered), so the client re-reads rather than retrying blind.
    """
    kind = _kind_in(session_id, proposal_id)
    decision = ProposalState(body.decision)
    who = identity.default_author()

    if kind == authoring_jobs.GOAL:
        outcome, phase = authoring.decide_goal(
            proposal_id, decision, expected_revision=body.expected_revision, by=who
        )
        if outcome.refusal is not None:
            raise ValueError(outcome.refusal)
        return await _after_goal(session_id, phase)

    stepped = authoring.settle_step(
        proposal_id,
        decision,
        expected_revision=body.expected_revision,
        by=who,
        chosen_option=body.option,
    )
    if stepped.settlement.refusal is not None:
        raise ValueError(stepped.settlement.refusal)
    return AuthoringDecided(
        phase=stepped.phase,
        revision=stepped.revision,
        next_proposal=stepped.next_proposal,
        queued=False,
    )


@router.post(
    "/{session_id}/retry",
    operation_id="retryAuthoring",
    summary="Try again from where the session failed",
    responses=REFUSES,
)
async def retry(session_id: str) -> AuthoringRetried:
    phase, seq = authoring.retry(session_id)
    if seq is not None:
        return AuthoringRetried(
            phase=phase, queued=await authoring_jobs.enqueue_turn(session_id, seq)
        )
    decided = await _after_goal(session_id, phase)
    return AuthoringRetried(phase=decided.phase, queued=decided.queued)


@router.get(
    "/{session_id}/preview",
    operation_id="previewAuthoring",
    summary="The pipeline as it would read now",
    responses=REFUSES,
)
def preview(session_id: str) -> AuthoringPreview:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft_id, mode = row.draft_id, Mode(row.mode)
        stored = db.get(PipelineDraft, draft_id)
        provenance = DraftProvenance.model_validate(stored.provenance or {})
    revision, text = drafts.preview(draft_id, ai=_ai_for(mode, provenance))
    return AuthoringPreview(revision=revision, text=text)


# ── helpers ───────────────────────────────────────────────────────────────────────────────


async def _after_goal(session_id: str, phase: Phase) -> AuthoringDecided:
    """A confirmed goal starts the blueprint: inline for Build, on the AI queue for Spawn."""
    view = _view(session_id)
    if phase is not Phase.RESOLVING:
        return AuthoringDecided(
            phase=phase, revision=view.revision, next_proposal=None, queued=False
        )
    if view.mode is Mode.SPAWN:
        queued = await authoring_jobs.enqueue_build(session_id, view.row_version)
        return AuthoringDecided(
            phase=phase, revision=view.revision, next_proposal=None, queued=queued
        )
    try:
        first = authoring.start_building(session_id)
    except Exception as failure:
        if isinstance(failure, ValueError):
            raise  # a coded refusal — 422 with its code
        # Anything else is the resolver failing, and `start_building` has already moved the
        # session to `failed`, where retry is the verb. Its message is not repeated here: it is
        # not a declared code, and the page reads the phase.
        first = None
    after = _view(session_id)
    return AuthoringDecided(
        phase=after.phase, revision=after.revision, next_proposal=first, queued=False
    )


def _kind_in(session_id: str, proposal_id: str) -> str:
    """The proposal's kind — **and a 404 when it belongs to another session**, so a path naming
    one session cannot act on another's proposal."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, proposal_id)
        if row is None or row.session_id != session_id:
            raise KeyError(proposal_id)
        return row.kind


def _view(session_id: str) -> AuthoringSessionView:
    picture = authoring.read(session_id)
    pending = picture["pending_proposal"]
    return AuthoringSessionView(
        id=picture["id"],
        draft_id=picture["draft_id"],
        name=picture["name"],
        mode=Mode(picture["mode"]),
        phase=Phase(picture["phase"]),
        failed_from=Phase(picture["failed_from"]) if picture["failed_from"] else None,
        goal=Goal.model_validate(picture["goal"]) if picture["goal"] else None,
        revision=picture["revision"],
        graph=DraftGraph.model_validate(picture["graph"] or {}),
        placement=picture["placement"],
        steps_total=picture["steps_total"],
        row_version=picture["row_version"],
        model_configured=model_access() is not None,
        turns=[
            AuthoringTurnView(
                seq=turn["seq"],
                role=turn["role"],
                state=TurnState(turn["state"]),
                text=turn["text"],
                blocks=turn["blocks"],
                base_revision=turn["base_revision"],
                at=turn["at"],
            )
            for turn in picture["turns"]
        ],
        history=[AuthoringDecisionView(**decision) for decision in picture["history"]],
        pending_proposal=(
            None
            if pending is None
            else AuthoringProposalView(
                id=pending["id"],
                kind=pending["kind"],
                draft_revision=pending["draft_revision"],
                block=pending["payload"]["block"],
                options=sorted(pending["payload"].get("options", {})),
                edges=pending["payload"].get("edges", []),
            )
        ),
    )


def _ai_for(mode: Mode, provenance: DraftProvenance) -> AiProvenance:
    """What AI points this installation offers a session, stated from configuration.

    **Never derived from the sidecar's claims** — `MD0225` checks a model-settled value against
    `available`, and deriving `available` from those values would make the check circular. `used`
    is read from the sidecar because it answers a different question: which points this draft
    actually exercised.
    """
    if model_access() is None:
        return AiProvenance(available=[], used=[])
    available = [AiPoint.PROMPT] + ([AiPoint.TIER_4] if mode is Mode.SPAWN else [])
    modelled = any(
        entry.selection is not None and entry.selection.source is ValueSource.MODEL
        for entry in provenance.nodes
    ) or any(entry.settled.source is ValueSource.MODEL for entry in provenance.params)
    used = [AiPoint.PROMPT] + ([AiPoint.TIER_4] if modelled else [])
    return AiProvenance(available=available, used=used)
