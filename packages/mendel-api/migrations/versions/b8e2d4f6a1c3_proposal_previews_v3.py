"""A proposal's preview views at shape 3: a port may say it is optional, its state and why,
what it adds, and when an output is written (#460).

The new fields are absent on every older preview and read as their defaults, so every shape-2
row is already a shape-3 row: the upgrader returns it unchanged and the migration moves the
stamp."""

import sqlalchemy as sa
from alembic import context, op

revision = "b8e2d4f6a1c3"
down_revision = "72bae0eda346"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_proposal_2_to_3(preview_views):
    """Shape 3 adds optional port fields, absent until a tool declares them."""
    return preview_views


def _stamp(stamp):
    op.get_bind().execute(sa.text("UPDATE pipeline_authoring_proposal SET shape_version = :s"),
                          {"s": stamp})


def upgrade():
    if not context.is_offline_mode():
        _stamp(3)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("3"))


def downgrade():
    if not context.is_offline_mode():
        _stamp(2)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("2"))
