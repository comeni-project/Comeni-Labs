"""run_intent, and the launcher's memory

Revision ID: d5a83f1e7c92
Revises: c8e2b1d94f37
Create Date: 2026-09-01 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5a83f1e7c92'
down_revision: Union[str, Sequence[str], None] = 'c8e2b1d94f37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """The audit table §11 asks for, and the three columns that make a verb possible.

    **`run_intent` is not a projection and has no rebuild path**, which is why `wiener.md` §7.1
    now carries an argument for it beside `run_message`'s: nothing can reconstruct who clicked a
    button. The *effect* of a verb does go through the record — `EventKind.CANCELLED` is
    admitted like any other event — and this table is the half the record cannot hold.

    **The three `pid_*` columns are nullable and nothing is back-filled.** A run launched before
    this migration has no recorded process, and `cancel` refuses it by saying exactly that
    rather than signalling a pid it guessed. That refusal is the honest answer and it is
    permanent for those rows: the process is either long gone or unidentifiable, and there is no
    third possibility worth writing code for.
    """
    op.create_table(
        "run_intent",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("lab_id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("because", sa.String(length=32), nullable=False),
        sa.Column("who", sa.String(length=200), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("why", sa.Text(), nullable=False, server_default=""),
        sa.Column("prior_phase", sa.String(length=16), nullable=False),
        sa.Column("resulting_run_id", sa.String(length=32), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default=""),
    )
    # Both, because the two questions an audit gets asked are *what happened to this run* and
    # *what has this laboratory been doing* — and the second is the one a reviewer asks.
    op.create_index("ix_run_intent_run_id", "run_intent", ["run_id"])
    op.create_index("ix_run_intent_lab_id", "run_intent", ["lab_id"])

    op.add_column("run", sa.Column("pid", sa.Integer(), nullable=True))
    op.add_column("run", sa.Column("pid_started_at", sa.Float(), nullable=True))
    op.add_column("run", sa.Column("pid_host", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("run", "pid_host")
    op.drop_column("run", "pid_started_at")
    op.drop_column("run", "pid")
    op.drop_index("ix_run_intent_lab_id", table_name="run_intent")
    op.drop_index("ix_run_intent_run_id", table_name="run_intent")
    op.drop_table("run_intent")
