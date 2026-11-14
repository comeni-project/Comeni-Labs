"""An input that takes several types lists them on the step card (#485): a port in a proposal's
previews carries `accepts` (proposal shape 10). Every shape-9 port showed one type, so its
upgrader writes an empty list."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "b7e3c1d9f046"
down_revision = "a9c4e2f7b815"
branch_labels = None
depends_on = None


def _ports(value, change):
    if isinstance(value, list):
        return [_ports(v, change) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: _ports(v, change) for k, v in value.items()}
    if isinstance(out.get("settings"), list) and "process" in out \
            and isinstance(out.get("ports"), list):
        out["ports"] = [change(p) if isinstance(p, dict) else p for p in out["ports"]]
    return out


def upgrade_pipeline_authoring_proposal_9_to_10(previews):
    """Shape 10 lists the types an input accepts; no shape-9 port listed any."""
    return None if previews is None else _ports(previews, lambda port: {"accepts": [], **port})


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
        _rewrite(upgrade_pipeline_authoring_proposal_9_to_10, 10)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("10"))


def downgrade():
    def drop(previews):
        return _ports(previews, lambda port: {k: v for k, v in port.items() if k != "accepts"})

    if not context.is_offline_mode():
        _rewrite(drop, 9)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("9"))
