"""a gate belongs to its draft

Issue 274: `gate_run.draft_id` named a draft by convention only. RESTRICT, as every key here
is; nothing deletes a draft.

Revision ID: f8b4d2c6a913
Revises: e2a6c8f4b157
Create Date: 2026-10-08

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f8b4d2c6a913"
down_revision: str | None = "e2a6c8f4b157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key("gate_run_draft_id_fkey", "gate_run", "pipeline_draft",
                          ["draft_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("gate_run_draft_id_fkey", "gate_run", type_="foreignkey")
