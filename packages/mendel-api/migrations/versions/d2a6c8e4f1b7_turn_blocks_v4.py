"""A turn's blocks at shape 4: a receipt may say what it changed (`about`, one builder plan 3).

`about` is new and absent on every older receipt, which reads as `None`, so every shape-3 row is
already a shape-4 row: the upgrader returns it unchanged and the migration moves the stamp."""

import sqlalchemy as sa
from alembic import context, op

revision = "d2a6c8e4f1b7"
down_revision = "f7b1d4c8e293"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_turn_3_to_4(blocks):
    """Shape 4 adds an optional `about` to a receipt, absent when it points at nothing."""
    return blocks


def _stamp(stamp):
    op.get_bind().execute(sa.text("UPDATE pipeline_authoring_turn SET shape_version = :s"),
                          {"s": stamp})


def upgrade():
    if not context.is_offline_mode():
        _stamp(4)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("4"))


def downgrade():
    if not context.is_offline_mode():
        _stamp(3)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("3"))
