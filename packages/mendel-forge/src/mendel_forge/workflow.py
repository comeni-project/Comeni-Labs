"""What can happen to an adaptation, and in what order.

**The transition table lives here rather than in the service that applies it**, because the
service needs a database and the rules do not. `mendel-api`'s DB tests skip when Postgres is
unreachable — CI has none — so a rule that only existed inside `services/forge_state.py` would
be a rule CI never checks. `services/forge_state.py` is the one module that *performs* a
transition; this is the one module that says which are legal.

**Two places where the plan's prose and its diagram disagree, resolved in favour of the prose
and written down rather than absorbed:**

- The diagram draws `failed --> queued`. Rule 9 says a failed adaptation records `failed_stage`
  and *retry resumes that stage*, which a single target cannot express: a scaffold that could
  not be built is not repaired by queueing a model. `retry_target` is that rule, and `SCAFFOLDING`
  joins `QUEUED` as a successor of `FAILED`.
- The diagram draws `archived` only out of `review`. A permanently failed adaptation — the tool
  was deleted upstream — is then retryable forever and closeable never. **That is left as drawn**,
  because widening a state machine is cheap later and narrowing one is not, and because
  §1.6 makes archiving a deliberate product act rather than a cleanup. It is a real gap.
"""

from enum import StrEnum

from comeni_core.diagnostics import coded


class AdaptationState(StrEnum):
    """Where one tool's adaptation has got to.

    A plain string column in Postgres rather than a native enum, for the reason
    `models.GateRun.state` already records: adding a member to a Postgres enum is a migration,
    and this class is already the closed vocabulary that matters.
    """

    SCAFFOLDING = "scaffolding"
    QUEUED = "queued"
    GENERATING = "generating"
    VALIDATING = "validating"
    REVIEW = "review"
    CHANGES_REQUESTED = "changes_requested"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


ALLOWED: dict[AdaptationState, frozenset[AdaptationState]] = {
    AdaptationState.SCAFFOLDING: frozenset({AdaptationState.QUEUED, AdaptationState.FAILED}),
    AdaptationState.QUEUED: frozenset({AdaptationState.GENERATING}),
    AdaptationState.GENERATING: frozenset({AdaptationState.VALIDATING, AdaptationState.FAILED}),
    AdaptationState.VALIDATING: frozenset({AdaptationState.REVIEW}),
    AdaptationState.REVIEW: frozenset(
        {
            AdaptationState.CHANGES_REQUESTED,
            AdaptationState.PUBLISHING,
            AdaptationState.ARCHIVED,
        }
    ),
    AdaptationState.CHANGES_REQUESTED: frozenset(
        {AdaptationState.GENERATING, AdaptationState.FAILED}
    ),
    AdaptationState.PUBLISHING: frozenset({AdaptationState.PUBLISHED, AdaptationState.REVIEW}),
    AdaptationState.PUBLISHED: frozenset(),
    AdaptationState.FAILED: frozenset({AdaptationState.QUEUED, AdaptationState.SCAFFOLDING}),
    AdaptationState.ARCHIVED: frozenset(),
}
"""Successors, by current state. Every member of `AdaptationState` is a key — a state missing
from this table would be one nothing could ever leave, which is a typo rather than a decision,
so `test_every_state_is_in_the_table` is what makes the omission fail."""

TERMINAL = frozenset(state for state, onward in ALLOWED.items() if not onward)
"""`published` and `archived`. Derived rather than listed: a second literal list is a second
answer to the same question, and the two drift."""

RUNNING = frozenset({AdaptationState.GENERATING, AdaptationState.VALIDATING})
"""States a *worker* holds. Rule 7 — a lost job must not leave a row in one of these forever —
so a sweep needs to know which they are, and it must not have to enumerate them itself."""

ACTIVE = frozenset(AdaptationState) - TERMINAL
"""Rule 2: at most one *active* adaptation per catalogue item. Everything that is not finished."""


def allowed(current: AdaptationState, target: AdaptationState) -> bool:
    return target in ALLOWED[current]


def refuse(current: AdaptationState, target: AdaptationState) -> str | None:
    """The refusal message for an illegal transition, or `None` when it is legal.

    Returns rather than raises, because the caller has already read a row and holds a session:
    it needs to record an event and roll back, not unwind through an exception it must catch to
    do either.
    """
    if allowed(current, target):
        return None
    onward = ", ".join(sorted(ALLOWED[current])) or "(nothing — it is finished)"
    return (
        coded("MF0300", f"an adaptation in {current} cannot become {target}")
        + f"\n  from {current} it can go to: {onward}"
    )


def retry_target(failed_stage: AdaptationState | None) -> AdaptationState:
    """Where a retry resumes — rule 9.

    A failure in `scaffolding` is a failure to read the source or write the bundle, and no
    amount of model time fixes it; a failure anywhere else is a failure of the attempt, and the
    queue is where an attempt starts. An unrecorded stage retries as an attempt, which is the
    safe reading: it costs one model call and cannot skip a step.
    """
    if failed_stage is AdaptationState.SCAFFOLDING:
        return AdaptationState.SCAFFOLDING
    return AdaptationState.QUEUED


