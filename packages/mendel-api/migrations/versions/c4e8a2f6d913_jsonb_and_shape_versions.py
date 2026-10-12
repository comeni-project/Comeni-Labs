"""Every JSON column becomes JSONB, and every table holding JSON records its shape (Part H).

**The columns are listed, not discovered**: a migration is a record of what it did, and it must
render offline (`alembic upgrade head --sql`, which `test_migrations.py` reads).
"""

import sqlalchemy as sa
from alembic import op

revision = "c4e8a2f6d913"
down_revision = "b9d3e7f5c164"
branch_labels = None
depends_on = None

COLUMNS = {
    "ai_invocation": ["input_digests"],
    "forge_catalogue_item": ["metadata"],
    "forge_message": ["citations"],
    "forge_revision": ["manifest", "prompt_versions", "validation"],
    "forge_source_snapshot": ["counts", "filters", "warnings"],
    "installation_setting": ["value"],
    "pipeline_authoring_proposal": ["payload", "preview_views"],
    "pipeline_authoring_session": ["blueprint", "extraction"],
    "pipeline_authoring_turn": ["blocks"],
    "pipeline_decision_migration": ["snapshot"],
    "pipeline_draft": ["graph", "provenance"],
    "pipeline_input_revision": ["states"],
    "pipeline_observation": ["evidence", "pieces", "value"],
    "pipeline_parameter_revision": ["value"],
    "pipeline_phrasing": ["asked"],
    "pipeline_producer_revision": ["states"],
    "pipeline_want_revision": ["states"],
}


def upgrade():
    for table, columns in COLUMNS.items():
        for column in columns:
            op.execute(f'ALTER TABLE {table} ALTER COLUMN "{column}" TYPE JSONB '
                       f'USING "{column}"::jsonb')
        op.add_column(table, sa.Column("shape_version", sa.Integer(), nullable=False,
                                       server_default="1"))


def downgrade():
    raise RuntimeError("Restore a verified backup rather than narrow JSONB back to JSON.")
