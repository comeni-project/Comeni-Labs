"""A suggestion may be the engine's reading of a hand edit (one builder, #395): `edit` groups the
readings of one edit, `says` is the engine's sentence. Both empty on every existing row."""

import sqlalchemy as sa
from alembic import op

revision = "e5c3a9d7b2f1"
down_revision = "d2a6b8f4c1e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pipeline_authoring_suggestion", sa.Column("edit", sa.String(32), nullable=True))
    op.add_column("pipeline_authoring_suggestion", sa.Column("says", sa.Text(), nullable=True))
    op.create_index("ix_pipeline_authoring_suggestion_edit", "pipeline_authoring_suggestion",
                    ["edit"])


def downgrade():
    op.drop_index("ix_pipeline_authoring_suggestion_edit", "pipeline_authoring_suggestion")
    op.drop_column("pipeline_authoring_suggestion", "says")
    op.drop_column("pipeline_authoring_suggestion", "edit")
