"""A channel's `scope` (`run`/`sample`) is its `grain` (`study`/`sample`) now (#466), wherever a
stored shape keeps one: a proposal's previews (shape 5) and a draft's graph (3).

A draft channel says `scope: run` as a plain string, and an IR channel's override is a resolved
value whose `value` is the string. Both are renamed, and `run` reads `study`. Nothing else is
called `scope` in these columns, so the rewrite renames the key wherever it appears. The rule is
written here rather than imported, because an upgrader reads JSON, never today's model."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "e6c4a2f8b913"
down_revision = "d4a7c2e9b815"
branch_labels = None
depends_on = None

_UP = {"run": "study", "sample": "sample"}
_DOWN = {"study": "run", "sample": "sample"}


def _renamed(value, old: str, new: str, values: dict):
    if isinstance(value, list):
        return [_renamed(v, old, new, values) for v in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, inner in value.items():
        if key == old:
            if isinstance(inner, str):
                inner = values.get(inner, inner)
            elif isinstance(inner, dict) and isinstance(inner.get("value"), str):
                inner = {**inner, "value": values.get(inner["value"], inner["value"])}
            out[new] = _renamed(inner, old, new, values)
        else:
            out[key] = _renamed(inner, old, new, values)
    return out


def upgrade_pipeline_authoring_proposal_4_to_5(previews):
    """Shape 5 names a channel's grain where shape 4 named its scope."""
    return None if previews is None else _renamed(previews, "scope", "grain", _UP)


def upgrade_pipeline_draft_2_to_3(graph):
    """Shape 3 names a drawn channel's grain where shape 2 named its scope."""
    return None if graph is None else _renamed(graph, "scope", "grain", _UP)


def _rewrite(table: str, column: str, change, stamp: int) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"SELECT id, {column} FROM {table}")).all()
    for row_id, document in rows:
        conn.execute(
            sa.text(f"UPDATE {table} SET {column} = CAST(:document AS jsonb), "
                    "shape_version = :stamp WHERE id = :id"),
            {"document": None if document is None else json.dumps(change(document)),
             "stamp": stamp, "id": row_id})


_MOVES = (
    ("pipeline_authoring_proposal", "preview_views", 4, 5, upgrade_pipeline_authoring_proposal_4_to_5),
    ("pipeline_draft", "graph", 2, 3, upgrade_pipeline_draft_2_to_3),
)


def upgrade():
    for table, column, _, new, change in _MOVES:
        if not context.is_offline_mode():
            _rewrite(table, column, change, new)
        op.alter_column(table, "shape_version", server_default=sa.text(str(new)))


def downgrade():
    for table, column, old, _, _ in _MOVES:
        if not context.is_offline_mode():
            _rewrite(table, column, lambda d: _renamed(d, "grain", "scope", _DOWN), old)
        op.alter_column(table, "shape_version", server_default=sa.text(str(old)))
