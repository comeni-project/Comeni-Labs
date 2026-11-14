"""A study input may be a table of several items (#466, stage 6): `pipeline_input_revision.table`,
and a suggestion's or a turn's change may say so (`tables`: suggestion shape 6, turn shape 10).

Every earlier input was one item, so the column starts false; every older suggestion and turn
is already in the new shape."""

import sqlalchemy as sa
from alembic import context, op

revision = "d6f2a8c0e174"
down_revision = "c4e0f6a8b532"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_suggestion_5_to_6(change):
    """Shape 6 lets a change be `tables`; every older one is already in it."""
    return change


def upgrade_pipeline_authoring_turn_9_to_10(blocks):
    """Shape 10 lets a block's change be `tables`; every older one is already in it."""
    return blocks


def _stamp(table: str, stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": stamp})
    op.alter_column(table, "shape_version", server_default=sa.text(str(stamp)))


def upgrade():
    op.add_column("pipeline_input_revision",
                  sa.Column("table", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    _stamp("pipeline_authoring_suggestion", 6)
    _stamp("pipeline_authoring_turn", 10)


def downgrade():
    if not context.is_offline_mode():
        op.execute("DELETE FROM pipeline_authoring_suggestion WHERE change->>'kind' = 'tables'")
    _stamp("pipeline_authoring_suggestion", 5)
    _stamp("pipeline_authoring_turn", 9)
    op.drop_column("pipeline_input_revision", "table")
