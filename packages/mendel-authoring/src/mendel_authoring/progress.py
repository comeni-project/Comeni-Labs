"""Where the walk is: the offered step's place in the pipeline as it now stands.

**Counted against the plan, never the transcript.** A swap inserts a step and a correction offers
one again, so the number of proposals made over a session says nothing about where the walk is;
the blueprint's order does. A review counts while it still holds for a step still in the plan.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OfferProgress(BaseModel):
    """One offer's place: step `position` of `total`, and whether that step was reviewed before."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    position: int = Field(ge=1)
    total: int = Field(ge=1)
    again: bool = False

    @model_validator(mode="after")
    def _within(self) -> Self:
        if self.position > self.total:
            raise ValueError("an offer's position cannot pass the plan's length")
        return self


class Upcoming(BaseModel):
    """A step the walk will still offer, at its `position` in the plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    position: int = Field(ge=1)


class WalkProgress(BaseModel):
    """How many of the plan's steps hold a review, the step offered now, if any, and the plan's
    steps after it whose review does not hold, in order — what the walk will still offer, named so
    the person can see the rest of the road. Empty when nothing is offered: a finished or paused
    walk has no "after"."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewed: int = Field(ge=0)
    total: int = Field(ge=0)
    active: OfferProgress | None = None
    upcoming: tuple[Upcoming, ...] = ()

    @model_validator(mode="after")
    def _within(self) -> Self:
        if self.reviewed > self.total:
            raise ValueError("more steps reviewed than the plan holds")
        return self


def progress_of(order: list[str], retained: frozenset[str],
                previously_reviewed: frozenset[str], pending: str | None) -> WalkProgress:
    """`retained` are the steps whose review still holds; `previously_reviewed` every step ever
    reviewed, superseded ones included. An offer outside the plan is refused, never clamped."""
    if len(set(order)) != len(order):
        raise ValueError("the plan names a step twice")
    if pending is not None and pending not in order:
        raise ValueError(f"the offered step {pending!r} is not in the plan")
    active = None if pending is None else OfferProgress(
        position=order.index(pending) + 1, total=len(order),
        again=pending in previously_reviewed,
    )
    return WalkProgress(reviewed=len(set(order) & retained), total=len(order), active=active,
                        upcoming=() if active is None else tuple(
                            Upcoming(node=step, position=at)
                            for at, step in enumerate(order, start=1)
                            if at > active.position and step not in retained))
