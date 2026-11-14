"""The builder agent's model calls are recorded with purpose `agent` (#463)."""

from alembic import op

revision = "d4b7e1a9c250"
down_revision = "c2d8f4a1e637"
branch_labels = None
depends_on = None

FORGE = "'analysis', 'implementation', 'repair', 'chat', 'review'"
BEFORE = "'goal', 'family', 'chat', 'tier4'"
AFTER = "'gap', 'ask', 'readback', 'characterise_family', 'characterise'"
"""The builder's purposes either side of `agent`, in `Purpose`'s order, which the check follows."""


def _purposes(builder: str) -> None:
    op.drop_constraint(op.f("ck_ai_invocation_agent_purpose"), "ai_invocation", type_="check")
    op.create_check_constraint(op.f("ck_ai_invocation_agent_purpose"), "ai_invocation",
        f"(agent = 'forge' AND purpose IN ({FORGE})) OR "
        f"(agent = 'builder' AND purpose IN ({builder}))")


def upgrade():
    _purposes(f"{BEFORE}, 'agent', {AFTER}")


def downgrade():
    op.execute("DELETE FROM ai_invocation WHERE agent = 'builder' AND purpose = 'agent'")
    _purposes(f"{BEFORE}, {AFTER}")
