"""Revision-specific reviewer advice and its invocation purpose."""

import sqlalchemy as sa
from alembic import op

revision = "a7d9e2b4c631"
down_revision = "e8a4d1c7f362"
branch_labels = None
depends_on = None


def _purpose(review: bool):
    purposes = "'analysis', 'implementation', 'repair', 'chat'" + (", 'review'" if review else "")
    op.drop_constraint(op.f("ck_ai_invocation_agent_purpose"), "ai_invocation", type_="check")
    op.create_check_constraint(op.f("ck_ai_invocation_agent_purpose"), "ai_invocation",
        f"(agent = 'forge' AND purpose IN ({purposes})) OR "
        "(agent = 'builder' AND purpose IN ('goal', 'family', 'chat', 'tier4', 'gap', 'ask', "
        "'readback', 'characterise_family', 'characterise'))")


def upgrade():
    _purpose(True)
    op.create_table("forge_review",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adaptation", sa.String(32), nullable=False),
        sa.Column("item", sa.String(255), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("file", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("invocation", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["adaptation"], ["forge_adaptation.id"], ondelete="RESTRICT",
            name=op.f("fk_forge_review_adaptation_forge_adaptation")))
    op.create_index(op.f("ix_forge_review_adaptation"), "forge_review", ["adaptation"])
    op.create_index("ix_forge_review_once", "forge_review",
                    ["adaptation", "item", "revision"], unique=True)


def downgrade():
    op.drop_table("forge_review")
    _purpose(False)
