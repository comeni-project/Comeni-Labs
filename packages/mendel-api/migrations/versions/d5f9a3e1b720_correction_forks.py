"""Retain an idempotent correction fork and its parent history cutoff."""

from alembic import op

revision = "d5f9a3e1b720"
down_revision = "c4e8b2d9a610"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN fork_key VARCHAR(64)")
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN fork_sequence INTEGER")
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN fork_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE pipeline_draft ADD CONSTRAINT uq_pipeline_draft_fork "
        "UNIQUE (forked_from, fork_key)"
    )
    op.execute(
        "ALTER TABLE pipeline_draft ADD CONSTRAINT ck_pipeline_draft_complete_fork CHECK "
        "((forked_from IS NULL AND fork_key IS NULL AND fork_sequence IS NULL AND fork_at IS NULL) "
        "OR (forked_from IS NOT NULL AND fork_key IS NOT NULL AND fork_sequence IS NOT NULL "
        "AND fork_at IS NOT NULL AND forked_from != id))"
    )


def downgrade():
    raise RuntimeError("Restore a verified backup; retained correction forks cannot be erased.")
