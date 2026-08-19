"""One schema for a question, whoever is asking and whoever answers.

**Two consumers, not two endpoints.** React renders an `OpenQuestion` as a card; an agent
GETs the same route and POSTs an answer back. That is what makes "the agent drives Mendel
via the API" cost nothing extra — spec §4.2.

**This is a DTO, not a door payload.** Plan 2.5 §5's egress rules govern `comeni-core`;
they do not reach here. It may carry prose freely.

**Slice 1 projects `Hole` only.** `Ambiguity` projects into this same shape when the Mendel
slice lands — it is the other subclass of the same `comeni_core.review.Question`, which is
why the projection is small. Nothing here is named for the forge.
"""

from datetime import datetime
from enum import StrEnum

from comeni_core.review import Candidate, Excerpt
from mendel_forge.ops import Drift
from mendel_forge.scaffold import Decision, Hole, Proposal
from pydantic import BaseModel, ConfigDict


class Band(StrEnum):
    """How much a wrong answer costs, which is not the same as how likely one is.

    Graded by consequence rather than hit rate — the operator's call on 2026-08-17, after
    the forge measured a model at 97% on the fields that change which pipeline gets built
    and ~60% on port labels. A flat accuracy number averages those two and hides the only
    one worth knowing.
    """

    DRIFT = "drift"
    """A contract that WAS true and now is not. Design §4's first rung, and it outranks a
    proposal that blocks a landing because it breaks pipelines that already run rather than
    holding up one that does not exist yet."""
    ROUTING = "routing"
    """Types and roles. A wrong answer routes, silently, and builds a different pipeline."""
    COSMETIC = "cosmetic"
    """Port labels. Routing is by `type_id`; a reviewer renames one in seconds."""
    PROSE = "prose"
    """Free text with no candidates. A model is never asked (issue #70)."""
    BLOCKED = "blocked"
    """A question a proposal is waiting on. Not more likely to be wrong — it is the thing
    stopping a module from landing, which is design §4's second rung."""

    @property
    def rank(self) -> int:
        """Consequence order — lower is worse to get wrong. `docs/design/forge-review.md` §4.

        **Declared rather than derived from the member order or the value.** `Band` is a
        `StrEnum`, so `sorted()` compares the strings and produces cosmetic, prose, routing —
        alphabetical order that reads as a priority. That shipped, and the queue put port
        labels above the fields that decide which pipeline gets built.

        Drift (1) arrived with phase 5, into the slot this docstring had been holding for it
        since phase 0. Blocked (2) arrived with phase 3, the same way.
        """
        return {
            Band.DRIFT: 1,
            Band.BLOCKED: 2,
            Band.ROUTING: 3,
            Band.PROSE: 4,
            Band.COSMETIC: 5,
        }[self]


_COSMETIC_SUFFIXES = (".name",)
_PROSE_SUBJECTS = frozenset({"priority_because"})


def band_for(subject: str, *, proposal: Proposal | None = None) -> Band:
    """Derived from the question, never stored on the hole.

    **It reads two things, and it used to read one.** The subject says what a wrong answer
    costs; an *open* proposal says the question is blocking a landing, which outranks that.
    A decided proposal — approved or rejected — blocks nothing, so the question returns to
    the band its subject gives it.

    Still derived rather than stored: a stored band would be a second place deciding what a
    field costs, and it would go stale the first time a field or a decision is added.
    """
    if proposal is not None and proposal.decision is Decision.OPEN:
        return Band.BLOCKED
    if subject in _PROSE_SUBJECTS:
        return Band.PROSE
    if subject.endswith(_COSMETIC_SUFFIXES):
        return Band.COSMETIC
    return Band.ROUTING


class RowKind(StrEnum):
    """What a row IS, which decides where following it leads.

    One row shape for every kind of work is firm (design §8), and a row still has to know
    whether it leads to a question or to a contract. Derived nowhere and stored here because
    it is a fact about the row's origin rather than about its content.
    """

    QUESTION = "question"
    DRIFT = "drift"


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RowKind = RowKind.QUESTION
    """Defaulted, so every existing construction is unchanged."""
    about: str | None = None
    """The contract a drift row is about. `None` on a question.

    **`asked_by` was NOT reused for this.** Its docstring says *which drafts ask it*, and
    putting a contract id there would be a lie in a field that already has a meaning, told to
    save one field — spec §3.4. It would also be found by whoever next reads `aggregate()`.
    """

    subject: str
    what: str
    why_open: str
    band: Band
    asked_by: list[str]
    """Which drafts ask it. A list because the same question recurs across modules, and
    answering once settles all of them — the throughput move the design rests on."""
    candidates: list[Candidate]
    closed: bool
    evidence: list[Excerpt]
    suggested: str | None = None
    """What a model answered, when one did. `None` means nobody has."""
    proposed: Proposal | None = None
    """Set when somebody declined this question — nothing declared fits, and here is what
    would. The hole is still open; this is why."""
    changed_at: datetime | None = None
    """When the newest draft asking this last moved. `None` where it is not known.

    On an aggregated row it is the MAXIMUM across the drafts asking, because the question a
    reviewer wants to see is one that moved *at all*, not one where everything moved."""


