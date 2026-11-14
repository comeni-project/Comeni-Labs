"""A step in a proposal's previews says which samples it takes, when each sample's tool is
chosen per sample (#466): shape 8.

Every shape-7 step took every sample, so the upgrader writes `null` on each step."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "a2c8e4f6b319"
down_revision = "f1b7d3a9c625"
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


def upgrade_pipeline_authoring_proposal_7_to_8(previews):
    """Shape 8 says which samples each step takes; none was a branch before."""
    return None if previews is None else _steps(
        previews, lambda step: {"takes_samples": None, **step})


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
        _rewrite(upgrade_pipeline_authoring_proposal_7_to_8, 8)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("8"))


def downgrade():
    def drop(previews):
        return _steps(previews, lambda step: {k: v for k, v in step.items()
                                              if k != "takes_samples"})
    if not context.is_offline_mode():
        _rewrite(drop, 7)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("7"))
