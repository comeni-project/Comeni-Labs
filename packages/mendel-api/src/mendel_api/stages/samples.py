"""②a Inside: reading a sample (14.7.6, 14.7.7; plan 1c). The section runs inside its action
(the upload's, or the reading's job); `upload` is the one step the interpreter sees, and its
outcome is the section's way out. Moved from `services/authoring.py`, with the route's sequence."""

import hashlib
import json
from datetime import datetime
from typing import NamedTuple

from comeni_core.diagnostics import coded
from mendel_authoring import commands as c
from mendel_authoring import payloads as p
from mendel_authoring import state as st
from mendel_authoring.decisions import ActorKind
from mendel_authoring.interpret import Refused
from mendel_authoring.types import Command

from mendel_api.authoring.types import (
    CharacteriseReply,
    Fact,
    FactKind,
    FactSource,
    Phase,
    ProposalState,
    SampleReading,
)
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring_decisions, decisions, registry, session
from mendel_api.services.inspect import Inspection
from mendel_api.services.session import Ctx, handles, records
from mendel_api.settings import settings
from mendel_api.stages import _jobs, gathering
from mendel_api.stages._rows import now as _now
from mendel_api.stages._rows import swap as _swap

READS = ("reading_of", "reading_open", "check_sample_question")
"""What a job may read of this stage directly (ruling 2 of plan 1c); every change is a command."""

GAP, UPLOAD = gathering.GAP, gathering.UPLOAD


class SampleAnswer(NamedTuple):
    """What one inspected sample settled, for the card."""

    phase: Phase
    recorded: list[str]
    """Subjects recorded from the sample, as measured."""
    kept: list[str]
    """Subjects the session already knew: what was said stands."""
    disagreed: list[str]
    """Of `kept`, those the sample measured differently. Shown, never written over."""


def _counts(evidence: dict) -> dict[str, int | float]:
    """Numbers only: a file name (`shorter_file`) never enters a fact (spec §9)."""
    return {
        k: v for k, v in evidence.items() if isinstance(v, int | float) and not isinstance(v, bool)
    }


def _sample_refusal(proposal) -> str | None:
    """Why this proposal cannot take a sample now, or `None` (MI0205, then MI0203)."""
    if proposal.kind != GAP or UPLOAD not in proposal.payload["options"]:
        return coded("MI0205", "that question does not take a sample")
    reading = _reading((proposal.payload or {}).get("block") or {}) or {}
    if reading.get("state") == "pending":
        return coded("MI0215", "a sample is already being read for this question")
    return st.settle(
        current=ProposalState(proposal.state),
        proposal_revision=proposal.draft_revision,
        draft_revision=proposal.draft_revision,
        expected_revision=proposal.draft_revision,
        decision=ProposalState.ACCEPTED,
    ).refusal


