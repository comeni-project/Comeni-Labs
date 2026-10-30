"""Registry releases cut from the app, one at a time (#367)."""

import sqlalchemy as sa
from alembic import op

revision = "d5f1b82e9a07"
down_revision = "c3e9a15d7f42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forge_release",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False, unique=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("says", sa.Text(), nullable=True),
        sa.Column("commit", sa.String(64), nullable=True),
        sa.Column("cut_by", sa.String(128), nullable=False),
        sa.Column("cut_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forge_release_one_cutting", "forge_release", ["state"], unique=True,
                    postgresql_where=sa.text("state = 'cutting'"))


def downgrade():
    op.drop_table("forge_release")
