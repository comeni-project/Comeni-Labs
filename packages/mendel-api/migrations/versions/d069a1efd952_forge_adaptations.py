"""Forging: adaptations, their items, every revision of each, and the chat (#364)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d069a1efd952"
down_revision = "82927313f17f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forge_adaptation",
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("base", sa.String(128), nullable=False),
        sa.Column("reforge", sa.String(255), nullable=True),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("depends_on", postgresql.JSONB(), nullable=False),
        sa.Column("started_by", sa.String(128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_forge_adaptation_path", "forge_adaptation", ["path"])
    op.create_table(
        "forge_item",
        sa.Column("adaptation", sa.String(32),
                  sa.ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("item", sa.String(255), primary_key=True),
        sa.Column("piece", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("current_n", sa.Integer(), nullable=False),
    )
    op.create_table(
        "forge_revision",
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adaptation", sa.String(32),
                  sa.ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item", sa.String(255), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.Column("piece", sa.String(16), nullable=False),
        sa.Column("move", sa.String(24), nullable=False),
        sa.Column("actor", sa.String(16), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("because", sa.Text(), nullable=True),
        sa.Column("invocation", sa.String(32), nullable=True),
        sa.Column("by", sa.String(128), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forge_revision_adaptation", "forge_revision", ["adaptation"])
    op.create_index("ix_forge_revision_once", "forge_revision", ["adaptation", "item", "n"],
                    unique=True)
    op.create_table(
        "forge_message",
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adaptation", sa.String(32),
                  sa.ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("item", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("invocation", sa.String(32), nullable=True),
        sa.Column("commands", postgresql.JSONB(), nullable=False),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forge_message_adaptation", "forge_message", ["adaptation"])
    op.create_index("ix_forge_message_once", "forge_message", ["adaptation", "seq"], unique=True)


def downgrade():
    op.drop_table("forge_message")
    op.drop_table("forge_revision")
    op.drop_table("forge_item")
    op.drop_table("forge_adaptation")
