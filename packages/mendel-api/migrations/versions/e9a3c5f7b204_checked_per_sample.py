"""A step in a proposal's previews lists the tool rules checked per sample (#466): shape 7.

Every shape-6 step had none, so the upgrader writes an empty list on each step."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "e9a3c5f7b204"
down_revision = "d8f2b6c4a917"
branch_labels = None
depends_on = None


def _steps(value, change):
    if isinstance(value, list):
        return [_steps(v, change) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: _steps(v, change) for k, v in value.items()}
    if isinstance(out.get("settings"), list) and "ports" in out and "process" in out:
        out = change(out)
    return out


def upgrade_pipeline_authoring_proposal_6_to_7(previews):
    """Shape 7 says which tool rules each step checks per sample."""
    return None if previews is None else _steps(
        previews, lambda step: {"checked_per_sample": [], **step})


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
        _rewrite(upgrade_pipeline_authoring_proposal_6_to_7, 7)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("7"))


def downgrade():
    def drop(previews):
        return _steps(previews, lambda step: {k: v for k, v in step.items()
                                              if k != "checked_per_sample"})
    if not context.is_offline_mode():
        _rewrite(drop, 6)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("6"))
