"""Forge pull requests on the registry, at most one open (#366)."""

import sqlalchemy as sa
from alembic import op

revision = "c3e9a15d7f42"
down_revision = "b7d2f4a81c6e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forge_pull_request",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adaptation", sa.String(32),
                  sa.ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(255), nullable=False),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("checks", sa.String(16), nullable=False),
        sa.Column("head", sa.String(64), nullable=False),
        sa.Column("says", sa.Text(), nullable=True),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("opened_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_forge_pull_request_adaptation", "forge_pull_request", ["adaptation"])
    op.create_index("ix_forge_pull_request_one_open", "forge_pull_request", ["state"], unique=True,
                    postgresql_where=sa.text("state = 'open'"))


def downgrade():
    op.drop_table("forge_pull_request")
