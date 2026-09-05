"""forge_event records the state it moved from

Archiving became legal from five states rather than one on 2026-09-05, and until then every
`archived` event came from `review` — so the column would have said nothing and its absence cost
nothing. It costs something now: an adaptation archived from `scaffolding` and one archived after
a failure are the same row in history without it, and they are very different stories.

Nullable, because an event may record something that is not a transition. A sentinel like `""`
would be a state name that is not one, and every reader would have to know that.

Revision ID: d3b81c5a4f07
Revises: a1f4c7d20e93
Create Date: 2026-09-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3b81c5a4f07"
down_revision: str | None = "a1f4c7d20e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column.

    **No backfill.** Existing rows genuinely do not know what state they moved from — the fact
    was never recorded — and writing `review` into every historical `archived` event would be
    inventing an audit trail, which is worse than a null that says *this was written before the
    column existed*.
    """
    op.add_column("forge_event", sa.Column("from_state", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("forge_event", "from_state")
