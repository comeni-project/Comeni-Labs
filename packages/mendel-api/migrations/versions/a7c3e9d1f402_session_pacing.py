"""session pacing — `mode` goes with Build and Spawn; the walk's pacing is recorded

Spec §13 of the consultant build: one consultant build, its pacing a setting the Pacing fork
reads and the session records. No data migration (spec §13.1: pre-MVP sessions are dropped).

Revision ID: a7c3e9d1f402
Revises: e5f1a9c3b7d2
Create Date: 2026-10-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c3e9d1f402"
down_revision: str | None = "e5f1a9c3b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("pipeline_authoring_session", "mode")
    op.add_column("pipeline_authoring_session", sa.Column("pacing", sa.String(24), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_authoring_session", "pacing")
    op.add_column(
        "pipeline_authoring_session",
        sa.Column("mode", sa.String(8), nullable=False, server_default="build"),
    )
