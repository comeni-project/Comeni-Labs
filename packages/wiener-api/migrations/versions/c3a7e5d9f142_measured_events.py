"""a run's measurements are events of its own kind

Revision ID: c3a7e5d9f142
Revises: b8d2f4a6c159
Create Date: 2026-11-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = 'c3a7e5d9f142'
down_revision: Union[str, Sequence[str], None] = 'b8d2f4a6c159'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BEFORE = ["started", "process_submitted", "process_started", "process_completed", "completed",
          "error", "heartbeat", "cancelled"]
AFTER = [*BEFORE, "measured"]


def _in(values: list[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _kinds(values: list[str]) -> None:
    op.drop_constraint(op.f("ck_run_event_kind"), "run_event", type_="check")
    op.create_check_constraint(op.f("ck_run_event_kind"), "run_event", f"kind IN ({_in(values)})")


def upgrade_run_1_to_2(terminal_seen):
    """Shape 2 lets `terminal_seen` name `measured`, which is never terminal: no row changes."""
    return terminal_seen


def upgrade_run_event_1_to_2(payload):
    """Shape 2 adds a `measured` fact and a `decided` value, absent on every older event."""
    return payload


def _stamp(table: str, stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": stamp})
    op.alter_column(table, "shape_version", server_default=sa.text(str(stamp)))


def upgrade() -> None:
    """#465: what a run measured is read from its results when it completes, as Wiener's own
    `measured` events. Spelled out, not imported: a migration is history."""
    _kinds(AFTER)
    _stamp("run", 2)
    _stamp("run_event", 2)


def downgrade() -> None:
    op.execute("DELETE FROM run_event WHERE kind = 'measured'")
    _kinds(BEFORE)
    _stamp("run_event", 1)
    _stamp("run", 1)
