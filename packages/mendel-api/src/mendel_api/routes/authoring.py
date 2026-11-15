"""The builder's HTTP surface (#463): the agent's chat, and what a person does directly beside it.

**The slow and the fast.** Starting a session, saying something and answering the agent's
question are accepted at once and answered by the AI worker; the reply arrives on the next poll,
written as the agent works. A person's own change, a corrected fact, a released tool, a canvas
edit and an uploaded sample answer in the response: they are the person's, recorded at once, and
the pipeline is built again so the canvas follows.

**The GET is the whole picture**: the thread, the canvas, what was understood, and what the AI
chose that nobody has reviewed. No provider text crosses this boundary; a failed turn carries a
declared code, written by the job.
"""

from datetime import datetime
from typing import Literal

from comeni_core.artifact.pipeline import AiProvenance
from comeni_core.declared.measurement import Measurement
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from comeni_core.spell.marks import HumanParamValue
from fastapi import APIRouter, HTTPException, Request, status
from mendel_authoring.decisions import ActorKind, InputDecision
from mendel_authoring.payloads import DecisionChange
from mendel_resolver.goal import Goal
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from mendel_api import identity
from mendel_api.agent import chat, direct, view
from mendel_api.authoring.canvas import CanvasFrame
from mendel_api.authoring.types import Block, Fact, Prose, TurnState, UploadedSample
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.refusals import REFUSES
from mendel_api.services import drafts, session
from mendel_api.settings import model_access

router = APIRouter(prefix="/pipeline/authoring", tags=["authoring"])

_FROZEN = ConfigDict(extra="forbid", frozen=True)


# ── what goes in ──────────────────────────────────────────────────────────────────────────


class BeginAuthoring(BaseModel):
    """What somebody wants, in their own words. **Prose, and nothing else**: a body that took a
    model id would let a browser choose what a provider is sent to."""

    model_config = _FROZEN

    prompt: Prose = Field(min_length=1)


class SayToAuthoring(BaseModel):
    """Words to the agent. **No revision**: saying something changes nothing by itself."""

    model_config = _FROZEN

    text: Prose = Field(min_length=1)


class AnswerQuestion(BaseModel):
    """The person's answer to the agent's question."""

    value: bool | int | float | str


class ReviewAiChoices(BaseModel):
    """The steps whose AI choices the person has looked at, or all of them."""

    nodes: list[str] | Literal["all"]


class EditAuthoringDraft(BaseModel):
    """The canvas as the person left it: the server reads what changed and records it."""

    model_config = _FROZEN

    graph: DraftGraph
    expected_revision: int = Field(ge=0)


class ChangeAuthoring(BaseModel):
    """The person's change to what is wanted, what they have, a fact, a tool or a setting."""

    model_config = _FROZEN

    change: DecisionChange
    expected_decision_revision: int | None = Field(default=None, ge=0)


class CorrectAuthoringFact(BaseModel):
    model_config = _FROZEN

    value: HumanParamValue | list[HumanParamValue] | None = None
    kind: Literal["measurement", "input"] = "measurement"
    expected_decision_revision: int | None = Field(default=None, ge=0)


class ReleaseToolChoice(BaseModel):
    model_config = _FROZEN

    type_id: str
    states: list[str] = Field(default_factory=list)
    expected_decision_revision: int | None = Field(default=None, ge=0)


# ── what comes out ────────────────────────────────────────────────────────────────────────


class AuthoringTurnView(BaseModel):
    model_config = _FROZEN

    seq: int
    role: Literal["person", "assistant"]
    state: TurnState
    text: str
    blocks: list[Block]
    base_revision: int
    at: datetime


class AuthoringUsage(BaseModel):
    """What the session's model calls have cost so far — the header's count (#191)."""

    model_config = _FROZEN

    input: int = 0
    output: int = 0
    cached: int = 0
    calls: int = 0
    in_flight: bool = False


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
    reply_format: str | None = None
    at: datetime


