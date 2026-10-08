"""every closed column holds only its enum's values

Issue 274: every `state`, `phase`, `kind` and `role` column was a free string, its allowed
values written down only as a Python enum. The values are spelled out here, not imported: a
migration is history, and an enum that grows later needs its own migration, which the drift
tests (`test_migrations.py`) ask for.

Revision ID: e2a6c8f4b157
Revises: d1f7b3a5c826
Create Date: 2026-10-08

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e2a6c8f4b157"
down_revision: str | None = "d1f7b3a5c826"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASES = ["understanding", "gathering", "goal_review", "resolving", "building", "complete",
          "failed", "stopped"]
ADAPTATION_STATES = ["scaffolding", "queued", "generating", "validating", "review",
                     "changes_requested", "publishing", "published", "failed", "archived"]

CHECKS = {
    ("gate_run", "gate"): ["lint", "preview", "stub", "test"],
    ("gate_run", "state"): ["queued", "running", "passed", "failed"],
    ("forge_adaptation", "state"): ADAPTATION_STATES,
    ("forge_revision", "state"): ["scaffolded", "generating", "validating", "validated",
                                  "superseded", "published", "failed"],
    ("forge_event", "kind"): ["created", "scaffolded", "queued", "claimed", "generated",
                              "validated", "changes_requested", "approved", "published",
                              "archived", "failed", "retried", "reclaimed"],
    ("forge_event", "from_state"): ADAPTATION_STATES,
    ("forge_message", "role"): ["curator", "assistant"],
    ("forge_message", "state"): ["pending", "answered", "failed"],
    ("ai_invocation", "agent"): ["forge", "builder"],
    ("ai_invocation", "state"): ["queued", "running", "succeeded", "failed", "refused"],
    ("pipeline_authoring_session", "phase"): PHASES,
    ("pipeline_authoring_session", "failed_from"): PHASES,
    ("pipeline_authoring_turn", "role"): ["person", "assistant"],
    ("pipeline_authoring_turn", "state"): ["pending", "answered", "failed"],
    ("pipeline_authoring_proposal", "kind"): ["step", "goal", "gap", "pacing"],
    ("pipeline_authoring_proposal", "state"): ["pending", "accepted", "rejected", "stale"],
}
FORGE_PURPOSES = ["analysis", "implementation", "repair", "chat"]
BUILDER_PURPOSES = ["goal", "family", "chat", "tier4", "gap", "ask", "readback",
                    "characterise_family", "characterise"]


# `op.f`: these names are already complete; without it the naming convention in `db.py`
# prefixes them a second time (`ck_gate_run_ck_gate_run_state`).


def _in(values: list[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    for (table, column), values in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_{table}_{column}"), table, f"{column} IN ({_in(values)})")
    op.create_check_constraint(
        op.f("ck_ai_invocation_agent_purpose"), "ai_invocation",
        f"(agent = 'forge' AND purpose IN ({_in(FORGE_PURPOSES)})) OR "
        f"(agent = 'builder' AND purpose IN ({_in(BUILDER_PURPOSES)}))",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ai_invocation_agent_purpose"), "ai_invocation", type_="check")
    for table, column in reversed(list(CHECKS)):
        op.drop_constraint(op.f(f"ck_{table}_{column}"), table, type_="check")
