"""`/questions` — the one surface React and an agent share."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from mendel_forge.scaffold import Decision
from pydantic import BaseModel

from mendel_api.questions import Band
from mendel_api.refusals import REFUSES
from mendel_api.services.answers import (
    Answered,
    AnsweredAll,
    Decided,
    Proposed,
    answer_all,
    answer_one,
    decide_proposal,
    propose_one,
)
from mendel_api.services.queue import Grouping, Ordering, QueueResponse
from mendel_api.services.queue import read as queue_read
from mendel_api.services.visits import mark as mark_visited

router = APIRouter(tags=["questions"])


@router.get(
    "/questions",
    operation_id="listQuestions",
    summary="Every open question, filtered, ordered and collapsed",
)
def queue(
    # `Annotated` rather than `Query(...)` as a default: it is FastAPI's current idiom and
    # it keeps the default a value, which is what `B008` is about — a call in a default is
    # evaluated once at import and shared.
    band: Annotated[Band | None, Query(description="Only this band.")] = None,
    group: Annotated[
        Grouping, Query(description="One row per question, or per draft.")
    ] = Grouping.QUESTION,
    sort: Annotated[
        Ordering, Query(description="Worst-to-get-wrong, or newest.")
    ] = Ordering.CONSEQUENCE,
    since_last_visit: Annotated[
        bool, Query(description="Only what moved since you last looked.")
    ] = False,
) -> QueueResponse:
    """The queue.

    **Every control is a query parameter and none of them is a header or a body**, because a
    curator who finds a bad answer must be able to send somebody the link to the screen they
    were looking at — spec §4.1.
    """
    return queue_read(band=band, group=group, sort=sort, since_last_visit=since_last_visit)


class Visited(BaseModel):
    seen_at: datetime


@router.post(
    "/visits",
    operation_id="markVisited",
    summary="Mark now as seen, for the since-last-visit filter",
    responses=REFUSES,
)
def visit() -> Visited:
    """**Deliberately not a side effect of reading the queue.** If a GET stamped a visit, the
    next GET would have a baseline of a moment ago and *what changed since I last looked*
    would be permanently empty — right once, then wrong forever.
    """
    return Visited(seen_at=mark_visited(None))


class AnswerRequest(BaseModel):
    draft: str
    subject: str
    value: Any
    why: str
    by: str | None = None
    """Absent means "whoever git says I am". Present means somebody typed a name."""


@router.post(
    "/questions/answer",
    operation_id="answerQuestion",
    summary="Settle one question on one draft",
    responses=REFUSES,
)
def answer(req: AnswerRequest) -> Answered:
    """Settle one question. Three lines, because the logic is a service.

    **No `try`.** A `ValueError` from below carries a coded refusal — `MF0002`, `MF0003`, or
    the reason check — and `create_app` turns it into a 422 for every route at once, exactly
    as `mendel_forge.http` does. Catching it here would be a second spelling of one contract,
    and the second spelling is the one that drifts.
    """
    return answer_one(
        draft=req.draft, subject=req.subject, value=req.value, why=req.why, by=req.by
    )


class AnswerAllRequest(BaseModel):
    subject: str
    value: Any
    why: str
    by: str | None = None


@router.post(
    "/questions/answer-all",
    operation_id="answerAll",
    summary="Settle one question on every draft that asks it",
    responses=REFUSES,
)
def answer_every(req: AnswerAllRequest) -> AnsweredAll:
    """**A partial batch is a 200, not a 207 and not a 422.** The operation did what it was
    asked and is reporting what it found; the refusals are in the body with their codes.
    A 207 is a status no generated client models usefully.
    """
    return answer_all(subject=req.subject, value=req.value, why=req.why, by=req.by)


class ProposeRequest(BaseModel):
    draft: str
    subject: str
    id: str
    description: str
    why: str
    by: str | None = None


@router.post(
    "/questions/propose",
    operation_id="proposeType",
    summary="Decline a question — nothing declared fits",
    responses=REFUSES,
)
def propose(req: ProposeRequest) -> Proposed:
    """Invariant 7's escape hatch. The hole stays open; `still_open` says so in the payload."""
    return propose_one(
        draft=req.draft,
        subject=req.subject,
        id=req.id,
        description=req.description,
        why=req.why,
        by=req.by,
    )


class DecideRequest(BaseModel):
    draft: str
    subject: str
    decision: Decision
    why: str
    id: str | None = None
    by: str | None = None


@router.post(
    "/questions/proposals/decide",
    operation_id="decideProposal",
    summary="Approve, rename or reject a proposal",
    responses=REFUSES,
)
def decide(req: DecideRequest) -> Decided:
    """One route, not two. Approve and reject are one decision with a value, and separate
    endpoints would let them drift apart."""
    return decide_proposal(
        draft=req.draft,
        subject=req.subject,
        decision=req.decision,
        id=req.id,
        why=req.why,
        by=req.by,
    )
