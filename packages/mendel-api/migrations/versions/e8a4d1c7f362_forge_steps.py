"""What the AI did, as a record, and a message's detail kept apart from its sentence (#420, #430)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8a4d1c7f362"
down_revision = "c3e7a1f94b20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forge_step",
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adaptation", sa.String(32), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["adaptation"], ["forge_adaptation.id"], ondelete="RESTRICT",
                                name=op.f("fk_forge_step_adaptation_forge_adaptation")),
    )
    op.create_index(op.f("ix_forge_step_adaptation"), "forge_step", ["adaptation"])
    op.create_index("ix_forge_step_once", "forge_step", ["adaptation", "seq"], unique=True)
    op.add_column("forge_message", sa.Column(
        "details", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade():
    op.drop_column("forge_message", "details")
    op.drop_table("forge_step")