def check_sample_question(proposal_id: str) -> None:
    """Refuse a sample before it is inspected: a settled gap, or one that takes no sample, is
    told so without its bytes being read (issue 226). `answer_with_sample` asks again, under
    the row's lock, since a second tab may settle it in between."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        refusal = _sample_refusal(proposal)
    if refusal is not None:
        raise ValueError(refusal)


class _Found(NamedTuple):
    """One measurement a sample settled, from an inspector or from a model."""

    measurement: str
    value: object
    pieces: list[str] = []
    evidence: dict | None = None


def _record_found(
    db,
    proposal,
    row,
    *,
    type_id: str | None,
    states: list[str],
    found: list[_Found],
    source: FactSource,
    by: str,
    stack,
    ingestion_key=None,
    current=True,
    invocation_id=None,
) -> tuple[list[str], list[str], list[str], bool]:
    """Record a sample's type and facts as `source`, the person's word standing; settle the
    proposal when its subject was recorded. Returns `(recorded, kept, disagreed, answered)`.

    **An open fact is not known**: *can't share* or *not sure* is nobody's value, and the
    person's own sample settling it is recorded in its place, never reported as disagreeing
    with a value nobody gave (review of #134).
    """
    session_id = proposal.session_id
    subject = proposal.payload["subject"]
    decided = {f.measurement for f in found if f.value is not None}
    facts = [
        f.model_dump(mode="json")
        for f in authoring_decisions.facts(row.draft_id)
        if not (f.source is FactSource.OPEN and f.subject in decided)
    ]
    known = {f["subject"]: f for f in facts}
    recorded, kept, disagreed = [], [], []
    if type_id and current:
        if type_id in known:
            kept.append(type_id)
        else:
            authoring_decisions.record(
                row.draft_id,
                Fact(kind=FactKind.INPUT, subject=type_id, states=sorted(states), source=source),
                who=by,
                proposal_id=proposal.id,
            )
            recorded.append(type_id)
    for item in found:
        if item.value is None:
            continue
        try:
            stack.measurements.check(item.measurement, item.value)
        except (ValueError, KeyError):
            continue
        observation = decisions.observe(
            row.draft_id,
            item.measurement,
            item.value,
            origin=source,
            pieces=item.pieces,
            evidence=gathering._goal_evidence(item.evidence),
            ingestion_key=ingestion_key,
            invocation_id=invocation_id,
        )
        if item.measurement in known:
            kept.append(item.measurement)
            if known[item.measurement].get("value") != item.value:
                disagreed.append(item.measurement)
            if known[item.measurement].get("value") == item.value:
                decisions.acknowledge_observation(
                    row.draft_id,
                    observation,
                    "agreement",
                    who="resolver",
                    actor_kind=ActorKind.RESOLVER,
                )
            continue
        if not current:
            continue
        decisions.select_observation(
            row.draft_id, item.measurement, observation, who=by, proposal_id=proposal.id
        )
        decisions.acknowledge_observation(row.draft_id, observation, "selected", who=by)
        recorded.append(item.measurement)
    answered = subject in recorded
    if answered:
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = by
        proposal.actor_kind = "person"
        proposal.chosen_option = UPLOAD
        proposal.settled_at = _now()
    # A sample that changed nothing leaves the session's version alone, so a click the person
    # made meanwhile is not refused as stale (issue 226).
    if answered or recorded:
        _swap(db, session_id, row.row_version)
    return recorded, kept, disagreed, answered


STALE_AFTER = settings.ai_job_timeout_seconds + 60
"""A reading older than the job could run reads as `no_answer` (ruling 4 of 14.7.7.2's plan):
a worker killed mid-job never writes back, and the card must not wait forever."""


def _reading(block: dict) -> dict | None:
    """The block's reading as it should be read now: a pending one past `STALE_AFTER` is
    `no_answer`. Nothing is written."""
    reading = block.get("reading")
    if not reading or reading.get("state") != "pending" or not reading.get("started_at"):
        return reading
    started = datetime.fromisoformat(reading["started_at"])
    if (_now() - started).total_seconds() > STALE_AFTER:
        return {**reading, "state": "no_answer", "code": "MA0007"}
    return reading


def _aged(payload: dict) -> dict:
    """The payload with a reading the job never finished shown as `no_answer` (nothing written)."""
    block = payload.get("block") or {}
    if not block.get("reading"):
        return payload
    return {**payload, "block": {**block, "reading": _reading(block)}}


def _set_reading(db, proposal, reading: SampleReading | None) -> None:
    payload = dict(proposal.payload)
    block = dict(payload["block"])
    block["reading"] = None if reading is None else reading.model_dump(mode="json")
    payload["block"] = block
    proposal.payload = payload


def reading_of(proposal_id: str) -> SampleReading | None:
    """The question's reading as it should be read now, or `None`."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        found = _reading((proposal.payload or {}).get("block") or {}) if proposal else None
    return None if found is None else SampleReading.model_validate(found)


def start_reading(proposal_id: str) -> int:
    """Mark the question as being read by the AI; the attempt that keys the job."""
    with session_scope() as db:
        proposal = db.get(
            PipelineAuthoringProposal, proposal_id, with_for_update=True, populate_existing=True
        )
        if proposal is None:
            raise KeyError(proposal_id)
        # **Asked again under the lock** (issue 241): a click mid-inspection, or a second upload
        # at the same moment, is refused here rather than queueing a job for a settled question.
        refusal = _sample_refusal(proposal)
        if refusal is not None:
            raise ValueError(refusal)
        before = (proposal.payload.get("block") or {}).get("reading") or {}
        attempt = int(before.get("attempt", 0)) + 1
        _set_reading(
            db,
            proposal,
            SampleReading(
                state="pending",
                attempt=attempt,
                started_at=_now(),
                decision_revision=db.get(
                    PipelineDraft, db.get(PipelineAuthoringSession, proposal.session_id).draft_id
                ).decision_revision,
                session_version=db.get(PipelineAuthoringSession, proposal.session_id).row_version,
            ),
        )
    return attempt


def reading_failed(proposal_id: str, attempt: int, state: str, code: str | None) -> None:
    """End a reading without recording anything, if it is still this attempt's."""
    with session_scope() as db:
        proposal = db.get(
            PipelineAuthoringProposal, proposal_id, with_for_update=True, populate_existing=True
        )
        if proposal is None:
            return
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("attempt") != attempt or reading.get("state") != "pending":
            return
        _set_reading(
            db,
            proposal,
            SampleReading.model_validate({**reading, "state": state, "code": code}),
        )


def end_hand_back(proposal_id: str, *, confirmed: bool) -> None:
    """After the re-sent file was inspected (spec §8): `handed` when its format confirmed it,
    and the recorded type dropped when not, so nothing the AI said stays."""
    with session_scope() as db:
        proposal = db.get(
            PipelineAuthoringProposal, proposal_id, with_for_update=True, populate_existing=True
        )
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("state") != "hand_back":
            return
        _set_reading(
            db,
            proposal,
            SampleReading.model_validate({**reading, "state": "handed"}) if confirmed else None,
        )


def reading_open(proposal_id: str, attempt: int) -> bool:
    """Whether this attempt's reading is still worth a model call: the question is pending and
    the reading is this attempt's, pending (issue 241)."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return False
        reading = _reading((proposal.payload or {}).get("block") or {}) or {}
    return reading.get("attempt") == attempt and reading.get("state") == "pending"


def _pin(proposal_id: str) -> None:
    """Pin the node of the session a sample answers before it records (`session.pin`)."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        session_id = proposal.session_id if proposal is not None else None
    if session_id is not None:
        session.pin(session_id)


def _moves(ctx: Ctx, answered: bool, recorded: list[str], disagreed: list[str], *, late=False):
    """Leave the sample request before asking; late evidence never selects an answer."""
    from mendel_api.stages import correcting

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        continuation = correcting._CONTINUATION.get(Phase(row.phase))
        conflicts = bool(decisions.pending_evidence(row.draft_id))
        if continuation is None:
            return
        arrow = Command.COMPARE_EVIDENCE if late and conflicts else Command.UPLOAD_SAMPLE
        if (late and not conflicts) or not session.allows(row.id, arrow.value):
            return
        if conflicts or (recorded and not answered):
            correcting.stale_proposals(db, row.id)
    payload = p.SampleAnswered(
        answered=answered or bool(recorded), conflicts=conflicts, continuation=continuation
    )
    try:
        session.take(ctx, arrow.value, payload)
    except Refused:
        return
    if recorded and not answered and not conflicts:
        gathering.queue_phrasing(ctx)


def _delivery_key(proposal_id, inspection):
    digest = hashlib.sha256(
        json.dumps(
            inspection.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return f"inspection:{proposal_id}:{digest}"


def record_inspection(
    ctx: Ctx,
    proposal_id: str,
    inspection,
    *,
    by: str,
    expected_decision_revision=None,
    expected_session_version=None,
) -> SampleAnswer:
    """What one inspected sample settles, recorded the way a click records an answer.

    **The person's word stands.** A measurement the session already knows is not overwritten; a
    disagreement is reported back. **An undetermined fact is not recorded**, so if it was the gap
    being answered, the gap stays open with its reason on the card. The proposal is settled only
    when the inspection decided its subject (or, for an input gap, read the type). A gap already
    settled refuses the sample before anything is recorded (MI0203), as a duplicate click does.
    """
    stack = registry.stack()
    _pin(proposal_id)
    with session_scope() as db:
        # **Locked**: two tabs uploading at once take turns here, so the second reads the
        # proposal settled and is refused as a duplicate click (MI0203), not by the version
        # swap below (MI0201, issue 226).
        proposal = db.get(
            PipelineAuthoringProposal, proposal_id, with_for_update=True, populate_existing=True
        )
        if proposal is None:
            raise KeyError(proposal_id)
        captured = expected_decision_revision is not None
        refusal = _sample_refusal(proposal)
        if proposal.kind != GAP or UPLOAD not in proposal.payload["options"]:
            raise ValueError(coded("MI0205", "that question does not take a sample"))
        if refusal is not None and not captured:
            raise ValueError(refusal)

        ctx.session_id = proposal.session_id
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        current = (
            not row.retired
            and proposal.state == ProposalState.PENDING.value
            and (
                expected_decision_revision is None
                or expected_decision_revision == draft.decision_revision
            )
            and (expected_session_version is None or expected_session_version == row.row_version)
        )
        measured = inspection.outcome == "measured"
        found = [
            _Found(f.measurement, f.value, f.pieces, f.evidence)
            for f in (inspection.facts if measured else [])
            if f.undetermined is None
        ]
        recorded, kept, disagreed, answered = _record_found(
            db,
            proposal,
            row,
            type_id=inspection.type_id if measured else None,
            states=[],
            found=found,
            source=FactSource.MEASURED,
            by=by,
            stack=stack,
            current=current,
            ingestion_key=_delivery_key(proposal_id, inspection),
        )
        session_id = proposal.session_id

    _moves(ctx, answered, recorded, disagreed, late=not current)
    return SampleAnswer(
        phase=session.current_phase(session_id), recorded=recorded, kept=kept, disagreed=disagreed
    )


def record_reading(
    ctx: Ctx,
    proposal_id: str,
    attempt: int,
    reply,
    *,
    by: str,
    handed_back: bool,
    expected_decision_revision=None,
    expected_session_version=None,
    invocation_id=None,
) -> SampleAnswer | None:
    """Admitted model evidence survives a late delivery; only its captured context may select."""
    stack = registry.stack()
    _pin(proposal_id)
    with session_scope() as db:
        proposal = db.get(
            PipelineAuthoringProposal, proposal_id, with_for_update=True, populate_existing=True
        )
        if proposal is None:
            return None
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        active_attempt = (
            proposal.state == ProposalState.PENDING.value
            and reading.get("attempt") == attempt
            and reading.get("state") == "pending"
        )
        if not active_attempt and expected_decision_revision is None:
            return None
        if proposal.kind != GAP or UPLOAD not in proposal.payload["options"]:
            raise ValueError(coded("MI0205", "that question does not take a sample"))
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        if expected_decision_revision is None:
            expected_decision_revision = reading.get("decision_revision")
            expected_session_version = reading.get("session_version")
        current = (
            active_attempt
            and not row.retired
            and (
                expected_decision_revision is None
                or expected_decision_revision == draft.decision_revision
            )
            and (expected_session_version is None or expected_session_version == row.row_version)
        )
        if reply.type_id is not None:
            declared = stack.vocabulary.types
            if (
                reply.type_id not in declared
                or not {s.id for s in reply.states} <= declared[reply.type_id]
            ):
                raise ValueError(coded("MI0205", "the model read an undeclared type or state"))
        session_id = ctx.session_id = proposal.session_id
        if handed_back:
            if not current:
                return None
            _set_reading(
                db,
                proposal,
                SampleReading(
                    state="hand_back",
                    attempt=attempt,
                    type_id=reply.type_id,
                    states=[s.id for s in reply.states],
                    decision_revision=expected_decision_revision,
                    session_version=expected_session_version,
                ),
            )
            recorded, kept, disagreed, answered = [], [], [], False
        else:
            found = [_Found(m.id, m.value) for m in reply.measurements]
            recorded, kept, disagreed, answered = _record_found(
                db,
                proposal,
                row,
                type_id=reply.type_id,
                states=[s.id for s in reply.states],
                found=found,
                source=FactSource.MODEL_READ,
                by=by,
                stack=stack,
                current=current,
                ingestion_key=f"reading:{proposal_id}:{attempt}",
                invocation_id=invocation_id,
            )
            if active_attempt:
                _set_reading(
                    db,
                    proposal,
                    SampleReading(
                        state="read",
                        attempt=attempt,
                        type_id=reply.type_id,
                        states=[s.id for s in reply.states],
                        recorded=recorded,
                        kept=kept,
                        disagreed=disagreed,
                        decision_revision=expected_decision_revision,
                        session_version=expected_session_version,
                    ),
                )
    _moves(ctx, answered, recorded, disagreed, late=not current)
    return SampleAnswer(
        phase=session.current_phase(session_id), recorded=recorded, kept=kept, disagreed=disagreed
    )


class Uploaded(NamedTuple):
    """What one upload did: the inspection, and what it settled (`None` while the AI reads)."""

    inspection: Inspection
    answer: SampleAnswer | None
    reading: bool


# ── the commands ─────────────────────────────────────────────────────────────────────────


@records(c.UploadSample)
def _upload(ctx: Ctx, cmd: c.UploadSample) -> Uploaded:
    """The route's sequence, unchanged, inside one action (ruling 8 of plan 1c): refused before a
    byte is inspected (issue 226); a hand-back claims the file by the recorded type only; a type
    nothing here reads is read by the AI, its job ending the reading if it never queues."""
    from mendel_api.services import characterise, inspect

    check_sample_question(cmd.proposal_id)
    reading = reading_of(cmd.proposal_id)
    claimed = reading.type_id if reading is not None and reading.state == "hand_back" else None
    with session_scope() as db:
        owner = db.get(PipelineAuthoringSession, cmd.session_id)
        version = db.get(PipelineDraft, owner.draft_id).decision_revision
        workflow = owner.row_version
    inspection = inspect.inspect_sample(list(cmd.files), registry.stack(), claimed)
    if claimed is not None:
        end_hand_back(cmd.proposal_id, confirmed=inspection.outcome == "measured")
    # **A hand-back never starts another reading** (issue 246): a re-sent file nothing claims,
    # even by the type the AI named, ends here, or the card would re-send it without end.
    if inspection.outcome == "no_inspector" and claimed is None and characterise.available():
        # Nothing here reads its type: the AI reads its first 8 KB of text (14.7.7).
        found = characterise.excerpt(cmd.files[0][1])
        if found is not None:
            attempt = start_reading(cmd.proposal_id)
            captured = reading_of(cmd.proposal_id)
            ctx.queue(
                _jobs.characterise(
                    cmd.session_id,
                    cmd.proposal_id,
                    attempt,
                    found,
                    expires=STALE_AFTER,
                    decision_revision=captured.decision_revision,
                    session_version=captured.session_version,
                    # Never queued (issue 241): the reading ends, rather than locking the
                    # question until it ages out.
                    unqueued=c.ReadingFailed(cmd.proposal_id, attempt, "no_answer", "MA0007"),
                )
            )
            return Uploaded(inspection, None, True)
    answer = record_inspection(
        ctx,
        cmd.proposal_id,
        inspection,
        by=cmd.by,
        expected_decision_revision=version,
        expected_session_version=workflow,
    )
    return Uploaded(inspection, answer, False)


@records(c.SampleInspected)
def _inspected(ctx: Ctx, cmd: c.SampleInspected) -> SampleAnswer:
    inspection = Inspection.model_validate(cmd.inspection)
    return record_inspection(
        ctx,
        cmd.proposal_id,
        inspection,
        by=cmd.by,
        expected_decision_revision=cmd.expected_decision_revision,
        expected_session_version=cmd.expected_session_version,
    )


@records(c.ReadingAnswered)
def _read(ctx: Ctx, cmd: c.ReadingAnswered) -> SampleAnswer | None:
    reply = CharacteriseReply.model_validate(cmd.reply)
    return record_reading(
        ctx,
        cmd.proposal_id,
        cmd.attempt,
        reply,
        by=cmd.by,
        handed_back=cmd.handed_back,
        expected_decision_revision=cmd.expected_decision_revision,
        expected_session_version=cmd.expected_session_version,
        invocation_id=cmd.invocation_id,
    )


@records(c.ReadingFailed)
def _reading_failed(ctx: Ctx, cmd: c.ReadingFailed) -> None:
    reading_failed(cmd.proposal_id, cmd.attempt, cmd.state, cmd.code)


# ── the handler ──────────────────────────────────────────────────────────────────────────


@handles("upload")
def upload(ctx: Ctx) -> str:
    if not isinstance(ctx.payload, p.SampleAnswered):
        raise TypeError("record_sample requires SampleAnswered")
    return "conflicts" if ctx.payload.conflicts else "answered" if ctx.payload.answered else "stays"
