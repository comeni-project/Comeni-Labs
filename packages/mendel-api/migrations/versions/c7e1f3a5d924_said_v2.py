"""A value the person stated is `said`, no longer `goal` (Part I.0 Plan B): each table one shape on.

`ValueSource.GOAL` became `SAID` with `pipeline.yml` version 7. The enum stays closed, so a row
still saying `goal` would be refused on read: every `"source": "goal"` in the JSON columns that
carry a goal, a blueprint or a preview is rewritten. Only the key `source`: a premise's
`origin: goal` is another enum and stays."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "c7e1f3a5d924"
down_revision = "a9d4e2c7b318"
branch_labels = None
depends_on = None

COLUMNS = {
    # table: (the JSON columns rewritten, the shape before, the shape after)
    "pipeline_draft": (("graph", "provenance"), 1, 2),
    "pipeline_authoring_session": (("blueprint",), 1, 2),
    "pipeline_authoring_proposal": (("payload", "preview_views"), 1, 2),
    "pipeline_authoring_turn": (("blocks",), 2, 3),
}


def _renamed(value, old, new):
    if isinstance(value, dict):
        return {k: (new if k == "source" and v == old else _renamed(v, old, new))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_renamed(v, old, new) for v in value]
    return value


def upgrade_said(value):
    """Shape 2: a stated value's `source` is `said`."""
    return _renamed(value, "goal", "said")


def _goal(value):
    return _renamed(value, "said", "goal")


def _rewrite(change, after):
    conn = op.get_bind()
    for table, (columns, old, new) in COLUMNS.items():
        stamp = new if after else old
        rows = conn.execute(sa.text(f"SELECT id, {', '.join(columns)} FROM {table}")).all()
        for row_id, *values in rows:
            sets = ", ".join(f"{c} = CAST(:{c} AS jsonb)" for c in columns)
            conn.execute(
                sa.text(f"UPDATE {table} SET {sets}, shape_version = :stamp WHERE id = :id"),
                {**{c: None if v is None else json.dumps(change(v))
                    for c, v in zip(columns, values, strict=True)},
                 "stamp": stamp, "id": row_id})


def upgrade():
    if not context.is_offline_mode():
        _rewrite(upgrade_said, True)
    for table, (_columns, _old, new) in COLUMNS.items():
        op.alter_column(table, "shape_version", server_default=sa.text(str(new)))


def downgrade():
    if not context.is_offline_mode():
        _rewrite(_goal, False)
    for table, (_columns, old, _new) in COLUMNS.items():
        op.alter_column(table, "shape_version", server_default=sa.text(str(old)))
