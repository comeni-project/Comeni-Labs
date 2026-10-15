"""what was kept is recorded on the draft — when, the graph it was kept from, the artifact's digest

Issue 277: "kept" was whether `<draft_root>/<id>/pipeline.yml` existed, so a draft edited after
it was kept listed the old artifact beside a graph that had moved on. The row is now the one
record of keeping; the file stays the artifact. No data migration: nothing is live, and a draft
kept before this lists as not kept until it is kept again (operator, issue 277).

Revision ID: c9e5a1f3b724
Revises: b8d4f0e2a613
Create Date: 2026-10-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e5a1f3b724"
down_revision: str | None = "b8d4f0e2a613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pipeline_draft", sa.Column("kept_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("pipeline_draft", sa.Column("kept_graph", sa.String(71), nullable=True))
    op.add_column("pipeline_draft", sa.Column("kept_digest", sa.String(71), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_draft", "kept_digest")
    op.drop_column("pipeline_draft", "kept_graph")
    op.drop_column("pipeline_draft", "kept_at")
