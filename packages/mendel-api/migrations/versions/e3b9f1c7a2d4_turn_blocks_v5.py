"""A turn's blocks at shape 5: a goal's constraints may say which optional inputs a person
switched on or off (`inputs`, #460).

`inputs` is new and absent on every older goal, which reads as an empty list, so every shape-4
row is already a shape-5 row: the upgrader returns it unchanged and the migration moves the
stamp."""

import sqlalchemy as sa
from alembic import context, op

revision = "e3b9f1c7a2d4"
down_revision = "a7d9e2b4c631"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_turn_4_to_5(blocks):
    """Shape 5 adds an optional `inputs` list to a goal's constraints, absent when empty."""
    return blocks


def _stamp(stamp):
    op.get_bind().execute(sa.text("UPDATE pipeline_authoring_turn SET shape_version = :s"),
                          {"s": stamp})


def upgrade():
    if not context.is_offline_mode():
        _stamp(5)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("5"))


def downgrade():
    if not context.is_offline_mode():
        _stamp(4)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("4"))
