"""What each pass of the retention sweep removed, by category (Part H)."""

import sqlalchemy as sa
from alembic import op

revision = "a3f7c9e1b246"
down_revision = "d7b3e9a1c524"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "retention_sweep",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("removed", sa.Integer(), nullable=False),
    )
    op.create_index("ix_retention_sweep_ran_at", "retention_sweep", ["ran_at"])


def downgrade():
    op.drop_table("retention_sweep")
