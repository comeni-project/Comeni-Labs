"""Wiener stores its own settings: how long a run's files and record are kept (Part H)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f2c6a8d4e317"
down_revision = "e9a4c1b7f205"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wiener_setting",
        sa.Column("lab_id", sa.String(32), primary_key=True),
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(200), nullable=False),
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_table("wiener_setting")
