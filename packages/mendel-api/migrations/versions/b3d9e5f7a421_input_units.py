"""An input may span several rows per sample (#466): `pipeline_input_revision.units`, and a
suggestion's or a turn's change may say so (`units`: suggestion shape 4, turn shape 8).

Every earlier input took one row per sample, so the column starts false; every older suggestion
is already in shape 4."""

import sqlalchemy as sa
from alembic import context, op

revision = "b3d9e5f7a421"
down_revision = "a2c8e4f6b319"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_suggestion_3_to_4(change):
    """Shape 4 lets a change be `units`; every older one is already in it."""
    return change


def upgrade_pipeline_authoring_turn_7_to_8(blocks):
    """Shape 8 lets a block's change be `units`; every older one is already in it."""
    return blocks


def _stamp(table: str, stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": stamp})
    op.alter_column(table, "shape_version", server_default=sa.text(str(stamp)))


def upgrade():
    op.add_column("pipeline_input_revision",
                  sa.Column("units", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    _stamp("pipeline_authoring_suggestion", 4)
    _stamp("pipeline_authoring_turn", 8)


def downgrade():
    if not context.is_offline_mode():
        op.execute("DELETE FROM pipeline_authoring_suggestion WHERE change->>'kind' = 'units'")
    _stamp("pipeline_authoring_suggestion", 3)
    _stamp("pipeline_authoring_turn", 7)
    op.drop_column("pipeline_input_revision", "units")
