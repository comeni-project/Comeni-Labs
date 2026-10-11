"""Chooser roles are explicit; legacy names do not imply a role."""

from alembic import op

revision = "e6a0b4f2c831"
down_revision = "d5f9a3e1b720"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE pipeline_authoring_proposal ADD COLUMN actor_kind VARCHAR(16)")
    op.execute(
        "ALTER TABLE pipeline_authoring_proposal ADD CONSTRAINT "
        "ck_pipeline_authoring_proposal_actor_kind CHECK "
        "(actor_kind IN ('person', 'model', 'resolver', 'unknown'))"
    )


def downgrade():
    raise RuntimeError("Restore a verified backup rather than discard attribution.")
