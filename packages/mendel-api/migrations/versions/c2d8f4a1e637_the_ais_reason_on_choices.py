"""The builder agent's reason for a tool it chose or a value it set (#463): a nullable `because`
on producer and parameter revisions, and on a change (suggestion shape 7, turn shape 11).

Every earlier revision, suggestion and turn is a person's or a model's without a reason, so the
column starts empty and every older stored change is already in the new shape."""

import sqlalchemy as sa
from alembic import context, op

revision = "c2d8f4a1e637"
down_revision = "b7e3c1d9f046"
branch_labels = None
depends_on = None

TABLES = ("pipeline_producer_revision", "pipeline_parameter_revision")


def upgrade_pipeline_authoring_suggestion_6_to_7(change):
    """Shape 7 lets a change carry `because`; no older one did."""
    return change


def upgrade_pipeline_authoring_turn_10_to_11(blocks):
    """Shape 11 lets a block's change carry `because`; no older one did."""
    return blocks


def _stamp(table: str, stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": stamp})
    op.alter_column(table, "shape_version", server_default=sa.text(str(stamp)))


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("because", sa.Text(), nullable=True))
    _stamp("pipeline_authoring_suggestion", 7)
    _stamp("pipeline_authoring_turn", 11)


def downgrade() -> None:
    _stamp("pipeline_authoring_suggestion", 6)
    _stamp("pipeline_authoring_turn", 10)
    for table in TABLES:
        op.drop_column(table, "because")
