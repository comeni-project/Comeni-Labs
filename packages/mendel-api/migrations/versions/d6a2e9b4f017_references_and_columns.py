"""An analysis's data keeps its references (study-wide files, each with its type) and a person's
columns, such as condition or batch (#511).

No backward compatibility before v0.1.0: downgrade refuses; restore a verified backup."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d6a2e9b4f017"
down_revision = "c1f4a8d2e930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_data", sa.Column("references", postgresql.JSONB(), nullable=False,
                                             server_default=sa.text("'[]'::jsonb")))
    op.add_column("analysis_data", sa.Column("columns", postgresql.JSONB(), nullable=False,
                                             server_default=sa.text("'{}'::jsonb")))
    op.alter_column("analysis_data", "references", server_default=None)
    op.alter_column("analysis_data", "columns", server_default=None)


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
