"""Answering a question."""

from typing import Any

from mendel_forge import ops
from pydantic import BaseModel

from mendel_api.identity import default_author
from mendel_api.settings import settings


class Answered(BaseModel):
    draft: str
    subject: str
    remaining: list[str]
    """What is still open on that draft. The UI needs it to know whether the draft can land."""


def answer_one(*, draft: str, subject: str, value: Any, why: str, by: str | None) -> Answered:
    """Settle one field on one draft.

    **`subject` becomes `field`.** `OpenQuestion.subject` and `FillRequest.field` are the same
    thing under two names, and this is the one place they meet: letting `subject` leak into the
    forge, or `field` into the API, would make one of the two vocabularies wrong everywhere.

    **A refusal is not swallowed.** `ops.fill` raises `ValueError` carrying a coded message —
    `MF0002` for a field that is not a hole, `MF0003` for a value the hole refuses. The route
    turns that into a 422 with the code intact, because the code is what tells a user what to
    do and `forge explain` is what expands it.
    """
    if not why.strip():
        raise ValueError("an answer needs a reason: every value carries one a reader can act on")

    result = ops.fill(
        ops.FillRequest(
            name=draft,
            field=subject,
            value=value,
            by=by or default_author(),
            why=why,
            workspace_root=settings.workspace_root,
        )
    )
    return Answered(draft=result.name, subject=result.field, remaining=result.remaining)
