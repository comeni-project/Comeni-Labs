"""Answering a question."""

from typing import Any

from mendel_forge import ops
from pydantic import BaseModel

from mendel_api.identity import default_author
from mendel_api.settings import settings


class RefusedDraft(BaseModel):
    draft: str
    detail: str
    """The coded refusal, as the forge wrote it. `forge explain <code>` expands it."""


class AnsweredAll(BaseModel):
    subject: str
    settled: list[str]
    refused: list[RefusedDraft]
    """Empty means nothing refused. **Never omitted** — a caller must not have to infer that
    a partial write happened from the length of `settled`."""


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


def answer_all(*, subject: str, value: Any, why: str, by: str | None) -> AnsweredAll:
    """Settle one question on every draft that asks it.

    **Best-effort, and every refusal is reported** — spec §3.1. The design's worked example is
    a batch with one wrong member (`samtools/faidx` takes a FASTA), and all-or-nothing would
    block the others exactly when the throughput move is most useful.

    **Atomic per draft** comes free: `ops.fill` writes a whole draft or raises.

    Sorted by draft name, because workspace order is directory order and directory order moves
    under a refactor nobody asked for.
    """
    if not why.strip():
        raise ValueError("an answer needs a reason: every value carries one a reader can act on")

    author = by or default_author()
    settled: list[str] = []
    refused: list[RefusedDraft] = []

    for name in sorted(ops.list_(ops.ListRequest(workspace_root=settings.workspace_root)).names):
        shown = ops.show(
            ops.ShowRequest(
                name=name,
                registry_root=settings.registry_root,
                source_root=settings.source_root,
                workspace_root=settings.workspace_root,
            )
        )
        if not any(h.subject == subject for h in shown.holes):
            continue
        try:
            ops.fill(
                ops.FillRequest(
                    name=name,
                    field=subject,
                    value=value,
                    by=author,
                    why=why,
                    workspace_root=settings.workspace_root,
                )
            )
        except ValueError as refusal:
            refused.append(RefusedDraft(draft=name, detail=str(refusal)))
        else:
            settled.append(name)

    return AnsweredAll(subject=subject, settled=settled, refused=refused)