def question_from_hole(
    hole: Hole,
    *,
    draft: str,
    changed_at: datetime | None = None,
    proposed: Proposal | None = None,
) -> OpenQuestion:
    return OpenQuestion(
        subject=hole.subject,
        what=hole.what,
        why_open=hole.why_open,
        band=band_for(hole.subject, proposal=proposed),
        asked_by=[draft],
        candidates=list(hole.candidates),
        # **The producer this field never had.** `suggested` is read by `aggregate()`, by the
        # queue's ordering, by `Question.tsx`'s highlight and by `QueueRow`'s Ask/Confirm label
        # — and until now every `suggested=` in the repository was in a test. So it was `None`
        # in production, the Confirm branch was unreachable, and the *Ask before Confirm* sort
        # a few lines below was comparing False to False.
        #
        # **Projected, not recomputed.** `candidates[0]` is the tempting shortcut and it is
        # wrong: the candidates are always ordered, but where nothing scored, that order is the
        # alphabet. `Hole.suggested` is `None` in exactly that case, so an unfounded hole keeps
        # saying *Ask* instead of inviting a person to Confirm `alignment.bai`.
        suggested=hole.suggested,
        closed=hole.closed,
        evidence=list(hole.evidence),
        changed_at=changed_at,
        proposed=proposed,
    )


def aggregate(questions: list[OpenQuestion]) -> list[OpenQuestion]:
    """Collapse identical work into one row, keyed by `(subject, suggested)`.

    **Not by subject alone.** Two drafts asked the same question and a model answered them
    differently is precisely the disagreement a reviewer is scanning for, and merging those
    rows would hide it — the `samtools/faidx` case in the design's confirmable screen.

    `asked_by` is sorted because workspace order is directory order, and directory order
    moves under a refactor nobody asked for; the same argument as `Scaffold._sorted_holes`.

    The input is never mutated: a projection that edits its argument is one you cannot call
    twice, and the route calls it on a list it did not build.
    """
    merged: dict[tuple[str, str | None], OpenQuestion] = {}
    for q in questions:
        key = (q.subject, q.suggested)
        found = merged.get(key)
        if found is None:
            merged[key] = q.model_copy(update={"asked_by": list(q.asked_by)})
        else:
            found.asked_by.extend(q.asked_by)
            if q.changed_at and (found.changed_at is None or q.changed_at > found.changed_at):
                found.changed_at = q.changed_at
            # A merged row keeps the first proposal it saw: one draft declining is enough to
            # say the question was declined, and the row is the question rather than a draft.
            if found.proposed is None and q.proposed is not None:
                found.proposed = q.proposed
    for q in merged.values():
        q.asked_by.sort()
    # Ask before Confirm — design §4. `suggested is None` sorts False < True, so an
    # unanswered question comes first within a band.
    return sorted(
        merged.values(),
        key=lambda q: (q.band.rank, q.suggested is not None, q.subject, q.suggested or ""),
    )


def question_from_drift(found: Drift) -> OpenQuestion:
    """A drift, as a queue row.

    `candidates` stays empty: a drift is not answered by choosing, and a row offering the
    source value as a candidate would invite `POST /questions/answer` on a contract that has
    no draft behind it. Following it leads to `/forge/contracts/:about/drift`, which is the
    design's *"drift is a state of a contract"* made literal.

    **A conformance drift reads differently from a value drift** and uses the same two
    fields: `registry_says` is then the diagnostic's summary and `source_says` is its fix, so
    the row still says what moved and what to do. `Drift.code` is how a reader tells which.
    """
    what = found.field or found.code or "this contract"
    return OpenQuestion(
        kind=RowKind.DRIFT,
        about=found.contract_id,
        subject=f"{found.contract_id}#{found.field or found.code}",
        what=f"{what} moved" if found.code is None else f"{what}: {found.registry_says}",
        why_open=(
            f"the registry says {found.registry_says!r}; the source says {found.source_says!r}"
        ),
        band=Band.DRIFT,
        asked_by=[],
        candidates=[],
        closed=False,
        evidence=[],
    )


def collapse_drift(rows: list[Drift]) -> list[Drift]:
    """One field drifting is one piece of work, whichever checkers noticed.

    **Found by running the thing.** `container` and `nf_process` are checked by both a value
    comparison and a conformance diagnostic — the overlap spec §3.1 declares rather than
    merges — so one edited tag produced two queue rows with the same subject, leading to the
    same screen. That is the same work twice, which is exactly what the queue's collapsing
    exists to prevent.

    **The value row wins**, because it is the one that can be accepted: it carries what the
    source says the value should be, where the diagnostic carries a summary and a fix. The
    drift SCREEN still shows both, in its two sections — the queue is an index, and the detail
    lives with the thing it is about.

    This is NOT `aggregate()`: that collapses one question across many drafts, and this
    collapses many findings about one field. Two contracts drifting on the same field stay two
    rows, because they are two commits.
    """
    best: dict[tuple[str, str], Drift] = {}
    for found in rows:
        key = (found.contract_id, found.field or found.code or "")
        if key not in best or (best[key].code is not None and found.code is None):
            best[key] = found
    return sorted(best.values(), key=lambda d: (d.contract_id, d.field, d.code or ""))
