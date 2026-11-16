"""An analysis's data keeps its reading rule, the fixes applied on every scan, and the file names
the rule did not fit (#511).

No backward compatibility before v0.1.0: downgrade refuses; restore a verified backup."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1f4a8d2e930"
down_revision = "b8e3d0f5a721"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_data", sa.Column("rule", postgresql.JSONB(), nullable=True))
    op.add_column("analysis_data", sa.Column("fixes", postgresql.JSONB(), nullable=False,
                                             server_default=sa.text("'[]'::jsonb")))
    op.add_column("analysis_data", sa.Column("unfit", postgresql.JSONB(), nullable=False,
                                             server_default=sa.text("'[]'::jsonb")))
    op.alter_column("analysis_data", "fixes", server_default=None)
    op.alter_column("analysis_data", "unfit", server_default=None)


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
