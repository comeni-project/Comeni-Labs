"""task resource columns

Revision ID: 03b19a9f28d7
Revises: 7c7286bda2b0
Create Date: 2026-08-24 22:04:34.234251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03b19a9f28d7'
down_revision: Union[str, Sequence[str], None] = '7c7286bda2b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Three derived columns and the labels column — A191 and A200.

    **Nothing is back-filled, deliberately.** These are derived from `run_event`, which is the
    source of truth, so an old run re-projects if anybody needs it. A migration that rewrites
    history is a worse risk than three nulls, and a null already means the honest thing here:
    nothing was reported.
    """
    op.add_column("run_task", sa.Column("peak_rss_bytes", sa.BigInteger(), nullable=True))
    op.add_column("run_task", sa.Column("realtime_ms", sa.BigInteger(), nullable=True))
    op.add_column("run_task", sa.Column("pct_cpu", sa.Float(), nullable=True))
    op.add_column("run_task", sa.Column("labels", sa.JSON(), nullable=True))

    # Only the two the Tasks tab sorts on. `pct_cpu` is read, never ordered by, and `labels`
    # is deliberately unindexed — A200: the column exists so a row can say `sample_07`, not so
    # a deployment can be searched for a patient.
    op.create_index("ix_run_task_peak_rss_bytes", "run_task", ["peak_rss_bytes"])
    op.create_index("ix_run_task_realtime_ms", "run_task", ["realtime_ms"])


def downgrade() -> None:
    """Drop all five — the two indexes first, then the four columns."""
    op.drop_index("ix_run_task_realtime_ms", table_name="run_task")
    op.drop_index("ix_run_task_peak_rss_bytes", table_name="run_task")
    op.drop_column("run_task", "labels")
    op.drop_column("run_task", "pct_cpu")
    op.drop_column("run_task", "realtime_ms")
    op.drop_column("run_task", "peak_rss_bytes")
