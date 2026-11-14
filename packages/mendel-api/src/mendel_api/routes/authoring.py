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

from datetime import datetime
from typing import Literal

from comeni_core.artifact.pipeline import AiProvenance
from comeni_core.declared.measurement import Measurement
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftEdge, DraftGraph, DraftProvenance
from comeni_core.spell.marks import HumanParamValue, OptionId
from fastapi import APIRouter, HTTPException, Request, status
from mendel_authoring import commands as c
from mendel_authoring.decisions import ActorKind, InputDecision
from mendel_authoring.payloads import DecisionChange
from mendel_authoring.progress import WalkProgress
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from mendel_api import identity
from mendel_api.agent import chat
from mendel_api.authoring.canvas import CanvasFrame
from mendel_api.authoring.envelopes import HistoryOffer, Offer
from mendel_api.authoring.types import (
    Block,
    Fact,
    Phase,
    ProposalState,
    Prose,
    TurnState,
    UploadedSample,
)
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services import drafts, session
from mendel_api.settings import model_access
from mendel_api.stages import gathering

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
    """For a step: `keep`, or one of the changes its card offered — an alternative tool
    (`alt_N`) or a fact (`fact_<measurement>`, with `value`). Ignored for a goal. **An id the
    engine minted, never a contract id** — a value chosen by id cannot be a value nobody
    offered."""
    value: HumanParamValue | list[HumanParamValue] | None = None
    """For a gap answered with the `value` option, or a step's `fact_<measurement>`: the typed
    value, held to the measurement's declaration before anything is recorded (`MI0208`).
    Ignored otherwise."""


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

    envelope: HistoryOffer
    id: str
    kind: Literal["goal", "step", "gap", "pacing", "disagreement"]
    state: ProposalState
    block: Block
    by: str | None
    actor_kind: ActorKind = ActorKind.UNKNOWN
    applicability: Literal["retained", "superseded", "removed"] | None = None
    chosen_option: str | None
    chosen_contract: str | None
    """The contract the chosen option stood for, so a row can name a substitution."""
    answer: str | None = None
    """For an answered gap, what was said: the typed value, or the chosen option's label."""
    at: str


class AuthoringProposalView(BaseModel):
    model_config = _FROZEN

    envelope: Offer

    id: str
    kind: Literal["goal", "step", "gap", "pacing", "disagreement"]
    draft_revision: int
    block: Block
    options: list[str]
    """Every id this proposal accepts. The block renders labels; this is what may be posted."""
    edges: list[DraftEdge] = []
    """The wires accepting it as proposed would add — what an optimistic reveal draws."""
    asked_at: str
    """When it was asked, ISO 8601: once the person says something after it, the chat docks it
    above the composer (one builder plan 3)."""


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
    cleared: Literal["deleted", "retention"] | None = None
    """Why `response` is empty though the model answered (Part H): the installation's retention
    limit passed, or its draft was deleted."""
    reply_format: str | None = None
    """`in_prompt`, or the provider format the server enforced (#194)."""
    at: str


class AuthoringSuggestionView(BaseModel):
    model_config = _FROZEN

    id: str
    says: str
    heard: bool
    quote: str | None = None
    kind: str
    subject: str
    measured: HumanParamValue | None = None
    """The measured value this contradicts (#345): the card asks *are you sure?* with Yes/No."""
    edit: str | None = None
    """Set when this is the engine's reading of a hand edit, not the model's suggestion: every
    reading of one edit shares it and is taken or set aside together (#395)."""


class DecideSuggestion(BaseModel):
    decision: Literal["apply", "dismiss"]


class AiChoiceView(BaseModel):
    model_config = _FROZEN

    node: str
    what: str


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
    samples: list[UploadedSample] = []
    """Every sample of the last upload, with its name and measurements (#466)."""
    inputs: list[InputDecision] = []
    fact_subjects: list[str] = []
    decision_revision: int = 0
    projection_current: bool = True
    retired: bool = False
    review_applicability: dict[str, Literal["retained", "superseded", "removed"]] = {}
    usage: AuthoringUsage = AuthoringUsage()
    """The session's model calls, totalled — carried by the poll the page already makes."""
    """What gathering learned, each with where it came from. Empty until 14.7.3's gathering."""
    revision: int
    graph: DraftGraph
    """The draft as the server holds it — the canvas restores from this, not from the transcript."""
    canvas: CanvasFrame | None = None
    """The visible graph with its step metadata and entry channels, read from what was recorded.
    `None` before a blueprint exists, or for an empty manual draft."""
    progress: WalkProgress | None = None
    """Where the walk is in the plan as it now stands. `None` before a blueprint, and for a
    draft the person owns by hand."""
    show_gap_details: bool = False
    """Dev mode as this build recorded it: whether gap kinds and repository paths are shown."""
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
    suggestions: list[AuthoringSuggestionView] = []
    not_offered: list[str] = []
    """What the person asked for that is not offered here, in their words (Part I.2)."""
    """The model's suggestions waiting for one click (Part I.0 §5.3)."""
    pending_proposal: AuthoringProposalView | None
    working: bool = False
    """Whether the builder agent is answering now (#463)."""
    ai_unreviewed: list[AiChoiceView] = []
    """What the AI chose that nobody has reviewed yet, by step (#463)."""


