"""session at — the protocol node an authoring session rests on

One column on `pipeline_authoring_session` (14.7.8.1): the node of
`mendel_authoring.protocol.PROTOCOL` the session rests on, written by the dispatcher and by
nothing else. **Nullable, and not backfilled**: a null `at` is derived from the phase, the
pending proposal and the pending turn (`services/session.rests_at`), so every existing row is
valid after this and the first move writes its real node. A backfill in SQL would be a second
copy of that derivation, which is the one place it must not drift.

Revision ID: c9e4b2d71a38
Revises: d5a1c7e93b20
Create Date: 2026-10-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e4b2d71a38"
down_revision: str | None = "d5a1c7e93b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pipeline_authoring_session", sa.Column("at", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_authoring_session", "at")
