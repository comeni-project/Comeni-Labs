"""The catalogue's formats, by side, with mentions kept apart (the registry redesign)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3e7a1f94b20"
down_revision = "d5f1b82e9a07"
branch_labels = None
depends_on = None

COLUMNS = ("formats_in", "formats_out", "mentions_in", "mentions_out")


def upgrade():
    for name in COLUMNS:
        op.add_column("catalogue_module", sa.Column(
            name, postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"))
    # As stored upstream: the next sync folds spellings together and finds the mentions.
    for name in COLUMNS[:2]:
        op.execute(f"""
            UPDATE catalogue_module SET {name} = ARRAY(
                SELECT left(value, 32) FROM jsonb_array_elements_text(document->'{name}'))
        """)
    op.drop_index("ix_catalogue_module_formats", table_name="catalogue_module")
    op.drop_column("catalogue_module", "formats")
    for name in COLUMNS[:2]:
        op.create_index(f"ix_catalogue_module_{name}", "catalogue_module", [name],
                        postgresql_using="gin")


def downgrade():
    for name in COLUMNS[:2]:
        op.drop_index(f"ix_catalogue_module_{name}", table_name="catalogue_module")
    op.add_column("catalogue_module", sa.Column(
        "formats", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"))
    op.execute("UPDATE catalogue_module SET formats = formats_in || formats_out")
    op.create_index("ix_catalogue_module_formats", "catalogue_module", ["formats"],
                    postgresql_using="gin")
    for name in COLUMNS:
        op.drop_column("catalogue_module", name)
