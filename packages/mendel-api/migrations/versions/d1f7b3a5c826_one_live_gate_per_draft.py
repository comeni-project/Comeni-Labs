"""one live gate per draft — a partial unique index over `queued` and `running`

Issue 278: two gates on one draft write into the same directory and stamp the same
`pipeline.yml`. A row still live from a gate the old code left `running` is failed first, so
the index can be built; the sweep does the same from now on.

Revision ID: d1f7b3a5c826
Revises: c9e5a1f3b724
Create Date: 2026-10-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f7b3a5c826"
down_revision: str | None = "c9e5a1f3b724"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE gate_run SET state = 'failed', finished_at = now(), "
        "output = 'MI0004: this gate was lost: no result came back within its time limit' "
        "WHERE state IN ('queued', 'running')"
    )
    op.create_index(
        "ix_gate_run_one_live",
        "gate_run",
        ["draft_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_gate_run_one_live", table_name="gate_run")