class AuthoringPosition(BaseModel):
    model_config = _FROZEN

    x: int
    y: int


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
    goal: Goal | None
    facts: list[Fact] = []
    samples: list[UploadedSample] = []
    inputs: list[InputDecision] = []
    fact_subjects: list[str] = []
    decision_revision: int = 0
    projection_current: bool = True
    retired: bool = False
    usage: AuthoringUsage = AuthoringUsage()
    revision: int
    graph: DraftGraph
    """The draft as the server holds it — the canvas restores from this."""
    canvas: CanvasFrame | None = None
    show_gap_details: bool = False
    steps_total: int = 0
    placement: dict[str, AuthoringPosition] = {}
    row_version: int
    model_configured: bool
    """Whether this installation has a model at all: the page says the builder needs one."""
    turns: list[AuthoringTurnView]
    working: bool = False
    """Whether the builder agent is answering now."""
    ai_unreviewed: list[AiChoiceView] = []
    """What the AI chose that nobody has reviewed yet, by step."""


class AuthoringStarted(BaseModel):
    model_config = _FROZEN

    session: AuthoringSessionView
    queued: bool
    """`False` when the queue already held this job: the turn will be answered once."""


class AuthoringSaid(BaseModel):
    model_config = _FROZEN

    seq: int
    queued: bool


class AuthoringReviewed(BaseModel):
    model_config = _FROZEN

    ai_unreviewed: list[AiChoiceView]


class AuthoringChanged(BaseModel):
    """The person's change, recorded, and the session as it now is."""

    model_config = _FROZEN

    moved: bool
    session: AuthoringSessionView


class AuthoringEdited(BaseModel):
    model_config = _FROZEN

    revision: int
    session: AuthoringSessionView


class MeasurerView(BaseModel):
    """One way a measurement can be measured, and where that runs (#134)."""

    model_config = _FROZEN

    measurement: str
    by: str
    runs: list[Literal["server", "pipeline"]]
    trusted: bool


class AuthoringVocabulary(BaseModel):
    """Every declared type and its states, and who can measure each measurement."""

    model_config = _FROZEN

    types: dict[str, list[str]]
    names: dict[str, str] = {}
    measurers: list[MeasurerView] = []
    measurements: dict[str, Measurement] = {}
    grains: dict[str, str] = {}
    """Each type's declared grain, `study` or `sample` (issue 494)."""


class AuthoringPreview(BaseModel):
    """The draft as `pipeline.yml` would read — **a preview, never the kept artifact.**"""

    model_config = _FROZEN

    revision: int
    state: Literal["ready", "empty", "illegal", "unavailable", "outdated"]
    text: str
    findings: list[str] = []


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


class InspectedFactView(BaseModel):
    model_config = _FROZEN

    measurement: str
    value: HumanParamValue | list[HumanParamValue] | None = None
    undetermined: str | None = None
    pieces: list[str] = []
    evidence: dict[str, int | float | bool | str] = {}
    coverage: Literal["head", "all"] | None = None


class SampleInspected(BaseModel):
    """What an upload measured, what it recorded, and the agent's turn it starts."""

    model_config = _FROZEN

    outcome: Literal["measured", "unreadable", "no_inspector", "tie"]
    type_id: str | None
    samples: int
    facts: list[InspectedFactView]
    reason: str | None
    steps: list[str]
    recorded: list[str]
    seq: int
    """The agent's turn the upload starts."""


# ── operations ────────────────────────────────────────────────────────────────────────────


@router.post(
    "",
    operation_id="beginAuthoring",
    summary="Describe an analysis; the builder agent starts building it",
    status_code=status.HTTP_201_CREATED,
    responses=REFUSES,
)
async def begin(body: BeginAuthoring) -> AuthoringStarted:
    """An empty draft, a session, the person's words, and the agent's turn queued: the pending
    turn is in the response, so the page shows the agent working at once."""
    session_id, queued = await chat.start(body.prompt, identity.default_author())
    return AuthoringStarted(session=await run_in_threadpool(_view, session_id), queued=queued)


@router.get(
    "/vocabulary",
    operation_id="authoringVocabulary",
    summary="The types a goal may name",
)
def vocabulary() -> AuthoringVocabulary:
    """Declared, public registry data. Registered before `/{session_id}`."""
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
    "/{session_id}/changes",
    operation_id="changeAuthoring",
    summary="Change what you want or what is known about your data",
    responses=REFUSES,
)
def change_authoring(session_id: str, body: ChangeAuthoring) -> AuthoringChanged:
    moved = direct.apply(session_id, body.change, who=identity.default_author(),
                         expected_revision=body.expected_decision_revision)
    return AuthoringChanged(moved=moved, session=_view(session_id))


