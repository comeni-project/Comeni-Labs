"""What needs a person, and what the registry holds.

**Counts and links, never items.** The Queue owns questions, Contracts owns drift, Sources owns
what can be started; this says how much and points. An **Overview** page that listed rows was
designed and cut once — `docs/design/forge-review.md` §3 — for answering the Queue's question,
and rendering one row here is how that decision gets undone by forgetting it. That discipline is
the whole reason a landing page is defensible at all
(`docs/notes/specs/2026-08-19-the-landing-page.md` §1).

**Sections, not a flat list.** The interface spec's own test of this design is that 3C *gains*
Mendel's items without changing shape. A flat list would make `mendel` a filter on a field, and
the day pipelines exist somebody would have to decide what that field is called; a section that
is empty today is a section that fills.

**One question now, and it is about need.** `forge` and `mendel` say what wants a person.

**There used to be a second half** — `standing`, what the registry *holds*: 12 contracts, 22
types, 3 rules. It was defended here as *the half a dashboard usually omits, and what makes a
front door a place rather than an inbox*. Plan 4 phase 2 deleted it on the operator's reading,
and the counter-argument is worth keeping because it is short: that is the PRODUCT's state, not
YOURS, and it is why the old page read as slop — information with no question behind it.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from mendel_api.services import checked, drafts, queue, tools

_PIPELINES_AT_MOST = 25
"""The front door counts and points; it is not the pipelines table. Past this many, the *Work*
block below is where somebody is actually looking."""


class Urgency(StrEnum):
    """How much a thing costs if it waits — not how likely it is to matter."""

    BLOCKING = "blocking"
    """It breaks something that already works. Drift is the only one today."""
    WAITING = "waiting"
    """Somebody is held up until a person decides. Open questions, blocked proposals."""
    IDLE = "idle"
    """Available work nobody is waiting on. An undrafted tool is an opportunity, and
    rendering it as a deficiency would be the wrong sentence entirely."""

    @property
    def rank(self) -> int:
        """Worst first.

        **Declared rather than derived from the member order**, which is the fourth time this
        project has needed the note: this is a `StrEnum`, so `sorted()` compares the strings and
        would answer blocking, idle, waiting — alphabetical order reading as consequence.
        `Band.rank` shipped that way once and put cosmetic work above routing.
        """
        return {Urgency.BLOCKING: 1, Urgency.WAITING: 2, Urgency.IDLE: 3}[self]


class Call(BaseModel):
    """One thing asking for a person: how much, said plainly, and where it lives."""

    what: str
    """A sentence, not a label — `dashboard.md` §7: name things by what a person recognises."""
    where: str
    """The screen that owns it. This page points; it does not do the work."""
    count: int
    urgency: Urgency


class Attention(BaseModel):
    """What needs a person, now.

    **`standing` is gone, deliberately** — Plan 4 phase 2. It reported what the *registry holds*:
    12 contracts, 22 types, 3 rules. `ov-settled` cuts it in one line: *that is the PRODUCT's
    state, not YOURS, and it is why the old page read as slop — information with no question
    behind it.* Deleted rather than hidden, along with `frontend/src/home/Standing.tsx`, because
    a model with no consumer is a model that comes back.
    """

    forge: list[Call] = Field(default_factory=list)
    """**Not rendered while the forge is hidden**, and not deleted either.

    Phase 0 took the forge out of the navigation by the operator's decision of 2026-08-30 — it
    is carried as needing testing and rework — and left every route resolving. A call to action
    pointing at a screen the frame offers no way into is worse than no call at all, so the page
    stops showing these; the day the forge comes back, so do they.

    Computed rather than skipped, because a value nobody asks for silently stops being correct.
    """
    mendel: list[Call] = Field(default_factory=list)
    """What the lab's own pipelines need.

    **This said "empty today, nothing stores pipelines" and that had been false since Plan 3E.**
    Drafts have been rows in Postgres since the builder became a builder; nobody came back to
    the sentence. It is filled now, from the same listing the *by pipeline* table reads.
    """


def whats_open() -> Attention:
    """One pass over four services, each of which is cached on the registry digest.

    Measured warm at **24.5ms** for the four together, of which about 18ms is
    `digest_of_directory` computed once per service. Inside the budget by twenty times, and
    audit A138 records where that stops being true.
    """
    # **One board, not two listings.** This read `contracts.listing()` and `sources.catalogue()`
    # separately, which is the same split spec §1.3 removed from the interface — and it meant the
    # front door and the tools page could disagree about how many contracts drifted. They now
    # answer from one composition.
    board = tools.board()
    open_work = queue.read()
    drift = {found.contract_id for found in checked.result().drift}

    # **Straight at `/forge/tools`, not at the redirect.** `/forge/sources` and
    # `/forge/contracts` still resolve, but `<Navigate>` replaces the whole location with a
    # *fixed* query — so `?against=drifted` was being discarded and the front door's
    # "1 no longer agrees → open" landed on every landed tool. A redirect keeps an old link
    # working; it is not somewhere new links should point.
    calls: list[Call] = []

    if drift:
        calls.append(
            Call(
                what=f"{len(drift)} {_contracts(len(drift))} no longer match their source",
                where="/forge/tools?against=drifted",
                count=len(drift),
                urgency=Urgency.BLOCKING,
            )
        )
    if open_work.total:
        calls.append(
            Call(
                what=f"{open_work.total} {_questions(open_work.total)} waiting on a decision",
                where="/forge/queue",
                count=open_work.total,
                urgency=Urgency.WAITING,
            )
        )
    undrafted = board.counts.get("undrafted", 0)
    if undrafted:
        calls.append(
            Call(
                what=f"{undrafted} {_tools(undrafted)} nobody has drafted",
                where="/forge/tools?state=undrafted",
                count=undrafted,
                urgency=Urgency.IDLE,
            )
        )

    calls.sort(key=lambda call: call.urgency.rank)
    return Attention(forge=calls, mendel=_waiting_on_a_person())


def _waiting_on_a_person() -> list[Call]:
    """The lab's own pipelines with a value nobody has answered.

    **It names the values.** *"strandedness and fragment size"*, not *"2 items"* — `ov-settled`,
    and the reason is that a count is what you write when you have not looked.

    **Only genuinely open ones.** A hand-drawn pipeline records every step as `tier: 4,
    source: human`, because a person chose it and `MD0220` says `source: human` is exactly what
    clears a review. `drafts._provenance_of` is where that distinction lives; counting raw tier 4
    reported five things needing attention on a pipeline where one did.

    One `Call` per pipeline rather than one for all of them: *which* pipeline is the first thing
    somebody needs, and a single row reading "3 pipelines need you" is a count again.
    """
    # **The front door must not go blank because the database is down**, and this is A192's
    # argument arriving on the other half of the product: `/overview` was required to degrade
    # where `/graph` 404s, because *a 404 on the default view turns a readable run into a blank
    # page*. The two halves here have different failure modes — the forge half reads FILES and
    # the mendel half reads ROWS — so the one that can be unavailable must not take the other
    # with it.
    #
    # It is also what keeps `whats_open()` testable in CI, which has no Postgres. That is a
    # consequence rather than the reason; the reason is the page.
    try:
        rows, _ = drafts.list_drafts(limit=_PIPELINES_AT_MOST)
    except Exception:  # noqa: BLE001 — an unreachable store is not a reason to lose the page
        return []
    calls: list[Call] = []
    for row in rows:
        if not row.open_values and not row.open_not_named:
            continue
        named = ", ".join(value.setting for value in row.open_values)
        if row.open_not_named:
            named += f" and {row.open_not_named} more"
        verb = "has" if len(row.open_values) + row.open_not_named == 1 else "have"
        calls.append(
            Call(
                what=f"{row.name or row.id[:8]}: {named} {verb} no rule",
                where=f"/build?draft={row.id}",
                count=len(row.open_values) + row.open_not_named,
                urgency=Urgency.WAITING,
            )
        )
    return calls


def _contracts(n: int) -> str:
    return "contract" if n == 1 else "contracts"


def _questions(n: int) -> str:
    return "question" if n == 1 else "questions"


def _tools(n: int) -> str:
    return "tool" if n == 1 else "tools"
