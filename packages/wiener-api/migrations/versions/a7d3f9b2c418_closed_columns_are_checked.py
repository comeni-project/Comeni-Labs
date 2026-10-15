"""every closed column holds only its enum's values

Revision ID: a7d3f9b2c418
Revises: f4c8a2e6b913
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7d3f9b2c418'
down_revision: Union[str, Sequence[str], None] = 'f4c8a2e6b913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PHASES = ["queued", "launching", "running", "succeeded", "failed", "cancelled", "lost"]

CHECKS = {
    ("run", "phase"): PHASES,
    ("run_event", "kind"): ["started", "process_submitted", "process_started",
                            "process_completed", "completed", "error", "heartbeat", "cancelled"],
    ("run_task", "status"): ["SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "ABORTED", "CACHED"],
    ("run_intent", "kind"): ["relaunch", "cancel", "escalate", "notify", "give_up"],
    ("run_intent", "because"): ["run_failed", "no_events", "operator_request"],
    ("run_intent", "prior_phase"): PHASES,
    ("run_intent", "outcome"): ["signalled", "already_gone"],
}


def _in(values: list[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Issue 274: every `phase`, `kind`, `status` and audit column was a free string, its
    values written down only as a `wiener_core` enum. Spelled out here, not imported: a
    migration is history. `op.f`: the names are complete, and the naming convention would
    otherwise prefix them again. `outcome`'s empty default was never a legal outcome."""
    op.alter_column("run_intent", "outcome", server_default=None)
    for (table, column), values in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_{table}_{column}"), table,
                                   f"{column} IN ({_in(values)})")


def downgrade() -> None:
    for table, column in reversed(list(CHECKS)):
        op.drop_constraint(op.f(f"ck_{table}_{column}"), table, type_="check")
    op.alter_column("run_intent", "outcome", server_default="")
