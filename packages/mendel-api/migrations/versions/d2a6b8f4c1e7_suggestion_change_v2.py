"""A suggestion's change at shape 2: it may be a person's structural intent (A1).

`role`, `exclude` and `source` are new kinds on the same fields, so every shape-1 row
is already a shape-2 row: the upgrader returns it unchanged and the migration moves the stamp."""

import sqlalchemy as sa
from alembic import context, op

revision = "d2a6b8f4c1e7"
down_revision = "7ea478ea7f3b"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_suggestion_1_to_2(change):
    """Shape 2 adds three kinds a change may be."""
    return change


def _stamp(stamp):
    op.get_bind().execute(sa.text("UPDATE pipeline_authoring_suggestion SET shape_version = :s"),
                          {"s": stamp})


def upgrade():
    if not context.is_offline_mode():
        _stamp(2)
    op.alter_column("pipeline_authoring_suggestion", "shape_version", server_default=sa.text("2"))


def downgrade():
    if not context.is_offline_mode():
        _stamp(1)
    op.alter_column("pipeline_authoring_suggestion", "shape_version", server_default=sa.text("1"))
