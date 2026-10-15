"""installation_setting — the settings menu's store (spec 2026-10-01 §8).

Revision ID: d5a1c7e93b20
Revises: c3e8f1a57d20
Create Date: 2026-10-01
"""

import sqlalchemy as sa
from alembic import op

revision: str = "d5a1c7e93b20"
down_revision: str | None = "c3e8f1a57d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installation_setting",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("installation_setting")
