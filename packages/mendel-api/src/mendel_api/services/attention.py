"""What needs a person, and what the registry holds.

**Counts and links, never items.** The Queue owns questions, Contracts owns drift, Sources owns
what can be started; this says how much and points. An **Overview** page that listed rows was
designed and cut once — `docs/design/forge-review.md` §3 — for answering the Queue's question,
and rendering one row here is how that decision gets undone by forgetting it. That discipline is
the whole reason a landing page is defensible at all
(`notes/specs/2026-08-19-the-landing-page.md` §1).

**Sections, not a flat list.** The interface spec's own test of this design is that 3C *gains*
Mendel's items without changing shape. A flat list would make `mendel` a filter on a field, and
the day pipelines exist somebody would have to decide what that field is called; a section that
is empty today is a section that fills.

**Two halves, and only one of them is about need.** `forge`/`mendel` say what wants a person;
`standing` says what the registry *holds*. The second is the half a dashboard usually omits, and
it is what makes a front door a place rather than an inbox.
"""

from enum import StrEnum

from pydantic import BaseModel

from mendel_api.services import checked, queue, registry, tools


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


class Standing(BaseModel):
    """What the registry holds. Not what it needs."""

    contracts: int
    matching: int
    unverifiable: int
    drifted: int
    types: int
    roles: int
    rules: int
    measurements: int
    sources: list[str]
    undrafted: int


class Attention(BaseModel):
    forge: list[Call]
    mendel: list[Call]
    """**Empty today, and that is a section rather than a zero.** Nothing stores pipelines, so
    the page renders no Mendel block at all — `0 pipelines need review` would claim that
    pipelines were looked at."""
    standing: Standing


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
    stack = registry.stack()
    drift = {found.contract_id for found in checked.result().drift}

    calls: list[Call] = []

    if drift:
        calls.append(
            Call(
                what=f"{len(drift)} {_contracts(len(drift))} no longer match their source",
                where="/forge/contracts?against=drifted",
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
                where="/forge/sources?state=undrafted",
                count=undrafted,
                urgency=Urgency.IDLE,
            )
        )

    calls.sort(key=lambda call: call.urgency.rank)

    return Attention(
        forge=calls,
        mendel=[],
        standing=Standing(
            contracts=board.counts.get("landed", 0),
            matching=board.status_counts.get("matching", 0),
            unverifiable=board.status_counts.get("unverifiable", 0),
            drifted=board.status_counts.get("drifted", 0),
            types=len(stack.vocabulary.types),
            roles=len(stack.roles.names),
            rules=len(stack.rules.decisions),
            measurements=len(stack.measurements.ids()),
            sources=board.sources,
            undrafted=undrafted,
        ),
    )


def _contracts(n: int) -> str:
    return "contract" if n == 1 else "contracts"


def _questions(n: int) -> str:
    return "question" if n == 1 else "questions"


def _tools(n: int) -> str:
    return "tool" if n == 1 else "tools"