class AnswerQuestion(BaseModel):
    """The person's answer to the agent's question."""

    value: bool | int | float | str


class ReviewAiChoices(BaseModel):
    """The steps whose AI choices the person has looked at, or all of them."""

    nodes: list[str] | Literal["all"]


class AuthoringReviewed(BaseModel):
    model_config = _FROZEN

    ai_unreviewed: list[AiChoiceView]


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
    """The graph and the revision it was based on, with no client-composed summary: the server
    composes the receipt from the difference, so the log cannot be told something that did not
    happen."""

    model_config = _FROZEN

    graph: DraftGraph
    expected_revision: int = Field(ge=0)


class AuthoringEdited(BaseModel):
    model_config = _FROZEN

    revision: int
    offered: list[str] = []
    """The suggestions the edit was read as, waiting for the person (#395): a structural edit
    changes nothing until its reading is confirmed."""


class MeasurerView(BaseModel):
    """One way a measurement can be measured, and where that runs (#134)."""

    model_config = _FROZEN

    measurement: str
    by: str
    runs: list[Literal["server", "pipeline"]]
    """Where it may run: on the server over an upload's head, in the pipeline over all of it."""
    trusted: bool


class AuthoringVocabulary(BaseModel):
    """Every declared type and its states — what a goal card may be edited to say — and who
    can measure each measurement."""

    model_config = _FROZEN

    types: dict[str, list[str]]
    names: dict[str, str] = {}
    """The registry's name for each type that declares one (Part I.2): what the goal card shows."""
    measurers: list[MeasurerView] = []
    measurements: dict[str, Measurement] = {}
    grains: dict[str, str] = {}
    """Each type's declared grain, `study` or `sample` (issue 494): a reference genome is one
    file for the run, never one per sample, before anything is built."""


class AuthoringPreview(BaseModel):
    """The draft as `pipeline.yml` would read — **a preview, never the kept artifact.**"""

    model_config = _FROZEN

    revision: int
    state: Literal["ready", "empty", "illegal", "unavailable", "outdated"]
    """`ready` carries text; the other three carry none — a partial pipeline is never YAML."""
    text: str
    """`pipeline.yml` as it would read now, byte for byte what Keep would write."""
    findings: list[str] = []
    """Why there is no text, as coded sentences."""


class CorrectionContext(BaseModel):
    model_config = _FROZEN
    expected_decision_revision: int = Field(ge=0)
    expected_draft_revision: int = Field(ge=0)
    expected_session_version: int = Field(ge=0)


class CorrectAuthoringFact(CorrectionContext):
    value: HumanParamValue | list[HumanParamValue] | None = None
    kind: Literal["measurement", "input"] = "measurement"


class ChangeAuthoring(CorrectionContext):
    """Any change to intent or facts, as the person makes it (Part I.0 §5.1)."""

    change: DecisionChange


class AnswerEvidenceQuestion(CorrectionContext):
    option: Literal["keep_current", "use_measurement", "correct", "unknown"]
    value: HumanParamValue | list[HumanParamValue] | None = None


class ReleaseToolChoice(CorrectionContext):
    type_id: str
    states: list[str] = Field(default_factory=list)


class AuthoringCorrected(BaseModel):
    model_config = _FROZEN
    session_id: str
    draft_id: str
    phase: Phase
    revision: int
    decision_revision: int
    next_proposal: str | None
    projection_current: bool


class FactHistoryEntry(BaseModel):
    model_config = _FROZEN
    seq: int
    value: HumanParamValue | list[HumanParamValue] | None = None
    origin: Literal["person_said", "measured", "model_read", "open", "varies"]
    selected: bool
    current: bool
    revision_id: str | None = None
    observation_id: str | None = None
    actor_kind: ActorKind = ActorKind.UNKNOWN
    who: str | None = None
    action: Literal["select", "retain", "retract", "inherit", "import", "observed"]
    at: datetime
    observed_at: datetime | None = None
    acknowledged_as: Literal["agreement", "retained", "selected", "obsolete"] | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    acknowledged_kind: ActorKind | None = None
    legacy: bool = False


