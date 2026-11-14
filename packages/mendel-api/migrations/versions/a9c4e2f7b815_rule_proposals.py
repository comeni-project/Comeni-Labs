"""Rules a model proposed from people's answers, and what a person decided (#462)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9c4e2f7b815"
down_revision = "d6f2a8c0e174"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rule_proposal",
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("target_key", sa.String(200), nullable=False),
        sa.Column("target", postgresql.JSONB(), nullable=False),
        sa.Column("rows", postgresql.JSONB(), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("evidence_digest", sa.String(71), nullable=False),
        sa.Column("invocation", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("problems", postgresql.JSONB(), nullable=False),
        sa.Column("decided_by", sa.String(128), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_rule_proposal_target_key"), "rule_proposal", ["target_key"])
    op.create_index(op.f("ix_rule_proposal_status"), "rule_proposal", ["status"])
    op.create_index(op.f("ix_rule_proposal_created_at"), "rule_proposal", ["created_at"])


def downgrade():
    op.drop_table("rule_proposal")
