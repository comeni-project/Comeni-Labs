"""What needs a person: the lab's pipelines with a value nobody has answered.

**Counts and links, never items.** Each call says how much, in words a person recognises, and
points at the screen that owns the work; the front door does not do the work itself.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from mendel_api.services import drafts

_PIPELINES_AT_MOST = 25
"""The front door counts and points; it is not the pipelines table."""


class Urgency(StrEnum):
    """How much a thing costs if it waits."""

    WAITING = "waiting"
    """Somebody is held up until a person decides."""


class Call(BaseModel):
    """One thing asking for a person: how much, said plainly, and where it lives."""

    what: str
    """A sentence, not a label: name things by what a person recognises."""
    where: str
    """The screen that owns it. This page points; it does not do the work."""
    count: int
    urgency: Urgency


class Attention(BaseModel):
    """What needs a person, now."""

    mendel: list[Call] = Field(default_factory=list)
    """What the lab's own pipelines need, from the same listing the pipelines table reads."""


def whats_open() -> Attention:
    """What needs a person, now."""
    return Attention(mendel=_waiting_on_a_person())


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
    # **The front door must not go blank because the database is down**: an unreachable store
    # answers with nothing waiting rather than an error on the default page.
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
