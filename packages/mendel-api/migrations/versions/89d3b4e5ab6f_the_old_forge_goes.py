"""The old forge's tables go (forge MVP part 0, #361).

Dropped in foreign-key order. `ai_invocation` stays, and so do its rows whose `agent` is
`forge`: `forge_message` referenced them, never the reverse. The new forge is designed from
scratch (`docs/superpowers/specs/2026-10-19-forge-mvp-design.md`) and brings its own tables."""

from alembic import op

revision = "89d3b4e5ab6f"
down_revision = "a9d4e2c7b318"
branch_labels = None
depends_on = None

OLD_TABLES = (
    "forge_message",
    "forge_event",
    "forge_revision",
    "forge_adaptation",
    "forge_catalogue_item",
    "forge_source_snapshot",
    "source_check",
    "queue_visit",
)


def upgrade():
    for table in OLD_TABLES:
        op.drop_table(table)


def downgrade():
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
