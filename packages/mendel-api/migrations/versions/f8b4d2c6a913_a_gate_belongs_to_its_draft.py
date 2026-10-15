"""a gate belongs to its draft

Issue 274: `gate_run.draft_id` named a draft by convention only. RESTRICT, as every key here
is; nothing deletes a draft.

Revision ID: f8b4d2c6a913
Revises: e2a6c8f4b157
Create Date: 2026-10-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "f8b4d2c6a913"
down_revision: str | None = "e2a6c8f4b157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    _refuse_orphans(
        "SELECT g.id FROM gate_run g LEFT JOIN pipeline_draft d ON d.id = g.draft_id "
        "WHERE d.id IS NULL",
        "gates point at a draft that does not exist",
    )
    op.create_foreign_key("gate_run_draft_id_fkey", "gate_run", "pipeline_draft",
                          ["draft_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("gate_run_draft_id_fkey", "gate_run", type_="foreignkey")
