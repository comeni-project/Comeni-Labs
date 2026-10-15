"""Convert the frozen legacy snapshot, then remove duplicate live authorities.

Writers must be stopped and a verified backup retained before the online upgrade.
Downgrade cannot reconstruct later decisions; restoring that backup is the rollback.
"""

from datetime import UTC, datetime

from alembic import context, op
from sqlalchemy import Column, Integer, text

revision = "a8c2d6e4b053"
down_revision = "f7b1c5d3a942"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        # Schema inspection may render the chain. Executing that script must fail before
        # dropping anything: data interpretation requires the frozen online snapshot.
        op.execute(
            "DO $$ BEGIN RAISE EXCEPTION "
            "'Decision cutover requires an online upgrade and verified backup'; END $$"
        )
    else:
        op.add_column("pipeline_want_revision", Column("states_order", Integer(), nullable=True))
        op.create_check_constraint(
            op.f("ck_pipeline_want_revision_states_order_nonnegative"),
            "pipeline_want_revision",
            "states_order >= 0",
        )
        from mendel_api.migration_data.decisions_v1 import Conversion, apply, convert, snapshots

        connection = op.get_bind()
        authored = set(
            connection.execute(
                text("SELECT id FROM pipeline_draft WHERE ownership='authored'")
            ).scalars()
        )
        captured = datetime.now(UTC)
        for snapshot in snapshots(connection):
            converted = (
                Conversion("already_rows") if snapshot.draft_id in authored else convert(snapshot)
            )
            apply(connection, snapshot, converted, at=captured)
        remaining = connection.execute(
            text("""SELECT count(*) FROM pipeline_draft d
            LEFT JOIN pipeline_decision_migration m ON m.draft_id=d.id
            WHERE m.draft_id IS NULL""")
        ).scalar_one()
        if remaining:
            raise RuntimeError("every draft needs an explicit conversion disposition")
    for column in ("facts", "goal", "reviewed", "policy"):
        op.drop_column("pipeline_authoring_session", column)
    op.drop_column("pipeline_draft", "goal")


def downgrade():
    raise RuntimeError("Restore the verified pre-cutover backup; JSON is no longer authoritative.")
