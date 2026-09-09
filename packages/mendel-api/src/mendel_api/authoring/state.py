"""How an authoring session moves, and when a proposal may still be applied.

**Pure.** No database, no clock, no model. A phase and an event in, a phase out; a proposal's
situation in, an outcome out. `services/authoring.py` is what reads rows and writes them, and it
holds none of these rules.

That split is `mendel_forge.workflow`'s, and it is worth restating why it earns its file. The
rules here are the ones that are easy to get right in one caller and wrong in the next: what may
follow what, and whether a decision made a moment ago still applies. Encoded in a service, each
becomes an `if` somebody remembers — and the second caller is where the memory fails.

The phases and the arrows are the living-pipeline plan's §2 state diagram, **transcribed rather
than invented**, so the picture stays the specification.
"""

from enum import StrEnum
from typing import NamedTuple

from comeni_core.diagnostics import coded

from mendel_api.authoring.types import Phase, ProposalState


class Event(StrEnum):
    """What happens to a session.

    One member per labelled arrow in §2's diagram. Named for the *fact* rather than for the
    destination — `GOAL_RETURNED`, not `TO_GOAL_REVIEW` — because the same fact leads somewhere
    different depending on where it arrives: `GOAL_ACCEPTED` reaches `resolving` from
    `goal_review`, from `building` and from `complete`, and naming it for the target would make
    those read as three events.
    """

    GOAL_RETURNED = "goal_returned"
    """A typed goal came back from the model."""
    GOAL_ACCEPTED = "goal_accepted"
    """The person accepted the goal — including a revised one, later in the session."""
    GOAL_REVISED = "goal_revised"
    """The person answered the goal summary in prose instead of accepting it."""
    BLUEPRINT_STORED = "blueprint_stored"
    """The resolver produced a whole blueprint and it was written down (§1.4)."""
    PROPOSAL_SETTLED = "proposal_settled"
    """A proposal was accepted or rejected. `building` loops on itself."""
    NOTHING_LEFT = "nothing_left"
    """The reveal reached the end of the blueprint with no proposal outstanding."""
    PROVIDER_FAILED = "provider_failed"
    """A model call failed or was refused, past retrying."""
    BUILD_FAILED = "build_failed"
    """The resolver could not produce a blueprint."""
    RETRY = "retry"
    """Leave `failed` for whichever phase failed."""


TRANSITIONS: dict[tuple[Phase, Event], Phase] = {
    (Phase.UNDERSTANDING, Event.GOAL_RETURNED): Phase.GOAL_REVIEW,
    (Phase.UNDERSTANDING, Event.PROVIDER_FAILED): Phase.FAILED,
    (Phase.GOAL_REVIEW, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.GOAL_REVIEW, Event.GOAL_REVISED): Phase.UNDERSTANDING,
    (Phase.RESOLVING, Event.BLUEPRINT_STORED): Phase.BUILDING,
    (Phase.RESOLVING, Event.BUILD_FAILED): Phase.FAILED,
    (Phase.RESOLVING, Event.PROVIDER_FAILED): Phase.FAILED,
    (Phase.BUILDING, Event.PROPOSAL_SETTLED): Phase.BUILDING,
    (Phase.BUILDING, Event.NOTHING_LEFT): Phase.COMPLETE,
    (Phase.BUILDING, Event.GOAL_ACCEPTED): Phase.RESOLVING,
    (Phase.COMPLETE, Event.GOAL_ACCEPTED): Phase.RESOLVING,
}
"""Every legal move, as one closed table.

**`failed` is deliberately not a source here.** Leaving it needs a second input — which phase
failed — so `advance` handles `RETRY` before consulting this table rather than encoding two
different destinations under one key.

`building --> building` on `PROPOSAL_SETTLED` is a real arrow and not a no-op: it is what makes
answering a proposal legal at all, and its absence would refuse every acceptance.
"""

RETRY_FALLBACK = Phase.UNDERSTANDING
"""Where a retry resumes when nothing recorded which phase failed.

**The safe reading**, and the same one `workflow.retry_target` takes: an unrecorded stage costs
one extra model call and cannot skip a step. Guessing `resolving` would resume a build against a
goal that may never have been confirmed.
"""


