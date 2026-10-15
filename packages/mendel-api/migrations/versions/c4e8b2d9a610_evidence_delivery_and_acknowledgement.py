"""Evidence delivery is idempotent; acknowledged observations do not reopen old questions.

Revision ID: c4e8b2d9a610
Revises: a9d6e4f2b817
"""

from alembic import op

revision = "c4e8b2d9a610"
down_revision = "a9d6e4f2b817"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE pipeline_observation ADD COLUMN ingestion_key VARCHAR(128)")
    op.execute(
        "ALTER TABLE pipeline_observation ADD CONSTRAINT "
        "uq_pipeline_observation_ingestion_subject "
        "UNIQUE (draft_id, ingestion_key, subject)"
    )
    op.execute("ALTER TABLE pipeline_evidence_access ADD COLUMN acknowledged_as VARCHAR(16)")
    op.execute("ALTER TABLE pipeline_evidence_access ADD COLUMN acknowledged_revision INTEGER")
    op.execute("ALTER TABLE pipeline_evidence_access ADD COLUMN acknowledged_at TIMESTAMPTZ")
    op.execute("ALTER TABLE pipeline_evidence_access ADD COLUMN acknowledged_by VARCHAR(200)")
    op.execute("ALTER TABLE pipeline_evidence_access ADD COLUMN acknowledged_kind VARCHAR(16)")
    op.execute(
        "ALTER TABLE pipeline_evidence_access ADD CONSTRAINT "
        "ck_pipeline_evidence_access_acknowledged_as CHECK "
        "(acknowledged_as IN ('agreement', 'retained', 'selected', 'obsolete'))"
    )
    op.execute(
        "ALTER TABLE pipeline_evidence_access ADD CONSTRAINT "
        "ck_pipeline_evidence_access_acknowledged_kind CHECK "
        "(acknowledged_kind IN ('person', 'model', 'resolver', 'unknown'))"
    )
    op.execute(
        "ALTER TABLE pipeline_evidence_access ADD CONSTRAINT "
        "ck_pipeline_evidence_access_complete_acknowledgement CHECK "
        "((acknowledged_as IS NULL AND acknowledged_revision IS NULL AND "
        "acknowledged_at IS NULL AND acknowledged_by IS NULL AND acknowledged_kind IS NULL) "
        "OR (acknowledged_as IS NOT NULL AND acknowledged_revision IS NOT NULL AND "
        "acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL AND "
        "acknowledged_kind IS NOT NULL AND acknowledged_kind != 'unknown'))"
    )

    # Freeze the new protocol vocabulary in this migration, independent of runtime enums.
    for table, column, values in (
        (
            "pipeline_authoring_session",
            "phase",
            "'understanding', 'gathering', 'goal_review', "
            "'resolving', 'building', 'complete', 'failed', 'correcting', 'stopped'",
        ),
        (
            "pipeline_authoring_session",
            "failed_from",
            "'understanding', 'gathering', 'goal_review', "
            "'resolving', 'building', 'complete', 'failed', 'correcting', 'stopped'",
        ),
        ("pipeline_authoring_proposal", "kind", "'step', 'goal', 'gap', 'pacing', 'disagreement'"),
    ):
        name = f"ck_{table}_{column}"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({column} IN ({values}))")
    op.execute("ALTER TABLE pipeline_authoring_proposal ALTER COLUMN by TYPE VARCHAR(200)")


def downgrade():
    raise RuntimeError("restore a backup: dropping retained evidence acknowledgements is lossy")
