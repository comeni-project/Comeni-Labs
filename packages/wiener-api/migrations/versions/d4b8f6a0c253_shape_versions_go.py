"""Shape versions go (#511): no Wiener row carries a `shape_version` stamp any more (no backward
compatibility before v0.1.0).

Downgrade refuses; restore a verified backup."""

from alembic import op

revision = "d4b8f6a0c253"
down_revision = "c3a7e5d9f142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("run", "run_event", "run_task", "wiener_setting"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS shape_version")


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
