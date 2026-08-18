"""`/questions` — the one surface React and an agent share."""

from typing import Any

from fastapi import APIRouter
from mendel_forge import ops
from pydantic import BaseModel

from mendel_api.questions import OpenQuestion, aggregate, question_from_hole
from mendel_api.refusals import REFUSES
from mendel_api.services.answers import Answered, answer_one
from mendel_api.settings import settings

router = APIRouter(tags=["questions"])


class QueueResponse(BaseModel):
    questions: list[OpenQuestion]
    total: int
    """Before aggregation. The list is short because rows collapse; the count must not be,
    or the queue understates how much work is open."""


@router.get(
    "/questions",
    operation_id="listQuestions",
    summary="Every open question, collapsed",
)
def queue() -> QueueResponse:
    """Every open question in the workspace, collapsed.

    `show` needs the registry and the source as well as the workspace: a hole's candidates
    are recomputed from the layer stack rather than stored, so a draft cannot be read
    without the registry it was drafted against.
    """
    names = ops.list_(ops.ListRequest(workspace_root=settings.workspace_root)).names
    found: list[OpenQuestion] = []
    for name in names:
        shown = ops.show(
            ops.ShowRequest(
                name=name,
                registry_root=settings.registry_root,
                source_root=settings.source_root,
                workspace_root=settings.workspace_root,
            )
        )
        found += [question_from_hole(h, draft=name) for h in shown.holes]
    return QueueResponse(questions=aggregate(found), total=len(found))


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
