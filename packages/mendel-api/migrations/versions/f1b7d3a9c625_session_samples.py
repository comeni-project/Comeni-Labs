"""A session keeps every sample of its last upload, with its name and measurements (#466):
the `samples` column, at session shape 3. Older rows have none, which reads as none."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "f1b7d3a9c625"
down_revision = "e9a3c5f7b204"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_session_2_to_3(samples):
    """Shape 3 adds the samples; a row from before has none."""
    return samples


def _stamp(stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text("UPDATE pipeline_authoring_session SET shape_version = :s"),
                              {"s": stamp})
    op.alter_column("pipeline_authoring_session", "shape_version",
                    server_default=sa.text(str(stamp)))


def upgrade():
    op.add_column("pipeline_authoring_session",
                  sa.Column("samples", postgresql.JSONB(), nullable=True))
    _stamp(3)


def downgrade():
    _stamp(2)
    op.drop_column("pipeline_authoring_session", "samples")
