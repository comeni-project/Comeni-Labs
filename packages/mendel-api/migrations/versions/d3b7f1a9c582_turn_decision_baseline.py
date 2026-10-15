"""The decisions as they stood when the person spoke, on the turn that answers them (Part I.0,
review I3)."""

import sqlalchemy as sa
from alembic import op

revision = "d3b7f1a9c582"
down_revision = "c6a2e8d4f159"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pipeline_authoring_turn",
                  sa.Column("base_decision_revision", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("pipeline_authoring_turn", "base_decision_revision")