class FactHistoryView(BaseModel):
    model_config = _FROZEN
    subject: str
    entries: list[FactHistoryEntry]


# ── operations ────────────────────────────────────────────────────────────────────────────


@router.post(
    "",
    operation_id="beginAuthoring",
    summary="Describe an analysis; the builder agent starts building it",
    status_code=status.HTTP_201_CREATED,
    responses=REFUSES,
)
async def begin(body: BeginAuthoring) -> AuthoringStarted:
    """An empty draft, a session, the person's words, and the agent's turn queued (#463): the
    pending turn is in the response, so the page shows the agent working at once."""
    session_id, queued = await chat.start(body.prompt, identity.default_author())
    return AuthoringStarted(session=_view(session_id), queued=queued)


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
    types = registry_service.builder_types(stack)
    return AuthoringVocabulary(
        types={t: sorted(types[t]) for t in sorted(types)},
        names={t: n for t, n in sorted(stack.vocabulary.names.items()) if t in types},
        measurements=stack.measurements.measurements,
        measurers=[MeasurerView(**m.model_dump()) for m in measurers.index(stack)],
        grains={t: str(g) for t, g in sorted(stack.vocabulary.grains.items()) if t in types},
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
    "/{session_id}/facts/{subject}/history", operation_id="authoringFactHistory", responses=REFUSES
)
def fact_history(session_id: str, subject: str) -> FactHistoryView:
    from mendel_api.services import decisions

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="authoring session not found")
        entries = decisions.history(row.draft_id, subject)
    return FactHistoryView(subject=subject, entries=entries)


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
    summary="Say something to the builder agent",
    status_code=status.HTTP_202_ACCEPTED,
    responses=REFUSES,
)
async def say(session_id: str, body: SayToAuthoring) -> AuthoringSaid:
    seq, queued = await chat.say(session_id, body.text)
    return AuthoringSaid(seq=seq, queued=queued)


@router.post(
    "/{session_id}/questions/{question_id}",
    operation_id="answerAgentQuestion",
    summary="Answer a question the builder agent asked",
    status_code=status.HTTP_202_ACCEPTED,
    responses=REFUSES,
)
async def answer_question(session_id: str, question_id: str,
                          body: AnswerQuestion) -> AuthoringSaid:
    seq, queued = await chat.answer(session_id, question_id, body.value)
    return AuthoringSaid(seq=seq, queued=queued)


@router.post(
    "/{session_id}/turns/{seq}/retry",
    operation_id="retryAgentTurn",
    summary="Ask the builder agent again after its turn failed",
    status_code=status.HTTP_202_ACCEPTED,
    responses=REFUSES,
)
async def retry_turn(session_id: str, seq: int) -> AuthoringSaid:
    try:
        queued = await chat.retry(session_id, seq)
    except KeyError:
        raise
    except LookupError as refused:
        raise HTTPException(status_code=409, detail=str(refused.args[0])) from None
    return AuthoringSaid(seq=seq, queued=queued)


@router.post(
    "/{session_id}/reviewed",
    operation_id="reviewAiChoices",
    summary="Say you have looked at what the AI chose",
    responses=REFUSES,
)
async def reviewed(session_id: str, body: ReviewAiChoices) -> AuthoringReviewed:
    await run_in_threadpool(chat.review, session_id, body.nodes, identity.default_author())
    left = await run_in_threadpool(chat.unreviewed, session_id)
    return AuthoringReviewed(ai_unreviewed=[AiChoiceView(**m) for m in left])


@router.post(
    "/{session_id}/edits",
    operation_id="editAuthoringDraft",
    summary="Record a direct edit to the session's draft",
    responses=REFUSES,
)
async def edit(session_id: str, body: EditAuthoringDraft) -> AuthoringEdited:
    """A canvas or settings edit (#395). A structural edit is read by the engine and offered in
    the chat — nothing changes until the person confirms it. A typed value is the person's
    change at once, each one command through the correction path."""
    from starlette.concurrency import run_in_threadpool

    edited = (await session.act(
        c.RecordEdit(
            session_id,
            body.graph.model_dump(mode="json"),
            identity.default_author(),
            body.expected_revision,
        )
    )).result
    revision = edited.revision
    for value in edited.values:
        versions = await run_in_threadpool(_versions, session_id)
        done = await session.act(
            c.Change(session_id, value.model_dump(mode="json"), identity.default_author(),
                     *versions))
        revision = done.result["revision"]
    return AuthoringEdited(revision=revision, offered=edited.offered)


