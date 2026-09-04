"""The only module that moves an adaptation.

**Which transitions are legal is `mendel_forge.workflow`'s; performing one is this module's.**
That split exists because CI has no Postgres: the rules are checked by a suite that always runs,
and what is here is the storage, tested where a database is available and skipped where it is
not. `services/visits.py` records the same split for the same reason.

**Every transition is one `UPDATE … WHERE id AND state AND row_version`, and the row count is
the answer.** Read-then-write would leave a window between the check and the write, and the
window is not theoretical: a reviewer with the candidate and the diff open in two tabs is the
ordinary case, and two workers claiming one queued job is what ARQ's at-least-once delivery
produces on any redeploy. A compare-and-swap has no window, so the loser is told rather than
overwriting the winner.

**Nothing here writes to a registry.** Approval moves an adaptation to `publishing`; `land.py`
is what turns a candidate into files, and it stays the only thing that does — invariant 2.
"""

import secrets
from datetime import UTC, datetime

from comeni_core.diagnostics import coded
from mendel_forge.workflow import (
    ALLOWED,
    TERMINAL,
    AdaptationState,
    EventKind,
    RevisionState,
    approval_refusals,
    refuse,
    retry_target,
)
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from mendel_api.db import session_scope
from mendel_api.models import ForgeAdaptation, ForgeCatalogueItem, ForgeEvent, ForgeRevision


class Moved(BaseModel):
    """What a caller needs after a successful transition, and nothing more.

    The new `row_version` in particular: a browser that transitions twice without re-reading
    would otherwise send a stale version on the second call and be refused for the wrong
    reason — told the row moved under it when it is the one that moved it.
    """

    id: str
    state: AdaptationState
    row_version: int


def _now() -> datetime:
    return datetime.now(UTC)


def _record(
    session: Session,
    adaptation_id: str,
    kind: EventKind,
    *,
    actor: str,
    detail: str = "",
    revision_id: str | None = None,
) -> None:
    """Append an event. **Public detail only** — see `models.ForgeEvent`."""
    session.add(
        ForgeEvent(
            adaptation_id=adaptation_id,
            revision_id=revision_id,
            kind=kind.value,
            detail=detail,
            actor=actor,
            at=_now(),
        )
    )


