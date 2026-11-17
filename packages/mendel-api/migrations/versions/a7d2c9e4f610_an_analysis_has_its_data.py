"""An analysis has its data (#511): `analysis_data` holds the folders a person ticked, every file
in them, the samples they pair into and what was measured on each, one row per draft. Samples
live only there now, so the session's `samples` column goes, with every upload it held.

**Turn shape 13.** The agent's question asked for an `upload`; it now points at Data, so an ask
block of shape `upload` becomes shape `data`.

No backward compatibility before v0.1.0: downgrade refuses; restore a verified backup."""

import json

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "a7d2c9e4f610"
down_revision = "e5a9c3f1b742"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_turn_12_to_13(blocks):
    """An `upload` question becomes a `data` one; every other block is unchanged."""
    return [{**b, "shape": "data"} if b.get("kind") == "ask" and b.get("shape") == "upload" else b
            for b in blocks or []]


def upgrade() -> None:
    op.create_table(
        "analysis_data",
        sa.Column("draft_id", sa.String(32),
                  sa.ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("folders", postgresql.JSONB(), nullable=False),
        sa.Column("scan", postgresql.JSONB(), nullable=False),
        sa.Column("files", postgresql.JSONB(), nullable=False),
        sa.Column("samples", postgresql.JSONB(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.drop_column("pipeline_authoring_session", "samples")
    if not context.is_offline_mode():
        bind = op.get_bind()
        rows = bind.execute(sa.text("SELECT id, blocks FROM pipeline_authoring_turn")).all()
        for row_id, blocks in rows:
            bind.execute(sa.text("UPDATE pipeline_authoring_turn SET blocks = "
                                 "CAST(:b AS jsonb), shape_version = 13 WHERE id = :i"),
                         {"b": json.dumps(upgrade_pipeline_authoring_turn_12_to_13(blocks)),
                          "i": row_id})
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("13"))


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
