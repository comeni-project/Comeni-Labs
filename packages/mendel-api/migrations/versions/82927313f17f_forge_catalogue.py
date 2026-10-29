"""The forge's catalogue: each sync, and each upstream module the last good sync read (#362)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "82927313f17f"
down_revision = "d2a6c8e4f1b7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "catalogue_sync",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("commit", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("modules", sa.Integer(), nullable=True),
        sa.Column("problems", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint("outcome IN ('running', 'ok', 'failed')", name=op.f("ck_catalogue_sync_outcome")),
    )
    op.create_table(
        "catalogue_module",
        sa.Column("shape_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("source", sa.String(32), primary_key=True),
        sa.Column("path", sa.String(255), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tool_version", sa.String(64), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.String(64)), nullable=False),
        sa.Column("formats", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("upstream_changed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search", sa.Text(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("seen_in", sa.Integer(),
                  sa.ForeignKey("catalogue_sync.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gone", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_catalogue_module_name", "catalogue_module", ["name"])
    op.create_index("ix_catalogue_module_tool_version", "catalogue_module", ["tool_version"])
    op.create_index("ix_catalogue_module_seen_in", "catalogue_module", ["seen_in"])
    op.create_index("ix_catalogue_module_topics", "catalogue_module", ["topics"],
                    postgresql_using="gin")
    op.create_index("ix_catalogue_module_formats", "catalogue_module", ["formats"],
                    postgresql_using="gin")
    op.create_index("ix_catalogue_module_search", "catalogue_module", ["search"],
                    postgresql_using="gin", postgresql_ops={"search": "gin_trgm_ops"})


def downgrade():
    op.drop_table("catalogue_module")
    op.drop_table("catalogue_sync")
