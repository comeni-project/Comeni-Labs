"""Saved alternatives load only on an explicit preview request."""

import sqlalchemy as sa
from alembic import op

revision = "b9d3e7f5c164"
down_revision = "a8c2d6e4b053"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pipeline_authoring_proposal",
                  sa.Column("preview_views", sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError("Restore a verified backup rather than discard saved previews.")
