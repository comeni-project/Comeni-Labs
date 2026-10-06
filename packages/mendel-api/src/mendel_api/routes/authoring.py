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

from comeni_core.artifact.pipeline import AiProvenance
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftProvenance
from comeni_core.spell.marks import HumanParamValue, OptionId
from fastapi import APIRouter, HTTPException, Request, status
from mendel_authoring import commands as c
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from mendel_api import identity
from mendel_api.authoring.types import (
    Block,
    Fact,
    Phase,
    ProposalState,
    Prose,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services import drafts, session
from mendel_api.settings import model_access
from mendel_api.stages import gathering, goal

router = APIRouter(prefix="/pipeline/authoring", tags=["authoring"])

_FROZEN = ConfigDict(extra="forbid", frozen=True)


# ── what goes in ──────────────────────────────────────────────────────────────────────────


class BeginAuthoring(BaseModel):
    """What somebody wants, in their own words.

    **Prose, and nothing else.** No mode (Build and Spawn are retired, spec §13.1), no name,
    no path, no registry, no model id — a body
    that accepted a model id would let a browser choose what a provider is sent to, and that is
    the operator's decision, made in the environment.
    """

    model_config = _FROZEN

    prompt: Prose = Field(min_length=1)


class SayToAuthoring(BaseModel):
    """A follow-up. **No revision**: saying something proposes no change, so it cannot conflict."""

    model_config = _FROZEN

    text: Prose = Field(min_length=1)


class DecideProposal(BaseModel):
    """An answer to one proposal, against the draft revision the person was looking at."""

    model_config = _FROZEN

    decision: Literal["accepted", "rejected"]
    expected_revision: int = Field(ge=0)
    goal: Goal | None = None
    """For a goal: the goal as the person edited it on the card, when they changed a field. Held to
    the declared vocabulary — `MI0204` — exactly as a model's goal is. Ignored for a step."""
    option: OptionId | None = None
    """For a step: `keep`, or one of the alternative ids the proposal offered. Ignored for a
    goal. **An id the engine minted, never a contract id** — a value chosen by id cannot be a
    value nobody offered."""
    value: HumanParamValue | None = None
    """For a gap answered with the `value` option: the typed value, held to the measurement's
    declaration before anything is recorded (`MI0208`). Ignored otherwise."""


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
    kind: Literal["goal", "step", "gap"]
    state: ProposalState
    block: Block
    by: str | None
    chosen_option: str | None
    chosen_contract: str | None
    """The contract the chosen option stood for, so a row can name a substitution."""
    answer: str | None = None
    """For an answered gap, what was said: the typed value, or the chosen option's label."""
    at: str


class AuthoringProposalView(BaseModel):
    model_config = _FROZEN

    id: str
    kind: Literal["goal", "step", "gap"]
    draft_revision: int
    block: Block
    options: list[str]
    """Every id this proposal accepts. The block renders labels; this is what may be posted."""
    edges: list[DraftEdge] = []
    """The wires accepting it as proposed would add — what an optimistic reveal draws."""


class AuthoringUsage(BaseModel):
    """What the session's model calls have cost so far — the header's count (#191)."""

    model_config = _FROZEN

    input: int = 0
    output: int = 0
    cached: int = 0
    """Input tokens served from a provider's prompt cache (#183)."""
    calls: int = 0
    in_flight: bool = False
    """Whether a model call is on its way right now: the header says *thinking…*."""


class AuthoringCallView(BaseModel):
    """One model call in the session, for the call panel (#182, #191)."""

    model_config = _FROZEN

    id: str
    purpose: str
    model: str
    input: int | None
    output: int | None
    cached: int | None
    duration_ms: int | None
    state: str
    response: str | None
    """Exactly what the model returned — a level-0 store (#182)."""
    reply_format: str | None = None
    """`in_prompt`, or the provider format the server enforced (#194)."""
    at: str


class AuthoringSessionView(BaseModel):
    """Everything needed to restore the page, from one read."""

    model_config = _FROZEN

    id: str
    draft_id: str
    name: str
    phase: Phase
    failed_from: Phase | None
    goal: Goal | None
    facts: list[Fact] = []
    usage: AuthoringUsage = AuthoringUsage()
    """The session's model calls, totalled — carried by the poll the page already makes."""
    """What gathering learned, each with where it came from. Empty until 14.7.3's gathering."""
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
    the builder needs one, and why, rather than spinning on a turn nobody will answer."""
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
    """Always `False` now: a blueprint is resolved inline, its first stop waiting in
    `next_proposal`. Kept for the client until the response is next reshaped."""


class AuthoringRetried(BaseModel):
    model_config = _FROZEN

    phase: Phase
    queued: bool


class EditAuthoringDraft(BaseModel):
    """The whole graph after a direct edit. **The graph and nothing else** — no summary: the server
    composes the receipt from the difference, so the log cannot be told something that did not
    happen."""

    model_config = _FROZEN

    graph: DraftGraph


class AuthoringEdited(BaseModel):
    model_config = _FROZEN

    revision: int
    reoffered: str | None
    """A pending step proposal made stale by the edit and offered again at the new revision."""


class MeasurerView(BaseModel):
    """One way a measurement can be measured, and where that runs (#134)."""

    model_config = _FROZEN

    measurement: str
    kind: Literal["inspector", "profiler"]
    by: str
    runs: Literal["server", "lab", "browser"]
    trusted: bool


class AuthoringVocabulary(BaseModel):
    """Every declared type and its states — what a goal card may be edited to say — and who
    can measure each measurement."""

    model_config = _FROZEN

    types: dict[str, list[str]]
    measurers: list[MeasurerView] = []


class AuthoringPreview(BaseModel):
    """The draft as `pipeline.yml` would read — **a preview, never the kept artifact.**"""

    model_config = _FROZEN

    revision: int
    state: Literal["ready", "empty", "illegal", "unavailable"]
    """`ready` carries text; the other three carry none — a partial pipeline is never YAML."""
    text: str
    """`pipeline.yml` as it would read now, byte for byte what Keep would write."""
    findings: list[str] = []
    """Why there is no text, as coded sentences."""


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
    done = await session.act(c.Begin(body.prompt, identity.default_author()))
    session_id, _ = done.result
    return AuthoringStarted(session=_view(session_id), queued=all(done.queued))


@router.get(
    "/vocabulary",
    operation_id="authoringVocabulary",
    summary="The types a goal may name",
)
def vocabulary() -> AuthoringVocabulary:
    """Declared, public registry data — the same list a model is shown, served to the card that
    lets a person correct what the model wrote. Registered before `/{session_id}`, which would
    otherwise read `vocabulary` as a session id."""
    from mendel_api.services import measurers
    from mendel_api.services import registry as registry_service

    stack = registry_service.stack()
    types = stack.vocabulary.types
    return AuthoringVocabulary(
        types={t: sorted(types[t]) for t in sorted(types)},
        measurers=[MeasurerView(**m.model_dump()) for m in measurers.index(stack)],
    )


@router.get(
    "/{session_id}",
    operation_id="readAuthoring",
    summary="The whole session, as the page restores it",
    responses=REFUSES,
)
def read(session_id: str) -> AuthoringSessionView:
    return _view(session_id)


@router.get(
    "/{session_id}/calls",
    operation_id="listAuthoringCalls",
    summary="The session's model calls, with what each returned",
    responses=REFUSES,
)
def list_calls(session_id: str) -> list[AuthoringCallView]:
    """Fetched when the call panel opens, and again only when the session's call count moves."""
    return [AuthoringCallView(**call) for call in session.calls(session_id)]


@router.post(
    "/{session_id}/messages",
    operation_id="sayToAuthoring",
    summary="Say something in the conversation",
    status_code=status.HTTP_202_ACCEPTED,
    responses=REFUSES,
)
async def say(session_id: str, body: SayToAuthoring) -> AuthoringSaid:
    done = await session.act(c.Say(session_id, body.text))
    return AuthoringSaid(seq=done.result, queued=all(done.queued))


@router.post(
    "/{session_id}/proposals/{proposal_id}/decide",
    operation_id="decideAuthoringProposal",
    summary="Accept or reject a goal or a step, or answer a question about your data",
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

    if kind == gathering.GAP:
        if decision is not ProposalState.ACCEPTED or body.option is None:
            raise ValueError(
                coded("MI0205", "a question about your data is answered with one of its options")
            )
        # The next question and the one after are phrased while the person reads (#186): `ask`
        # queued them, after the commit. A button click is not put behind a model.
        await session.act(c.AnswerGap(proposal_id, body.option, body.value, who))
        after = _view(session_id)
        return AuthoringDecided(
            phase=after.phase,
            revision=after.revision,
            next_proposal=after.pending_proposal.id if after.pending_proposal else None,
            queued=False,
        )

    if kind == goal.GOAL:
        done = await session.act(
            c.DecideGoal(
                proposal_id,
                decision.value,
                body.expected_revision,
                who,
                None if body.goal is None else body.goal.model_dump(mode="json"),
            )
        )
        outcome, phase = done.result
        if outcome.refusal is not None:
            raise ValueError(outcome.refusal)
        return await _after_goal(session_id, phase)

    stepped = (
        await session.act(
            c.SettleStep(proposal_id, decision.value, body.expected_revision, who, body.option)
        )
    ).result
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
    done = await session.act(c.Retry(session_id))
    phase, seq = done.result
    if seq is not None:
        return AuthoringRetried(phase=phase, queued=all(done.queued))
    decided = await _after_goal(session_id, phase)
    return AuthoringRetried(phase=decided.phase, queued=decided.queued)


@router.post(
    "/{session_id}/edits",
    operation_id="editAuthoringDraft",
    summary="Record a direct edit to the session's draft",
    responses=REFUSES,
)
def edit(session_id: str, body: EditAuthoringDraft) -> AuthoringEdited:
    """A canvas or settings edit. Saved, stamped as the person's, and written into the log as a
    receipt the server composes — never narrated by a model."""
    revision, reoffered = session.perform(
        c.RecordEdit(session_id, body.graph.model_dump(mode="json"), identity.default_author())
    ).result
    return AuthoringEdited(revision=revision, reoffered=reoffered)


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
        draft_id = row.draft_id
        stored = db.get(PipelineDraft, draft_id)
        provenance = DraftProvenance.model_validate(stored.provenance or {})
        read_by_ai = session.characterised(row.facts)
    shown = drafts.preview(draft_id, ai=_ai_for(provenance, characterised=read_by_ai))
    return AuthoringPreview(
        revision=shown.revision, state=shown.state, text=shown.text, findings=shown.findings
    )


# ── helpers ───────────────────────────────────────────────────────────────────────────────


async def _after_goal(session_id: str, phase: Phase) -> AuthoringDecided:
    """A confirmed goal starts the blueprint, inline: resolving it calls no model."""
    view = _view(session_id)
    if phase is not Phase.RESOLVING:
        return AuthoringDecided(
            phase=phase, revision=view.revision, next_proposal=None, queued=False
        )
    try:
        first = (await session.act(c.StartBuilding(session_id))).result
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
    picture = session.read(session_id)
    pending = picture["pending_proposal"]
    return AuthoringSessionView(
        id=picture["id"],
        draft_id=picture["draft_id"],
        name=picture["name"],
        phase=Phase(picture["phase"]),
        failed_from=Phase(picture["failed_from"]) if picture["failed_from"] else None,
        goal=gathering.as_goal(picture["goal"]),
        facts=picture["facts"],
        usage=AuthoringUsage(**picture["usage"]),
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


def _ai_for(provenance: DraftProvenance, *, characterised: bool = False) -> AiProvenance:
    """`session.ai_for`, kept under this name for its Task 12 test."""
    return session.ai_for(provenance, characterised=characterised)


class InspectedFactView(BaseModel):
    model_config = _FROZEN

    measurement: str
    value: HumanParamValue | None = None
    undetermined: str | None = None
    pieces: list[str] = []
    evidence: dict[str, int | float | bool | str] = {}


class SampleInspected(BaseModel):
    """What one uploaded sample measured, and what that settled (14.7.6.4)."""

    model_config = _FROZEN

    outcome: Literal["measured", "unreadable", "no_inspector", "tie", "reading"]
    type_id: str | None
    facts: list[InspectedFactView]
    reason: str | None
    steps: list[str]
    """What was done, in order: returned with the answer, not streamed."""
    recorded: list[str]
    kept: list[str]
    disagreed: list[str]
    session: AuthoringSessionView


_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["proposal_id", "files"],
                    "properties": {
                        "proposal_id": {"type": "string"},
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "minItems": 1,
                            "maxItems": 2,
                        },
                    },
                }
            }
        },
    }
}


