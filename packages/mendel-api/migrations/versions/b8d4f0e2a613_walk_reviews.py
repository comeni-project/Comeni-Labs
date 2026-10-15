"""the walk reviews — its place is the steps reviewed; its pacing and gaps are one policy

Spec §14.6 of the consultant build: the draft is a projection of the blueprint, so the walk's
place is the set of steps a person (or the engine, placing quietly) has reviewed, not a cursor
into one blueprint's order. Pacing and whether registry gaps stop the walk are stored together.
No data migration (old sessions are dropped, as in 3b).

Revision ID: b8d4f0e2a613
Revises: a7c3e9d1f402
Create Date: 2026-10-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4f0e2a613"
down_revision: str | None = "a7c3e9d1f402"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("pipeline_authoring_session", "cursor")
    op.drop_column("pipeline_authoring_session", "pacing")
    op.add_column("pipeline_authoring_session", sa.Column("reviewed", sa.JSON(), nullable=True))
    op.add_column("pipeline_authoring_session", sa.Column("policy", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_authoring_session", "policy")
    op.drop_column("pipeline_authoring_session", "reviewed")
    op.add_column("pipeline_authoring_session", sa.Column("pacing", sa.String(24), nullable=True))
    op.add_column(
        "pipeline_authoring_session",
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
    )
