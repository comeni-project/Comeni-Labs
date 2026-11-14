"""A run-time setting reads several facts (#466): a proposal's previews (shape 6) show each fact
and where it comes from, where shape 5 showed one fact and its measurer.

Every shape-5 lookup read one measured fact, so it becomes a list of one, measured in the run."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "d8f2b6c4a917"
down_revision = "c7e1a4d9f305"
branch_labels = None
depends_on = None


def _views(value, change):
    if isinstance(value, list):
        return [_views(v, change) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: _views(v, change) for k, v in value.items()}
    if isinstance(out.get("at_run"), dict):
        out["at_run"] = change(out["at_run"])
    return out


def _up(view):
    if "facts" in view:
        return view
    rest = {k: v for k, v in view.items() if k not in ("fact", "measured_by")}
    return {**rest, "facts": [{"fact": view.get("fact"), "source": "measured",
                               "said": "measured in the run",
                               "measured_by": view.get("measured_by")}]}


def _down(view):
    facts = view.get("facts") or [{}]
    rest = {k: v for k, v in view.items() if k != "facts"}
    return {**rest, "fact": facts[0].get("fact"), "measured_by": facts[0].get("measured_by")}


def upgrade_pipeline_authoring_proposal_5_to_6(previews):
    """Shape 6 lists a run-time setting's facts, each with where it comes from."""
    return None if previews is None else _views(previews, _up)


def _rewrite(change, stamp):
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, preview_views FROM pipeline_authoring_proposal")).all()
    for row_id, previews in rows:
        conn.execute(
            sa.text("UPDATE pipeline_authoring_proposal "
                    "SET preview_views = CAST(:previews AS jsonb), shape_version = :stamp "
                    "WHERE id = :id"),
            {"previews": None if previews is None else json.dumps(_views(previews, change)),
             "stamp": stamp, "id": row_id})


def upgrade():
    if not context.is_offline_mode():
        _rewrite(_up, 6)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("6"))


def downgrade():
    if not context.is_offline_mode():
        _rewrite(_down, 5)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("5"))