def begin(catalogue_item_id: str, *, who: str) -> str:
    """Start adapting one catalogue item. Returns the adaptation id.

    **Refuses when an active adaptation already exists**, which is the service half of a rule
    the partial unique index also enforces. Two mechanisms, and they are not the redundancy
    `SourceSnapshot.classified` was: this one produces a sentence naming the adaptation already
    in flight, and the index is the only one that holds when two requests arrive together.
    Deleting either leaves a real defect, which is the test of whether a second mechanism is
    earning its place.
    """
    with session_scope() as session:
        if session.get(ForgeCatalogueItem, catalogue_item_id) is None:
            raise KeyError(catalogue_item_id)

        active = session.scalars(
            select(ForgeAdaptation).where(
                ForgeAdaptation.catalogue_item_id == catalogue_item_id,
                ForgeAdaptation.state.not_in([s.value for s in TERMINAL]),
            )
        ).first()
        if active is not None:
            raise ValueError(
                coded("MI0101", "this tool is already being adapted")
                + f"\n  adaptation {active.id} is in {active.state}"
                + "\n  archive it, or finish it, before starting another"
            )

        adaptation_id = secrets.token_hex(16)
        session.add(
            ForgeAdaptation(
                id=adaptation_id,
                catalogue_item_id=catalogue_item_id,
                state=AdaptationState.SCAFFOLDING.value,
                row_version=1,
                who=who,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        _record(session, adaptation_id, EventKind.CREATED, actor=who)
    return adaptation_id


def move(
    adaptation_id: str,
    target: AdaptationState,
    *,
    expect: AdaptationState,
    row_version: int,
    actor: str,
    kind: EventKind,
    detail: str = "",
    revision_id: str | None = None,
    failed_stage: AdaptationState | None = None,
) -> Moved:
    """The one transition. Every other verb in this module calls it.

    `expect` and `row_version` are both compared, and both are load-bearing for different
    mistakes: `expect` catches acting on a state the caller has misread, and `row_version`
    catches acting on a state that happens to match but has moved through it and back — a
    `review` a request-changes cycle already left and returned to.
    """
    illegal = refuse(expect, target)
    if illegal is not None:
        raise ValueError(illegal)

    with session_scope() as session:
        values: dict[str, object] = {
            "state": target.value,
            "row_version": row_version + 1,
            "updated_at": _now(),
        }
        if revision_id is not None:
            values["current_revision_id"] = revision_id
        # Cleared on every transition that is not *into* failure, so a retried adaptation does
        # not carry the stage of a failure it has already recovered from. A stale
        # `failed_stage` sends the next retry to the wrong place, which is rule 9 inverted.
        values["failed_stage"] = failed_stage.value if failed_stage is not None else None

        done = session.execute(
            update(ForgeAdaptation)
            .where(
                ForgeAdaptation.id == adaptation_id,
                ForgeAdaptation.state == expect.value,
                ForgeAdaptation.row_version == row_version,
            )
            .values(**values)
        )
        if done.rowcount != 1:
            row = session.get(ForgeAdaptation, adaptation_id)
            if row is None:
                raise KeyError(adaptation_id)
            raise ValueError(
                coded("MI0100", "this adaptation moved while you were looking at it")
                + f"\n  you expected {expect} at version {row_version}"
                + f"\n  it is {row.state} at version {row.row_version}"
                + "\n  re-read it before acting on it"
            )
        _record(session, adaptation_id, kind, actor=actor, detail=detail, revision_id=revision_id)

    return Moved(id=adaptation_id, state=target, row_version=row_version + 1)


def claim(adaptation_id: str, *, row_version: int, worker: str) -> Moved:
    """A worker takes a queued job.

    **Safe to call twice with the same job id**, which ARQ requires — the second call finds the
    row already at `generating` with a bumped version and is refused with `MI0100` rather than
    starting a second model call. That is the whole of what "idempotent" buys here: the duplicate
    is told, not served.
    """
    return move(
        adaptation_id,
        AdaptationState.GENERATING,
        expect=AdaptationState.QUEUED,
        row_version=row_version,
        actor=worker,
        kind=EventKind.CLAIMED,
    )


def fail(
    adaptation_id: str, *, stage: AdaptationState, row_version: int, actor: str, detail: str
) -> Moved:
    """Record a failure and where it happened.

    `stage` is what retry reads. A scaffold that could not be built is not repaired by queueing
    a model, and without this column every retry assumes it was the model's fault.
    """
    return move(
        adaptation_id,
        AdaptationState.FAILED,
        expect=stage,
        row_version=row_version,
        actor=actor,
        kind=EventKind.FAILED,
        detail=detail,
        failed_stage=stage,
    )


def retry(adaptation_id: str, *, row_version: int, actor: str) -> Moved:
    """Resume the stage that failed, not the one a single arrow would have picked."""
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        stage = AdaptationState(row.failed_stage) if row.failed_stage else None
    target = retry_target(stage)
    return move(
        adaptation_id,
        target,
        expect=AdaptationState.FAILED,
        row_version=row_version,
        actor=actor,
        kind=EventKind.RETRIED,
        detail=f"resuming at {target}",
    )


def request_changes(adaptation_id: str, *, row_version: int, who: str, reason: str) -> Moved:
    """Not rejection — the plan's word, and the reason it is not `reject` is that a terminal
    word makes an ordinary correction feel destructive. The candidate being corrected is kept.

    A reason is required. A revision queued with no reason is one the next reviewer cannot
    read, and the model cannot act on either.
    """
    if not reason.strip():
        raise ValueError(
            coded("MF0301", "requesting changes needs a reason")
            + "\n  it is what the next attempt is given, and what the next reviewer reads"
        )
    return move(
        adaptation_id,
        AdaptationState.CHANGES_REQUESTED,
        expect=AdaptationState.REVIEW,
        row_version=row_version,
        actor=who,
        kind=EventKind.CHANGES_REQUESTED,
        detail=reason,
    )


def approve(
    adaptation_id: str, *, row_version: int, who: str, reason: str, registry_digest_now: str
) -> Moved:
    """Move to `publishing`, once every condition holds.

    **This does not publish.** It records that a named human approved, and hands the adaptation
    to the one thing that writes files. Splitting the decision from the write is what keeps
    invariant 2 checkable: a person approves here, `land.py` writes there, and neither can do
    the other's job.
    """
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        revision = (
            session.get(ForgeRevision, row.current_revision_id)
            if row.current_revision_id
            else None
        )
        refusals = approval_refusals(
            revision_id=row.current_revision_id,
            revision_state=RevisionState(revision.state) if revision else None,
            unresolved_required=revision.unresolved_required if revision else 0,
            validation_green=bool(revision and revision.green),
            who=who,
            reason=reason,
            registry_digest_at_validation=row.registry_digest,
            registry_digest_now=registry_digest_now,
        )
    if refusals:
        raise ValueError("\n".join(refusals))

    return move(
        adaptation_id,
        AdaptationState.PUBLISHING,
        expect=AdaptationState.REVIEW,
        row_version=row_version,
        actor=who,
        kind=EventKind.APPROVED,
        detail=reason,
    )


def archive(adaptation_id: str, *, row_version: int, who: str, reason: str) -> Moved:
    return move(
        adaptation_id,
        AdaptationState.ARCHIVED,
        expect=AdaptationState.REVIEW,
        row_version=row_version,
        actor=who,
        kind=EventKind.ARCHIVED,
        detail=reason,
    )


def add_revision(
    adaptation_id: str,
    *,
    state: RevisionState,
    manifest: dict,
    parent_revision_id: str | None = None,
    prompt_versions: dict | None = None,
) -> str:
    """Write the next revision and make it current.

    The ordinal is derived from what is already stored rather than passed in: a caller that
    computes it has read the table, and between that read and this write another revision can
    land. The unique index on `(adaptation_id, ordinal)` is what turns that race into a
    refusal instead of two revisions both called 2.
    """
    with session_scope() as session:
        if session.get(ForgeAdaptation, adaptation_id) is None:
            raise KeyError(adaptation_id)
        ordinals = session.scalars(
            select(ForgeRevision.ordinal).where(ForgeRevision.adaptation_id == adaptation_id)
        ).all()
        revision_id = secrets.token_hex(16)
        session.add(
            ForgeRevision(
                id=revision_id,
                adaptation_id=adaptation_id,
                ordinal=max(ordinals, default=0) + 1,
                parent_revision_id=parent_revision_id,
                state=state.value,
                manifest=manifest,
                validation={},
                green=False,
                unresolved_required=0,
                prompt_versions=prompt_versions or {},
                created_at=_now(),
            )
        )
        session.execute(
            update(ForgeAdaptation)
            .where(ForgeAdaptation.id == adaptation_id)
            .values(current_revision_id=revision_id, updated_at=_now())
        )
    return revision_id


def stale(older_than: datetime) -> list[str]:
    """Adaptations a worker claimed and never finished.

    Rule 7 — a failed or lost job must not leave a row in `generating` forever. This reports;
    the caller decides, because "the worker died" and "the model is slow" look identical from
    here and only the caller knows what the timeout should be.
    """
    running = [s.value for s in (AdaptationState.GENERATING, AdaptationState.VALIDATING)]
    with session_scope() as session:
        return list(
            session.scalars(
                select(ForgeAdaptation.id).where(
                    ForgeAdaptation.state.in_(running),
                    ForgeAdaptation.updated_at < older_than,
                )
            ).all()
        )


def onward(state: AdaptationState) -> list[AdaptationState]:
    """What this adaptation could become next.

    Served to the browser so the page draws the buttons the server would accept, rather than
    every button plus a refusal. The list is `workflow.ALLOWED`'s, not a second copy of it —
    a page and a service with independent ideas of what is legal is how a disabled button and
    a working endpoint end up disagreeing.
    """
    return sorted(ALLOWED[state])
