"""`/questions` — the one surface React and an agent share."""

from fastapi import APIRouter
from mendel_forge import ops
from pydantic import BaseModel

from mendel_api.questions import OpenQuestion, aggregate, question_from_hole
from mendel_api.settings import settings

router = APIRouter()


class QueueResponse(BaseModel):
    questions: list[OpenQuestion]
    total: int
    """Before aggregation. The list is short because rows collapse; the count must not be,
    or the queue understates how much work is open."""


@router.get("/questions")
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
