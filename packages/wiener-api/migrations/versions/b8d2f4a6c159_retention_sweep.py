"""What each pass of Wiener's retention sweep removed, and when a run's working files went
(Part H)."""

import sqlalchemy as sa
from alembic import op

revision = "b8d2f4a6c159"
down_revision = "f2c6a8d4e317"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "retention_sweep",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lab_id", sa.String(32), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("removed", sa.Integer(), nullable=False),
    )
    op.create_index("ix_retention_sweep_lab_id", "retention_sweep", ["lab_id"])
    op.create_index("ix_retention_sweep_ran_at", "retention_sweep", ["ran_at"])
    op.add_column("run", sa.Column("work_cleared_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("run", "work_cleared_at")
    op.drop_table("retention_sweep")