def advance(phase: Phase, event: Event, failed_from: Phase | None = None) -> Phase:
    """The phase after `event`, or a coded refusal.

    Raises rather than returns, unlike `workflow.refuse` next door, and the difference is what
    the caller holds. The forge's caller has already read a row and needs to record an event and
    roll back, so it wants a message. Here every caller is inside one transaction that should
    not commit at all if the move was illegal, and an exception is what makes forgetting to check
    impossible rather than merely visible.
    """
    if event is Event.RETRY:
        if phase is not Phase.FAILED:
            raise ValueError(_refusal(phase, event))
        return failed_from or RETRY_FALLBACK

    try:
        return TRANSITIONS[(phase, event)]
    except KeyError:
        raise ValueError(_refusal(phase, event)) from None


def _refusal(phase: Phase, event: Event) -> str:
    """Names what *can* happen, so the recovery is one request rather than a guess."""
    onward = sorted(e.value for (source, e) in TRANSITIONS if source is phase)
    if phase is Phase.FAILED:
        onward = [Event.RETRY.value]
    return coded("MI0200", f"a session in {phase.value} cannot handle {event.value}") + (
        f"\n  from {phase.value} it can handle: {', '.join(onward) or '(nothing)'}"
    )


def failed_from(phase: Phase) -> Phase:
    """The value to record in `failed_from` when `phase` fails.

    Trivial today and named anyway: the column is only useful if it is written, and a service
    writing `session.phase` directly would be correct by accident until the day a failure is
    recorded one transition after it happened.
    """
    return phase


class Settlement(NamedTuple):
    """What may be done about a proposal, and what to record.

    A `NamedTuple` rather than three return values, because `applies` and `state` are read
    together and a caller that reads one without the other is the bug this type prevents:
    writing `state` while ignoring `applies` is exactly how a stale proposal gets applied.
    """

    state: ProposalState
    """What the proposal's state should be afterwards. Unchanged when the request is refused."""
    applies: bool
    """Whether the caller may act on the draft. **Never true for a stale or conflicting one.**"""
    refusal: str | None
    """The coded refusal to answer with, or `None` when the settlement stands.

    **A `coded()` message, not a bare code.** It was the bare code for one commit, and
    `test_every_declared_code_is_emitted` caught what that meant: `MI0202` was declared, appeared
    in the generated diagnostics page, answered `mendel explain` — and no code path could ever
    produce it, because the string was assembled by hand. A caller holding only `"MI0202"` has to
    write the sentence itself, which is how two transports come to explain one refusal
    differently."""
    bumps_revision: bool
    """Whether the draft's revision moves. Only an acceptance changes the pipeline."""


def settle(
    *,
    current: ProposalState,
    proposal_revision: int,
    draft_revision: int,
    expected_revision: int,
    decision: ProposalState,
) -> Settlement:
    """Whether a proposal may still be settled, and how.

    Three questions in one place, in the order that makes each answer unambiguous:

    1. **Has it already been settled?** A duplicate delivery — a retried request, a double click
       — must get the same answer rather than a second effect (`MI0203`).
    2. **Was the client looking at the current draft?** `expected_revision` is compared against a
       number the client was *shown*. Not a timestamp: two writes inside one clock tick are
       indistinguishable by time, which is precisely when this matters (`MI0201`).
    3. **Was the proposal made about the current draft?** If the draft moved after the proposal
       was offered, applying it writes a decision made about a pipeline that no longer looks that
       way. It becomes `stale` — **not** `rejected`, because nobody rejected it (`MI0202`).

    Order matters between 2 and 3. A client on an older view *and* a proposal from an older
    revision is reported as the conflict, because that is the one the person can act on: re-read
    and try again. Telling them their proposal went stale when their whole view is behind sends
    them to fix the wrong thing.
    """
    if decision not in (ProposalState.ACCEPTED, ProposalState.REJECTED):
        raise ValueError(f"a proposal settles to accepted or rejected, not {decision.value}")

    if current is not ProposalState.PENDING:
        return Settlement(
            current,
            False,
            coded("MI0203", "this proposal has already been settled")
            + f"\n  it is {current.value}",
            False,
        )

    if expected_revision != draft_revision:
        return Settlement(
            current,
            False,
            coded("MI0201", "this draft moved while you were looking at it")
            + f"\n  you expected revision {expected_revision}; it is at {draft_revision}"
            + "\n  re-read it before accepting",
            False,
        )

    if proposal_revision != draft_revision:
        return Settlement(
            ProposalState.STALE,
            False,
            coded("MI0202", "this proposal was made against an older draft")
            + f"\n  it was offered at revision {proposal_revision}; the draft is at "
            + f"{draft_revision}"
            + "\n  nothing was applied, and it is now marked stale",
            False,
        )

    return Settlement(decision, True, None, decision is ProposalState.ACCEPTED)
