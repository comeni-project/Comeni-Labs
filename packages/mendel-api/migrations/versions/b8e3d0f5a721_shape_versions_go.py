"""Shape versions go (#511): no row carries a `shape_version` stamp any more. There is no backward
compatibility before v0.1.0, so a migration that changes a JSON column's shape rewrites or drops
what it holds, and nothing checks a row's shape on load.

No backward compatibility before v0.1.0: downgrade refuses; restore a verified backup."""

from alembic import op

revision = "b8e3d0f5a721"
down_revision = "a7d2c9e4f610"
branch_labels = None
depends_on = None

TABLES = (
    "ai_invocation", "analysis_data", "catalogue_module", "forge_adaptation", "forge_message",
    "forge_revision", "forge_step", "installation_setting", "pipeline_authoring_session",
    "pipeline_authoring_turn", "pipeline_decision_migration", "pipeline_draft",
    "pipeline_exclusion_revision", "pipeline_input_revision", "pipeline_observation",
    "pipeline_parameter_revision", "pipeline_producer_revision", "pipeline_want_revision",
    "rule_proposal",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS shape_version")


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
