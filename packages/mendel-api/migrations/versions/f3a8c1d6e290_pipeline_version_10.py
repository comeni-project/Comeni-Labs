"""A session's blueprint holds a whole `pipeline.yml`, and version 10 (#507) adds only
`CallArg.pad`, left out when 0. A version-9 blueprint is a version-10 one with its version moved,
so the session opens as before. Written here rather than imported: an upgrader reads JSON, never
today's model.

No backward compatibility before v0.1.0: downgrade refuses; restore a verified backup."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "f3a8c1d6e290"
down_revision = "d6a2e9b4f017"
branch_labels = None
depends_on = None


def upgrade_blueprint_9_to_10(blueprint):
    """The blueprint with its pipeline at version 10; anything else unchanged."""
    if not isinstance(blueprint, dict):
        return blueprint
    pipeline = blueprint.get("pipeline")
    if isinstance(pipeline, dict) and pipeline.get("version") == 9:
        return {**blueprint, "pipeline": {**pipeline, "version": 10}}
    return blueprint


def upgrade() -> None:
    if context.is_offline_mode():
        return
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, blueprint FROM pipeline_authoring_session")).all()
    for row_id, blueprint in rows:
        moved = upgrade_blueprint_9_to_10(blueprint)
        if moved is not blueprint:
            conn.execute(
                sa.text("UPDATE pipeline_authoring_session "
                        "SET blueprint = CAST(:blueprint AS jsonb) WHERE id = :id"),
                {"blueprint": json.dumps(moved), "id": row_id})


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
