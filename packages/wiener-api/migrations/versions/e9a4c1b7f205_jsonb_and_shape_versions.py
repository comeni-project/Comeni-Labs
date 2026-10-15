"""Every Wiener JSON column becomes JSONB, and every table holding JSON records its shape
(Part H). The columns are listed, not discovered: a migration records what it did and renders
offline."""

import sqlalchemy as sa
from alembic import op

revision = "e9a4c1b7f205"
down_revision = "b9e5d1a7c320"
branch_labels = None
depends_on = None

COLUMNS = {
    "run": ["terminal_seen"],
    "run_event": ["payload"],
    "run_task": ["attempts", "labels"],
}


def upgrade():
    for table, columns in COLUMNS.items():
        for column in columns:
            op.execute(f'ALTER TABLE {table} ALTER COLUMN "{column}" TYPE JSONB '
                       f'USING "{column}"::jsonb')
        op.add_column(table, sa.Column("shape_version", sa.Integer(), nullable=False,
                                       server_default="1"))


def downgrade():
    raise RuntimeError("Restore a verified backup rather than narrow JSONB back to JSON.")
