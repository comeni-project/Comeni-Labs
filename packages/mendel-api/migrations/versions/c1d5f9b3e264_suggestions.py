"""The model's suggestions, waiting for a click (Part I.0 spec §5.3)."""

import sqlalchemy as sa
from alembic import op

revision = "c1d5f9b3e264"
down_revision = "b4e8c2a6d917"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pipeline_authoring_suggestion",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(32),
                  sa.ForeignKey("pipeline_authoring_session.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("change", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("heard", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("invocation_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("state IN ('pending', 'applied', 'dismissed', 'stale')",
                           name="state"),
    )
    op.create_index("ix_pipeline_authoring_suggestion_session_id",
                    "pipeline_authoring_suggestion", ["session_id"])
    op.create_index("ix_pipeline_authoring_suggestion_state",
                    "pipeline_authoring_suggestion", ["state"])


def downgrade():
    op.drop_table("pipeline_authoring_suggestion")
