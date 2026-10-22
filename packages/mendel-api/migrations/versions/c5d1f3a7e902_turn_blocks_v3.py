"""A turn's blocks at shape 3: a goal's constraints may carry a person's structural intent (A1).

`absent_roles`, `exclusions` and `sources` are new and omitted when empty, so every shape-2 row
is already a shape-3 row: the upgrader returns it unchanged and the migration moves the stamp."""

import sqlalchemy as sa
from alembic import context, op

revision = "c5d1f3a7e902"
down_revision = "b7c3e9a1d204"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_turn_2_to_3(blocks):
    """Shape 3 adds three optional constraint lists to a goal, absent when empty."""
    return blocks


def _stamp(stamp):
    op.get_bind().execute(sa.text("UPDATE pipeline_authoring_turn SET shape_version = :s"),
                          {"s": stamp})


def upgrade():
    if not context.is_offline_mode():
        _stamp(3)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("3"))


def downgrade():
    if not context.is_offline_mode():
        _stamp(2)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("2"))
