"""Reserve explicit frozen conversion provenance before the authority cutover."""

from alembic import op

revision = "f7b1c5d3a942"
down_revision = "e6a0b4f2c831"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE pipeline_decision_migration (
        draft_id VARCHAR(32) PRIMARY KEY REFERENCES pipeline_draft(id) ON DELETE RESTRICT,
        version VARCHAR(16) NOT NULL, disposition VARCHAR(24) NOT NULL,
        reason VARCHAR(24), at TIMESTAMPTZ NOT NULL, snapshot JSON NOT NULL,
        CONSTRAINT ck_pipeline_decision_migration_disposition CHECK
        (disposition IN ('already_rows','manual','confirmed','manual_confirmed','gathering',
                         'understanding','ambiguous_manual','obsolete_protocol'))
    )""")


def downgrade():
    raise RuntimeError("Restore a verified backup rather than erase retained legacy provenance.")
