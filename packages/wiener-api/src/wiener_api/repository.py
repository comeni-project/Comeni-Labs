# packages/wiener-api/src/wiener_api/repository.py
"""Every query on a tenant-scoped table, and there are no others.

`docs/design/wiener.md` §7.1 names the cost of a tenant column plainly: **a filter you can
forget is a leak**, and it is the class of bug that stays invisible until it is a disclosure.
So the guard is not "remember the filter" — it is that a query lives here or it does not exist,
and every function here takes `lab_id` as its first parameter. `test_tenancy.py` holds both
halves. A177.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from wiener_api.models import Run


def run(session: Session, lab_id: str, run_id: str) -> Run | None:
    return session.scalar(select(Run).where(Run.lab_id == lab_id, Run.id == run_id))


def runs(session: Session, lab_id: str, limit: int = 50) -> list[Run]:
    return list(session.scalars(
        select(Run).where(Run.lab_id == lab_id).order_by(Run.submitted_at.desc()).limit(limit)
    ))
