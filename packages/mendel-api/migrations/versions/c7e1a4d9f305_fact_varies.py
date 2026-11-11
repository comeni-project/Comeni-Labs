"""A fact's origin may be `varies` (#466): a person said it differs between samples, so the
observation carries no value and each sample's comes from the run."""

import sqlalchemy as sa
from alembic import context, op

revision = "c7e1a4d9f305"
down_revision = "b3d9f5a1c7e2"
branch_labels = None
depends_on = None

# Both tables check their origin against `FactOrigin`, so both take the new member. Plain SQL:
# the metadata's naming convention would prefix the name `op` is given.
_TABLES = ("pipeline_observation", "pipeline_input_revision")
_ADD = ("ALTER TABLE {table} ADD CONSTRAINT ck_{table}_origin"
        " CHECK (origin IN ('person_said', 'measured', 'model_read', 'open'{extra}))")


def upgrade_pipeline_authoring_turn_6_to_7(blocks):
    """Shape 7 lets a fact's source be `varies`; every older row is already in it."""
    return blocks


def _stamp(stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text("UPDATE pipeline_authoring_turn SET shape_version = :s"),
                              {"s": stamp})
    op.alter_column("pipeline_authoring_turn", "shape_version",
                    server_default=sa.text(str(stamp)))


def upgrade():
    _stamp(7)
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_origin")
        op.execute(_ADD.format(table=table, extra=", 'varies'"))


def downgrade():
    _stamp(6)
    op.execute("DELETE FROM pipeline_observation WHERE origin = 'varies'")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_origin")
        op.execute(_ADD.format(table=table, extra=""))
