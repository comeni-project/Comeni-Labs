"""Grain (#466) in the two stored shapes `e6c4a2f8b913` left out: a session's blueprint, which
holds a whole `pipeline.yml` (shape 2), and a forge revision's value (shape 2).

A blueprint is version 8 with `scope` on its channels; version 9 differs only in naming the
channel's grain, so it is renamed and its version moved, and the session opens as before. A
forge revision may hold a drafted type with `scope: run`, or a contract input dumped with
`cardinality: "1"` (always written then) or `"*"`. `"1"` was the default and is dropped; `"*"`
is `grain: study, many: true`. Written here rather than imported: an upgrader reads JSON, never
today's model."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "b3d9f5a1c7e2"
down_revision = "e6c4a2f8b913"
branch_labels = None
depends_on = None

_UP = {"run": "study", "sample": "sample"}


def _grained(value):
    if isinstance(value, list):
        return [_grained(v) for v in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, inner in value.items():
        if key == "scope" and isinstance(inner, str):
            out["grain"] = _UP.get(inner, inner)
        elif key == "cardinality" and inner in ("1", "*"):
            if inner == "*":
                out["grain"], out["many"] = "study", True
        else:
            out[key] = _grained(inner)
    return out


def upgrade_pipeline_authoring_session_1_to_2(blueprint):
    """Shape 2 is a version-9 pipeline: a channel names its grain."""
    if not isinstance(blueprint, dict):
        return blueprint
    upgraded = _grained(blueprint)
    pipeline = upgraded.get("pipeline")
    if isinstance(pipeline, dict) and pipeline.get("version") == 8:
        upgraded["pipeline"] = {**pipeline, "version": 9}
    return upgraded


def upgrade_forge_revision_1_to_2(value):
    """Shape 2 names a drafted type's grain, and a contract input's grain and `many`."""
    return _grained(value)


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
    ("pipeline_authoring_session", "blueprint", 1, 2, upgrade_pipeline_authoring_session_1_to_2),
    ("forge_revision", "value", 1, 2, upgrade_forge_revision_1_to_2),
)


def upgrade():
    for table, column, _, new, change in _MOVES:
        if not context.is_offline_mode():
            _rewrite(table, column, change, new)
        op.alter_column(table, "shape_version", server_default=sa.text(str(new)))


def downgrade():
    """Restamps only: a version-9 blueprint is not rewritten back, since nothing older reads
    it and no user exists before v0.1.0."""
    for table, _, old, _, _ in _MOVES:
        if not context.is_offline_mode():
            op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": old})
        op.alter_column(table, "shape_version", server_default=sa.text(str(old)))
