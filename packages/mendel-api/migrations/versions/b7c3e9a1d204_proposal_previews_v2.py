"""A proposal's previews at shape 2: each setting says whether it is optional (#384).

`SettingView.optional` is new. A shape-1 row has none, and reading it as `false` would show a
saved preview's optional value as one that needs the person, so the upgrader derives it from
the setting's route as the server does: `ext` and `directive` leave the tool its own behaviour.
The rule is copied here rather than imported, because an upgrader reads JSON, never today's
model."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "b7c3e9a1d204"
down_revision = "89d3b4e5ab6f"
branch_labels = None
depends_on = None

_OMITTABLE = ("ext", "directive")


def _settings(value, change):
    if isinstance(value, dict):
        out = {k: _settings(v, change) for k, v in value.items()}
        if isinstance(out.get("settings"), list):
            out["settings"] = [change(s) if isinstance(s, dict) else s for s in out["settings"]]
        return out
    if isinstance(value, list):
        return [_settings(v, change) for v in value]
    return value


def upgrade_pipeline_authoring_proposal_1_to_2(previews):
    """Shape 2 adds `optional` to every setting a preview's frame draws."""
    if previews is None:
        return None
    return _settings(previews, lambda s: {**s, "optional": s.get("via") in _OMITTABLE})


def _without_optional(previews):
    if previews is None:
        return None
    return _settings(previews, lambda s: {k: v for k, v in s.items() if k != "optional"})


def _rewrite(change, stamp):
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, preview_views FROM pipeline_authoring_proposal")).all()
    for row_id, previews in rows:
        conn.execute(
            sa.text("UPDATE pipeline_authoring_proposal "
                    "SET preview_views = CAST(:previews AS jsonb), shape_version = :stamp "
                    "WHERE id = :id"),
            {"previews": None if previews is None else json.dumps(change(previews)),
             "stamp": stamp, "id": row_id})


def upgrade():
    if not context.is_offline_mode():
        _rewrite(upgrade_pipeline_authoring_proposal_1_to_2, 2)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("2"))


def downgrade():
    if not context.is_offline_mode():
        _rewrite(_without_optional, 1)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("1"))