def _versions(session_id: str) -> tuple[int, int, int]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        return draft.decision_revision, draft.revision, row.row_version


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
        from mendel_api.services import authoring_decisions

        read_by_ai = session.characterised(
            [f.model_dump(mode="json") for f in authoring_decisions.facts(row.draft_id)]
        )
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
        samples=picture["samples"],
        **{
            key: picture[key]
            for key in (
                "inputs",
                "fact_subjects",
                "decision_revision",
                "projection_current",
                "retired",
                "review_applicability",
            )
        },
        usage=AuthoringUsage(**picture["usage"]),
        revision=picture["revision"],
        graph=DraftGraph.model_validate(picture["graph"] or {}),
        canvas=picture["canvas"],
        progress=picture["progress"],
        show_gap_details=picture["show_gap_details"],
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
        suggestions=[AuthoringSuggestionView(**s) for s in picture["suggestions"]],
        not_offered=picture["not_offered"],
        working=chat.working(picture["turns"]),
        ai_unreviewed=[AiChoiceView(**m) for m in chat.unreviewed(session_id)],
        pending_proposal=(
            None
            if pending is None
            else AuthoringProposalView(
                id=pending["id"],
                kind=pending["kind"],
                draft_revision=pending["draft_revision"],
                envelope=pending["payload"],
                block=pending["payload"]["block"],
                options=sorted(pending["payload"].get("options", {})),
                edges=pending["payload"].get("edges", []),
                asked_at=pending["asked_at"],
            )
        ),
    )


def _ai_for(provenance: DraftProvenance, *, characterised: bool = False) -> AiProvenance:
    """`session.ai_for`, kept under this name for its Task 12 test."""
    return session.ai_for(provenance, characterised=characterised)


class InspectedFactView(BaseModel):
    model_config = _FROZEN

    measurement: str
    value: HumanParamValue | list[HumanParamValue] | None = None
    undetermined: str | None = None
    pieces: list[str] = []
    evidence: dict[str, int | float | bool | str] = {}
    coverage: Literal["head", "all"] | None = None
    """How much of the file the measurer read (#465): `all` only for a whole file."""


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
    if heads.count < 1:
        raise ValueError(coded("MI0214", "no files: upload one or more samples"))
    proposal_id = heads.fields.get("proposal_id")
    # **Every database call off the event loop** (issue 226): a slow answer here would hold
    # every other request.
    kind = await run_in_threadpool(_kind_in, session_id, proposal_id) if proposal_id else None
    if kind != gathering.GAP:
        raise ValueError(coded("MI0205", "a sample answers a question about your data"))
    # The rest is one action (plan 1c): refused before a byte is inspected, a hand-back claimed
    # by the recorded type only, and a type nothing here reads handed to the AI.
    done = await session.act(
        c.UploadSample(session_id, proposal_id, tuple(heads.files), identity.default_author(),
                       sizes=sample_upload.sizes_of(heads.fields.get("sizes"), len(heads.files)))
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


@router.post(
    "/{session_id}/facts/{subject}",
    operation_id="correctAuthoringFact",
    summary="Correct a selected fact or return it to unknown",
    responses=REFUSES,
)
async def correct_fact(
    session_id: str, subject: str, body: CorrectAuthoringFact
) -> AuthoringCorrected:
    done = await session.act(
        c.CorrectFact(
            session_id,
            subject,
            body.value,
            identity.default_author(),
            body.expected_decision_revision,
            body.expected_draft_revision,
            body.expected_session_version,
            body.kind,
        )
    )
    return AuthoringCorrected.model_validate(done.result)


@router.post(
    "/{session_id}/changes",
    operation_id="changeAuthoring",
    summary="DecisionChange what you want or what is known about your data",
    responses=REFUSES,
)
async def change_authoring(session_id: str, body: ChangeAuthoring) -> AuthoringCorrected:
    done = await session.act(
        c.Change(
            session_id,
            body.change.model_dump(mode="json"),
            identity.default_author(),
            body.expected_decision_revision,
            body.expected_draft_revision,
            body.expected_session_version,
        )
    )
    return AuthoringCorrected.model_validate(done.result)


@router.post(
    "/{session_id}/release-tool",
    operation_id="releaseAuthoringTool",
    summary="Let the engine choose a producer again",
    responses=REFUSES,
)
async def release_tool(session_id: str, body: ReleaseToolChoice) -> AuthoringCorrected:
    done = await session.act(
        c.ReleaseProducer(
            session_id,
            body.type_id,
            tuple(body.states),
            identity.default_author(),
            body.expected_decision_revision,
            body.expected_draft_revision,
            body.expected_session_version,
        )
    )
    return AuthoringCorrected.model_validate(done.result)
