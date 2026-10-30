"""The `test-datasets` commit a catalogue sync read, for forge tests to pin to (#365)."""

import sqlalchemy as sa
from alembic import op

revision = "a4c1e7f09b23"
down_revision = "d069a1efd952"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("catalogue_sync", sa.Column("test_data_commit", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("catalogue_sync", "test_data_commit")
