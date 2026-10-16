"""A turn's blocks at shape 2: a fact's card carries its values and reasons (#341).

Both fields are new and optional, so every shape-1 row is already a shape-2 row: the upgrader
returns it unchanged and the migration moves the stamp."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "a9d4e2c7b318"
down_revision = "d3b7f1a9c582"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_turn_1_to_2(blocks):
    """Shape 2 adds `fact_values` and `fact_reasons` to a need, both empty when absent."""
    return blocks


def _without_fact_fields(value):
    if isinstance(value, dict):
        return {k: _without_fact_fields(v) for k, v in value.items()
                if k not in ("fact_values", "fact_reasons")}
    if isinstance(value, list):
        return [_without_fact_fields(v) for v in value]
    return value


def _rewrite(change, stamp):
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, blocks FROM pipeline_authoring_turn")).all()
    for row_id, blocks in rows:
        conn.execute(
            sa.text("UPDATE pipeline_authoring_turn SET blocks = CAST(:blocks AS jsonb), "
                    "shape_version = :stamp WHERE id = :id"),
            {"blocks": json.dumps(change(blocks)), "stamp": stamp, "id": row_id})


def upgrade():
    if not context.is_offline_mode():
        _rewrite(upgrade_pipeline_authoring_turn_1_to_2, 2)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("2"))


def downgrade():
    if not context.is_offline_mode():
        _rewrite(_without_fact_fields, 1)
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("1"))