@router.post(
    "/{session_id}/facts/{subject}",
    operation_id="correctAuthoringFact",
    summary="Correct a fact or an input",
    responses=REFUSES,
)
def correct_fact(session_id: str, subject: str, body: CorrectAuthoringFact) -> AuthoringChanged:
    change = DecisionChange(kind=body.kind, subject=subject, value=body.value)
    moved = direct.apply(session_id, change, who=identity.default_author(),
                         expected_revision=body.expected_decision_revision)
    return AuthoringChanged(moved=moved, session=_view(session_id))


@router.post(
    "/{session_id}/release-tool",
    operation_id="releaseAuthoringTool",
    summary="Let the engine choose a producer again",
    responses=REFUSES,
)
def release_tool(session_id: str, body: ReleaseToolChoice) -> AuthoringChanged:
    change = DecisionChange(kind="pin", subject=body.type_id, states=body.states, retract=True)
    moved = direct.apply(session_id, change, who=identity.default_author(),
                         expected_revision=body.expected_decision_revision)
    return AuthoringChanged(moved=moved, session=_view(session_id))


@router.post(
    "/{session_id}/edits",
    operation_id="editAuthoringDraft",
    summary="Record a direct edit on the canvas",
    responses=REFUSES,
)
def edit(session_id: str, body: EditAuthoringDraft) -> AuthoringEdited:
    """A canvas edit (#395): what it means — a step removed, a tool swapped, a value typed — is
    the person's change at once. A move is layout and writes nothing."""
    revision = direct.edit(session_id, body.graph, who=identity.default_author(),
                           expected_revision=body.expected_revision)
    return AuthoringEdited(revision=revision, session=_view(session_id))


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
    shown = drafts.preview(draft_id, ai=_ai_for(provenance))
    return AuthoringPreview(
        revision=shown.revision, state=shown.state, text=shown.text, findings=shown.findings
    )


_UPLOAD_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["files"],
                    "properties": {
                        "question_id": {"type": "string"},
                        "files": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "minItems": 1,
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
    summary="Upload samples: each measured here, the agent told what they showed",
    responses={**REFUSES, 403: {"description": "`MI0213`: the protection level refuses it."}},
    openapi_extra=_UPLOAD_BODY,
)
async def upload_sample(session_id: str, request: Request) -> SampleInspected:
    """**Only the first 4 MB of each file is kept**, in memory, and nothing is written to disk.
    The protection level is asked before a byte is read. What was measured is recorded as the
    person's data, and the agent is told in the person's next turn."""
    from mendel_api.services import inspect, protection, sample_upload

    if not protection.allows(protection.Crossing.UPLOAD):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            protection.refuse(protection.Crossing.UPLOAD))
    try:
        heads = await sample_upload.read_heads(request, head=inspect.HEAD_BYTES)
    except ValueError as refused:
        raise ValueError(coded("MI0214", str(refused))) from None
    if heads.count < 1:
        raise ValueError(coded("MI0214", "no files: upload one or more samples"))
    sizes = sample_upload.sizes_of(heads.fields.get("sizes"), len(heads.files))
    who = identity.default_author()
    found = await run_in_threadpool(direct.upload, session_id, list(heads.files), sizes, who=who)
    said = (f"I uploaded {found['samples']} sample(s)"
            + (f"; measured {', '.join(found['recorded'])}" if found["recorded"] else "")
            + (f" ({found['reason']})" if found["reason"] else "") + ".")
    seq, _ = await chat.say(session_id, said)
    return SampleInspected(
        outcome=found["outcome"], type_id=found["type_id"], samples=found["samples"],
        facts=[InspectedFactView(**f) for f in found["facts"]], reason=found["reason"],
        steps=found["steps"], recorded=found["recorded"], seq=seq)


# ── helpers ───────────────────────────────────────────────────────────────────────────────


def _ai_for(provenance: DraftProvenance) -> AiProvenance:
    return session.ai_for(provenance)


def _view(session_id: str) -> AuthoringSessionView:
    picture = view.read(session_id)
    return AuthoringSessionView(
        **{k: v for k, v in picture.items() if k not in ("turns", "usage", "graph", "goal")},
        goal=Goal.model_validate(picture["goal"]) if picture["goal"] else None,
        usage=AuthoringUsage(**picture["usage"]),
        graph=DraftGraph.model_validate(picture["graph"] or {}),
        model_configured=model_access("builder", "agent") is not None,
        turns=[AuthoringTurnView(**t) for t in picture["turns"]],
        ai_unreviewed=[AiChoiceView(**m) for m in chat.unreviewed(session_id)],
    )
