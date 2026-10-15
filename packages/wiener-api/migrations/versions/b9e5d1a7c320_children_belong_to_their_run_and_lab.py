"""a run's children belong to it, in its lab

Revision ID: b9e5d1a7c320
Revises: a7d3f9b2c418
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


revision: str = 'b9e5d1a7c320'
down_revision: Union[str, Sequence[str], None] = 'a7d3f9b2c418'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHILDREN = ("run_event", "run_task", "run_intent")


def _refuse_orphans(query: str, what: str) -> None:
    """A key cannot be added over rows that break it; say so with the count and the query,
    rather than leaving Postgres's bare violation to explain it (issue 297). Offline (`--sql`)
    there is no data to count."""
    if context.is_offline_mode():
        return
    count = op.get_bind().execute(sa.text(f"SELECT count(*) FROM ({query}) AS orphans")).scalar()
    if count:
        raise RuntimeError(
            f"{count} {what}, so the key cannot be added. Delete or repair them first; "
            f"they are: {query}"
        )


def upgrade() -> None:
    """Issue 274: Wiener had no foreign key, and every child copied `lab_id` with nothing
    making it equal its parent's. Each key is `(lab_id, …)`, so a row in another lab's run
    cannot exist; RESTRICT, as Mendel's are, and nothing here deletes a row."""
    _refuse_orphans(
        "SELECT r.id FROM run r LEFT JOIN run_artifact a "
        "ON a.id = r.artifact_id AND a.lab_id = r.lab_id WHERE a.id IS NULL",
        "runs point at an artifact their lab does not have",
    )
    for child in CHILDREN:
        _refuse_orphans(
            f"SELECT c.run_id FROM {child} c LEFT JOIN run r "
            f"ON r.id = c.run_id AND r.lab_id = c.lab_id WHERE r.id IS NULL",
            f"{child} rows point at a run their lab does not have",
        )
    op.create_unique_constraint("uq_run_artifact_lab_id_id", "run_artifact", ["lab_id", "id"])
    op.create_unique_constraint("uq_run_lab_id_id", "run", ["lab_id", "id"])
    op.create_foreign_key("fk_run_artifact", "run", "run_artifact", ["lab_id", "artifact_id"],
                          ["lab_id", "id"], ondelete="RESTRICT")
    for child in CHILDREN:
        op.create_foreign_key(f"fk_{child}_run", child, "run", ["lab_id", "run_id"],
                              ["lab_id", "id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_run_intent_resulting_run", "run_intent", "run",
                          ["lab_id", "resulting_run_id"], ["lab_id", "id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_run_intent_resulting_run", "run_intent", type_="foreignkey")
    for child in reversed(CHILDREN):
        op.drop_constraint(f"fk_{child}_run", child, type_="foreignkey")
    op.drop_constraint("fk_run_artifact", "run", type_="foreignkey")
    op.drop_constraint("uq_run_lab_id_id", "run", type_="unique")
    op.drop_constraint("uq_run_artifact_lab_id_id", "run_artifact", type_="unique")
