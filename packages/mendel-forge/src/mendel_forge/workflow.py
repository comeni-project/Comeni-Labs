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
  was deleted upstream — was then retryable forever and closeable never. **Left as drawn until
  2026-09-05**, on the argument that widening a state machine is cheap later and narrowing one
  is not. The operator settled it the other way: archiving destroys nothing, so the objection to
  closing a failure has no purchase, and the asymmetry was backwards — `review`, the healthier
  state, could archive and `failed` could not.

**So the table is computed now, from two rules rather than ten rows.** Anything unfinished can
fail; anything a worker is not holding can be archived. `_exits` is that sentence and it is why
`ALLOWED` is a comprehension. The second rule closed a hole the first one made visible:
`validating` had `review` as its only successor, so a worker killed mid-validation left a row
whose only legal move was to promote a half-validated candidate — which is exactly what Task 7's
startup recovery sweep would otherwise have had to do.
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


FINISHED = frozenset({AdaptationState.PUBLISHED, AdaptationState.ARCHIVED})
"""The two states nothing leaves. Declared before the table because the table is derived from
it, where it used to be derived from the table."""

RUNNING = frozenset(
    {
        AdaptationState.SCAFFOLDING,
        AdaptationState.GENERATING,
        AdaptationState.VALIDATING,
        AdaptationState.PUBLISHING,
    }
)
"""States a job holds, so **archiving one would orphan the job rather than stop it**. That is
what `_exits` reads it for, and it is the only thing that reads it.

**It held two of the four until 2026-09-05, and the omission had no consequence until it did.**
Nothing read this set at all, so `scaffolding` and `publishing` being absent cost nothing while
it was decorative. It stopped being decorative the moment `_exits` derived the archive rule from
it: two states with a job in flight would have been archivable out from under that job, and
`publishing` is the transition that writes to the registry.

The membership test is *is a job holding this row* — one per state, from Task 7's list:
`scaffold_forge_adaptation`, `generate_forge_revision` (which spans generating and validating),
and `publish_forge_adaptation`. `queued` is waiting rather than held; `review` and
`changes_requested` are held by a person, which is not the same thing at all — a person cannot
be orphaned by an archive, they can be told.

**This set is deliberately NOT what `services/forge_state.stale()` sweeps, today.** That
docstring used to say a sweep reads this and must not enumerate the states itself, and it was
false in both directions: `stale()` enumerates `(generating, validating)` inline, and reading
this set instead would make it reclaim `scaffolding` rows — which is wrong until Task 7 actually
enqueues `scaffold_forge_adaptation`, because until then a row sits in `scaffolding` with no job
behind it and reclaiming it would restart work nobody asked for.

The two questions are *can this be archived* and *should this be reclaimed*, and they have the
same answer only once every state here is genuinely job-backed. **Wiring `stale()` to `RUNNING`
belongs in Task 7**, with the jobs that make it true and the test that can then fail."""

_ONWARD: dict[AdaptationState, frozenset[AdaptationState]] = {
    AdaptationState.SCAFFOLDING: frozenset({AdaptationState.QUEUED}),
    AdaptationState.QUEUED: frozenset({AdaptationState.GENERATING}),
    AdaptationState.GENERATING: frozenset({AdaptationState.VALIDATING}),
    AdaptationState.VALIDATING: frozenset({AdaptationState.REVIEW}),
    AdaptationState.REVIEW: frozenset(
        {AdaptationState.CHANGES_REQUESTED, AdaptationState.PUBLISHING}
    ),
    AdaptationState.CHANGES_REQUESTED: frozenset({AdaptationState.GENERATING}),
    AdaptationState.PUBLISHING: frozenset({AdaptationState.PUBLISHED, AdaptationState.REVIEW}),
    AdaptationState.PUBLISHED: frozenset(),
    AdaptationState.FAILED: frozenset({AdaptationState.QUEUED, AdaptationState.SCAFFOLDING}),
    AdaptationState.ARCHIVED: frozenset(),
}
"""Progress only — where an adaptation goes when something *works*.

Failing and archiving are not in here, because they are not steps in a workflow; they are two
rules that hold everywhere, and `ALLOWED` applies them below.
"""


def _exits(state: AdaptationState) -> frozenset[AdaptationState]:
    """The two rules that are not steps.

    **Anything unfinished can fail.** A stage that cannot record its own failure has to invent
    somewhere to put one, and `validating` was exactly that: its only successor was `review`, so
    a worker killed mid-validation left a row whose only legal move was *forward*, promoting a
    half-validated candidate. That is what the startup recovery sweep would have had to do.

    **Archiving is legal from any state a worker does not hold.** Settled by the operator on
    2026-09-04: archiving destroys nothing — every foreign key is `RESTRICT`, `forge_event` has
    no update path, and revisions and invocation audit survive — so it is a lifecycle statement,
    *nobody is working on this*, rather than a disposal. The old table let `review` archive and
    `failed` not, which is backwards: it is the *healthier* state that could be closed. A failed
    adaptation held its catalogue item's one-active slot forever, with no exit but retry or a
    manual `UPDATE`, because the partial unique index excludes exactly `FINISHED` and `begin()`
    refuses with `MI0101`.

    A `RUNNING` state is excluded from archiving and not from failing, which is the whole
    distinction: a worker holds the row, and archiving it out from under a running job would
    orphan the job rather than stop it. Failing is what a *sweep* does to a row whose worker is
    already gone.
    """
    if state in FINISHED:
        return frozenset()
    exits = {AdaptationState.FAILED}
    if state not in RUNNING:
        exits.add(AdaptationState.ARCHIVED)
    # **No self-transition.** `failed -> failed` fell straight out of the rule and is nonsense:
    # a compare-and-swap that expects `failed` and writes `failed` succeeds, bumps the row
    # version, records an event, and changes nothing — a retry loop that reports progress. The
    # enumerated table could not express this defect, which is the cost of computing one.
    return frozenset(exits - {state})


ALLOWED: dict[AdaptationState, frozenset[AdaptationState]] = {
    state: onward | _exits(state) for state, onward in _ONWARD.items()
}
"""Successors, by current state — **computed rather than enumerated, since 2026-09-05.**

The trade is real and was recorded rather than dismissed: an enumerated table is readable at a
glance and this one has to be run to be read. What buys that back is that the two rules cannot
drift from the states they are about. `FAILED` reachable from eight states was eight rows to
keep in step; `ARCHIVED` from five was five, and the enumerated version had one.

Every member of `AdaptationState` is a key — a state missing would be one nothing could ever
leave, which is a typo rather than a decision, so `test_every_state_is_in_the_table` is what
makes the omission fail. `test_the_table_matches_the_rules_spelled_out` is the readability
half: it asserts the computed result against a literal, so a reader who wants the old glance
has one and a change to `_exits` has to be agreed with in two places.
"""

TERMINAL = frozenset(state for state, onward in ALLOWED.items() if not onward)
"""`published` and `archived`. Still derived from the table rather than listed, so it stays a
statement about what `ALLOWED` says rather than a second answer beside it — and
`test_terminal_is_exactly_finished` holds it against `FINISHED`, which is now the input."""

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
