"""gathering — the facts a session learns before the goal card

One JSON column on `pipeline_authoring_session`: the facts gathering recorded, each with where
it came from (`authoring.types.Fact`). **Every existing session is a valid row after this**:
`[]` is true for a session that never gathered, which every earlier one is. The server default
is what makes `NOT NULL` legal on a table that already has rows, and it agrees with the model's
`default=list`.

The new phases `gathering` and `stopped` need no migration: `phase` is `String(16)` and both
fit.

Revision ID: a4c8e1f26b93
Revises: f7a2c9b41d05
Create Date: 2026-09-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e1f26b93"
down_revision: str | None = "f7a2c9b41d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pipeline_authoring_session",
        sa.Column("facts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("pipeline_authoring_session", "facts")
