"""the projection holds what the fold needs, so ingest restores it rather than replaying

Revision ID: e6b2c4d8f103
Revises: d5a83f1e7c92
Create Date: 2026-10-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6b2c4d8f103'
down_revision: Union[str, Sequence[str], None] = 'd5a83f1e7c92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Issue 282: every event replayed the run's whole record to learn the state before it.
    The fold's facts that no column held are added, so `wiener_core.state.restore` can rebuild
    that state from `run` and `run_task`, and `seq` is taken from `run.last_seq` under the run's
    row lock instead of `max + 1` with none.

    **`last_seq` is back-filled from the record**, because it is what the next `seq` is taken
    from. The other facts are not: nothing is live (operator, issue 277), and a run recorded
    before this is rebuilt correctly by `projection.state_of`.
    """
    op.add_column('run', sa.Column('last_seq', sa.Integer(), nullable=False,
                                   server_default='-1'))
    op.add_column('run', sa.Column('last_activity_ms', sa.BigInteger(), nullable=True))
    op.add_column('run', sa.Column('started_at_ms', sa.BigInteger(), nullable=True))
    op.add_column('run', sa.Column('terminal_seen', sa.JSON(), nullable=False,
                                   server_default='[]'))
    op.add_column('run', sa.Column('run_succeeded', sa.Boolean(), nullable=True))
    op.add_column('run_task', sa.Column('first_seen_ms', sa.BigInteger(), nullable=True))
    op.execute(
        "UPDATE run SET last_seq = sub.top FROM "
        "(SELECT run_id, max(seq) AS top FROM run_event GROUP BY run_id) AS sub "
        "WHERE run.id = sub.run_id"
    )


def downgrade() -> None:
    op.drop_column('run_task', 'first_seen_ms')
    for column in ('run_succeeded', 'terminal_seen', 'started_at_ms', 'last_activity_ms',
                   'last_seq'):
        op.drop_column('run', column)
