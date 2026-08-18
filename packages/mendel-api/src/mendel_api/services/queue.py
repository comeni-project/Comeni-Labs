"""Reading the queue: what is open, in what order, grouped how.

**Every control is answered here rather than in the browser.** The design's claim is that one
page survives 5,800 contracts (`forge-review.md` §4), and a client that filters after
downloading everything does not survive it — it just hides the cost until somebody has a real
registry.
"""

from enum import StrEnum

from mendel_forge import ops
from pydantic import BaseModel

from mendel_api.questions import Band, OpenQuestion, aggregate, question_from_hole
from mendel_api.services import visits
from mendel_api.settings import settings


class Grouping(StrEnum):
    QUESTION = "question"
    """One row per distinct question. The default, and the throughput move: the same
    question asked by eleven drafts is answered once."""
    MODULE = "module"
    """One row per draft per question. What you want when you are finishing one module."""


class Ordering(StrEnum):
    CONSEQUENCE = "consequence"
    """Design §4's ladder — what is worst to get wrong, first."""
    RECENT = "recent"
    """What moved most recently. The maintenance reading."""


class QueueResponse(BaseModel):
    questions: list[OpenQuestion]
    total: int
    """Open questions in the workspace, BEFORE filtering and before collapsing. The list is
    short because rows collapse and filters narrow; the count must not be, or the queue
    understates how much work is open."""


def read(
    *,
    band: Band | None = None,
    group: Grouping = Grouping.QUESTION,
    sort: Ordering = Ordering.CONSEQUENCE,
    since_last_visit: bool = False,
    who: str | None = None,
) -> QueueResponse:
    """Every open question, filtered, ordered and grouped.

    `show` needs the registry and the source as well as the workspace: a hole's candidates
    are recomputed from the layer stack rather than stored, so a draft cannot be read
    without the registry it was drafted against.
    """
    names = ops.list_(ops.ListRequest(workspace_root=settings.workspace_root)).names

    found: list[OpenQuestion] = []
    for name in names:
        shown = ops.show(
            ops.ShowRequest(
                name=name,
                registry_root=settings.registry_root,
                source_root=settings.source_root,
                workspace_root=settings.workspace_root,
            )
        )
        found += [
            question_from_hole(h, draft=name, changed_at=shown.changed_at) for h in shown.holes
        ]

    total = len(found)

    # `None` means this person has never been here, and that must show EVERYTHING. Reading
    # it as "nothing is newer than never" empties the queue for the one reader least able
    # to tell that it is wrong.
    if since_last_visit:
        seen = visits.last(who)
        if seen is not None:
            found = [q for q in found if q.changed_at is not None and q.changed_at > seen]

    if band is not None:
        found = [q for q in found if q.band is band]

    rows = aggregate(found) if group is Grouping.QUESTION else _by_module(found)

    if sort is Ordering.RECENT:
        # `datetime.min` is not timezone-aware and cannot be compared with a stored time, so
        # rows without a time are partitioned out rather than given a fake one.
        timed = [r for r in rows if r.changed_at is not None]
        untimed = [r for r in rows if r.changed_at is None]
        rows = sorted(timed, key=lambda r: r.changed_at, reverse=True) + untimed

    return QueueResponse(questions=rows, total=total)


def _by_module(questions: list[OpenQuestion]) -> list[OpenQuestion]:
    """Un-collapsed, ordered by draft and then by consequence within it."""
    return sorted(questions, key=lambda q: (q.asked_by[0], q.band.rank, q.subject))
