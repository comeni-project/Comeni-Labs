"""Forge tests as Wiener runs: one row per test per attempt (#365)."""

import sqlalchemy as sa
from alembic import op

revision = "b7d2f4a81c6e"
down_revision = "a4c1e7f09b23"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forge_test_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adaptation", sa.String(32),
                  sa.ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("says", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heard_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_forge_test_run_adaptation", "forge_test_run", ["adaptation"])
    op.create_index("ix_forge_test_run_state", "forge_test_run", ["state"])
    op.create_index("ix_forge_test_run_once", "forge_test_run",
                    ["adaptation", "attempt", "name"], unique=True)


def downgrade():
    op.drop_table("forge_test_run")