class RevisionState(StrEnum):
    """One attempt at a candidate.

    `VALIDATED` says the checks *finished*, not that they passed — `forge_revision`'s
    validation summary carries the verdict. Conflating the two would make a revision a
    reviewer can read and reject unrepresentable, and §2's own diagram has
    `validating --> review: checks fail but candidate is inspectable`.
    """

    SCAFFOLDED = "scaffolded"
    GENERATING = "generating"
    VALIDATING = "validating"
    VALIDATED = "validated"
    SUPERSEDED = "superseded"
    PUBLISHED = "published"
    FAILED = "failed"


SEALED = frozenset(
    {
        RevisionState.VALIDATING,
        RevisionState.VALIDATED,
        RevisionState.SUPERSEDED,
        RevisionState.PUBLISHED,
        RevisionState.FAILED,
    }
)
"""Rule 3 — a revision is immutable once validation begins. `VALIDATING` is in the set rather
than after it: the point of the rule is that a reviewer's verdict and the thing it is about
cannot drift apart, and a candidate rewritten *while* being checked breaks that just as
thoroughly as one rewritten after."""


def sealed(state: RevisionState) -> bool:
    return state in SEALED


class EventKind(StrEnum):
    """What is written into `forge_event`, and therefore what a reviewer can be shown.

    Closed on purpose: the events are the audit, and an audit whose vocabulary any call site
    may extend with a string is one nothing can query. `detail` carries the specifics.
    """

    CREATED = "created"
    SCAFFOLDED = "scaffolded"
    QUEUED = "queued"
    CLAIMED = "claimed"
    GENERATED = "generated"
    VALIDATED = "validated"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"
    RETRIED = "retried"
    RECLAIMED = "reclaimed"


class MessageRole(StrEnum):
    """Who wrote a review-chat message.

    `CURATOR` rather than `user`: the person here is reviewing somebody else's proposal, and
    the word a table uses is the word a page ends up using.
    """

    CURATOR = "curator"
    ASSISTANT = "assistant"


class MessageState(StrEnum):
    """A chat turn's own lifecycle. §1.7 — chat never changes files, so this is short."""

    PENDING = "pending"
    ANSWERED = "answered"
    FAILED = "failed"


class InvocationPurpose(StrEnum):
    """Which of §3's calls this was.

    One member per committed prompt id. A purpose with no prompt file is a call nobody can
    audit, which is what `ai_invocation` exists to prevent.
    """

    ANALYSIS = "analysis"
    IMPLEMENTATION = "implementation"
    REPAIR = "repair"
    CHAT = "chat"


class InvocationState(StrEnum):
    """`REFUSED` is separate from `FAILED` on purpose.

    A provider that timed out and a model whose answer did not validate are different findings:
    the first is retried, the second is a prompt or a model that cannot do the job. Folding
    both into `failed` makes the second invisible in exactly the numbers §5.9 wants to measure.
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUSED = "refused"


def approval_refusals(
    *,
    revision_id: str | None,
    revision_state: RevisionState | None,
    unresolved_required: int,
    validation_green: bool,
    who: str,
    reason: str,
    registry_digest_at_validation: str,
    registry_digest_now: str,
) -> list[str]:
    """Rule 5, as six independent checks — **all of them, not the first one.**

    A precondition function that returns on the first failure makes a reviewer fix one thing,
    press the button, and be told about the next. Six clicks to learn six facts the server knew
    at the first one. Returning the whole list costs nothing and is what the page renders.

    The last check is the one that is easy to leave out and the only one that can go stale while
    nobody touches the adaptation: the registry moved under a candidate that was validated
    against it, so *green* is a statement about a layer that no longer exists. It is the same
    argument `mendel upgrade` rests on, one document over.
    """
    refusals: list[str] = []
    if revision_id is None:
        refusals.append(coded("MF0301", "there is no current revision to approve"))
    if revision_state is not None and revision_state is not RevisionState.VALIDATED:
        refusals.append(
            coded("MF0301", f"the current revision is {revision_state}, not validated")
        )
    if unresolved_required:
        refusals.append(
            coded("MF0301", f"{unresolved_required} required hole(s) are still unresolved")
        )
    if not validation_green:
        refusals.append(coded("MF0301", "validation did not pass"))
    if not who.strip():
        refusals.append(coded("MF0301", "approval needs a named human"))
    if not reason.strip():
        refusals.append(coded("MF0301", "approval needs a reason"))
    if registry_digest_at_validation != registry_digest_now:
        refusals.append(
            coded("MF0301", "the registry moved since this candidate was validated")
            + f"\n  validated against {registry_digest_at_validation or '(none)'}"
            + f"\n  the registry is now {registry_digest_now or '(none)'}"
            + "\n  re-validate before approving — the green verdict describes a layer that is gone"
        )
    return refusals