@router.post(
    "/{session_id}/samples",
    operation_id="uploadAuthoringSample",
    summary="Answer a question about your data with a sample: one file, or a pair",
    responses={**REFUSES, 403: {"description": "`MI0213`: the protection level refuses it."}},
    openapi_extra=_UPLOAD_BODY,
)
async def upload_sample(session_id: str, request: Request) -> SampleInspected:
    """**Only the first 4 MB of each file is kept**, in memory; the rest is read through and
    dropped, and nothing is written to disk (14.7.6's ruling: nothing deletes a session yet, so
    nothing about a sample is kept). The protection level is asked before a byte is read."""
    from mendel_api.services import inspect, protection, sample_upload

    if not protection.allows(protection.Crossing.UPLOAD):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, protection.refuse(protection.Crossing.UPLOAD)
        )
    try:
        heads = await sample_upload.read_heads(request, head=inspect.HEAD_BYTES)
    except ValueError as refused:
        raise ValueError(coded("MI0214", str(refused))) from None
    if not 1 <= heads.count <= 2:
        raise ValueError(coded("MI0214", f"{heads.count} files: upload one file, or a pair"))
    proposal_id = heads.fields.get("proposal_id")
    # **Every database call off the event loop** (issue 226): a slow answer here would hold
    # every other request.
    kind = await run_in_threadpool(_kind_in, session_id, proposal_id) if proposal_id else None
    if kind != gathering.GAP:
        raise ValueError(coded("MI0205", "a sample answers a question about your data"))
    # The rest is one action (plan 1c): refused before a byte is inspected, a hand-back claimed
    # by the recorded type only, and a type nothing here reads handed to the AI.
    done = await session.act(
        c.UploadSample(session_id, proposal_id, tuple(heads.files), identity.default_author())
    )
    up = done.result
    view = await run_in_threadpool(_view, session_id)
    if up.reading:
        return SampleInspected(
            outcome="reading",
            type_id=None,
            facts=[],
            reason=None,
            steps=[*up.inspection.steps, "nothing here reads its type: the AI is reading it"],
            recorded=[],
            kept=[],
            disagreed=[],
            session=view,
        )
    return SampleInspected(
        outcome=up.inspection.outcome,
        type_id=up.inspection.type_id,
        facts=[InspectedFactView(**f.model_dump()) for f in up.inspection.facts],
        reason=up.inspection.reason,
        steps=up.inspection.steps,
        recorded=up.answer.recorded,
        kept=up.answer.kept,
        disagreed=up.answer.disagreed,
        session=view,
    )
