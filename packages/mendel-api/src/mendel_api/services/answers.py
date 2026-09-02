"""Answering a question."""

from typing import Any

from mendel_forge import ops
from mendel_forge.scaffold import Decision
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
                source_root=settings.registry_root,
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


class Proposed(BaseModel):
    draft: str
    subject: str
    still_open: bool
    """**Always `True`.** A proposal is not a fill — the hole stays open, `is_complete()` is
    still false and `land` still refuses. It is a field rather than a comment because the UI
    must not render a declined question as settled."""


def propose_one(
    *, draft: str, subject: str, id: str, description: str, why: str, by: str | None
) -> Proposed:
    """Record that nothing declared fits — invariant 7's escape hatch.

    A closed choice with no way to decline forces a wrong answer, which is the defect
    `docs/notes/specs/2026-08-17-vocabulary-proposals.md` was written about.
    """
    if not why.strip():
        raise ValueError("a proposal needs a reason: a reviewer has only this to judge by")
    if not description.strip():
        raise ValueError("a proposal needs a description: an id alone is a name nobody can review")

    result = ops.propose(
        ops.ProposeRequest(
            name=draft,
            field=subject,
            id=id,
            description=description,
            why=why,
            by=by or default_author(),
            workspace_root=settings.workspace_root,
        )
    )
    return Proposed(draft=result.name, subject=result.field, still_open=True)


class Decided(BaseModel):
    draft: str
    subject: str
    value: str | None
    still_open: bool
    """`True` after a rejection — the hole reopened and the row stays. Same field and same
    argument as `Proposed.still_open`: the UI must not remove a row that is still work."""


def decide_proposal(
    *, draft: str, subject: str, decision: Decision, id: str | None, why: str, by: str | None
) -> Decided:
    """Approve or reject a proposal.

    A **rename is approve-with-a-different-id**, not a third verb: they differ only in what
    gets written, and two endpoints would let them drift apart.
    """
    if not why.strip():
        raise ValueError("a decision needs a reason: the next reviewer has only this to read")

    result = ops.decide(
        ops.DecideRequest(
            name=draft,
            field=subject,
            decision=decision,
            id=id,
            why=why,
            by=by or default_author(),
            workspace_root=settings.workspace_root,
        )
    )
    return Decided(
        draft=result.name,
        subject=result.field,
        value=result.value,
        still_open=result.value is None,
    )
