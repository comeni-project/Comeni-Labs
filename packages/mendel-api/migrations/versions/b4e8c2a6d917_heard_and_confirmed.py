"""The words a decision was heard in, what was asked and cannot be made, and when the goal was
confirmed (Part I.0 spec §6).

`confirmed_revision` is backfilled from the old inference — a present want meant confirmed —
so every draft confirmed before this reads as confirmed after it, now as a record."""

import sqlalchemy as sa
from alembic import op

revision = "b4e8c2a6d917"
down_revision = "a3f7c9e1b246"
branch_labels = None
depends_on = None

REVISIONS = (
    "pipeline_input_revision",
    "pipeline_want_revision",
    "pipeline_fact_revision",
    "pipeline_producer_revision",
    "pipeline_parameter_revision",
    "pipeline_review_revision",
)

ASKED = (
    """CREATE TABLE pipeline_asked (
        id VARCHAR(32) NOT NULL,
        draft_id VARCHAR(32) NOT NULL,
        subject_key VARCHAR(400) NOT NULL,
        position INTEGER DEFAULT 0 NOT NULL,
        current_id VARCHAR(32) NOT NULL,
        PRIMARY KEY (id),
        CONSTRAINT uq_pipeline_asked_owner UNIQUE (id, draft_id),
        CONSTRAINT uq_pipeline_asked_subject UNIQUE (draft_id, subject_key),
        FOREIGN KEY(draft_id) REFERENCES pipeline_draft (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_pipeline_asked_draft_id ON pipeline_asked (draft_id)""",
    """CREATE TABLE pipeline_asked_revision (
        phrase TEXT NOT NULL,
        present BOOLEAN DEFAULT true NOT NULL,
        id VARCHAR(32) NOT NULL,
        draft_id VARCHAR(32) NOT NULL,
        subject_id VARCHAR(32) NOT NULL,
        seq INTEGER DEFAULT 0 NOT NULL,
        actor_kind VARCHAR(16) DEFAULT 'person' NOT NULL,
        who VARCHAR(200) DEFAULT '' NOT NULL,
        legacy BOOLEAN DEFAULT false NOT NULL,
        action VARCHAR(16) DEFAULT 'select' NOT NULL,
        at TIMESTAMP WITH TIME ZONE NOT NULL,
        turn_id INTEGER,
        proposal_id VARCHAR(32),
        heard TEXT,
        heard_seq INTEGER,
        PRIMARY KEY (id),
        CONSTRAINT uq_pipeline_asked_revision_owner UNIQUE (id, subject_id, draft_id),
        CONSTRAINT fk_pipeline_asked_revision_subject FOREIGN KEY(subject_id, draft_id)
        REFERENCES pipeline_asked (id, draft_id) ON DELETE RESTRICT,
        CONSTRAINT ck_pipeline_asked_revision_unknown_is_legacy CHECK (actor_kind !=
        'unknown' OR legacy),
        CONSTRAINT ck_pipeline_asked_revision_actor_kind CHECK (actor_kind IN ('person',
        'model', 'resolver', 'unknown')),
        CONSTRAINT ck_pipeline_asked_revision_action CHECK (action IN ('select', 'retain',
        'retract', 'inherit', 'import'))
)""",
    """CREATE INDEX ix_pipeline_asked_revision_draft_id ON pipeline_asked_revision (draft_id)""",
    """CREATE INDEX ix_pipeline_asked_revision_subject_id
        ON pipeline_asked_revision (subject_id)""",
    """ALTER TABLE pipeline_asked ADD CONSTRAINT fk_pipeline_asked_current FOREIGN KEY(current_id,
        id, draft_id) REFERENCES pipeline_asked_revision (id, subject_id, draft_id) ON DELETE
        RESTRICT DEFERRABLE INITIALLY DEFERRED""",
)


def upgrade():
    for table in (*REVISIONS, "pipeline_observation"):
        op.add_column(table, sa.Column("heard", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("heard_seq", sa.Integer(), nullable=True))
    for statement in ASKED:
        op.execute(statement)
    op.add_column("pipeline_draft", sa.Column("confirmed_revision", sa.Integer(), nullable=True))
    op.execute(
        """UPDATE pipeline_draft d SET confirmed_revision = d.decision_revision
           WHERE EXISTS (SELECT 1 FROM pipeline_want w
                         JOIN pipeline_want_revision r ON r.id = w.current_id
                         WHERE w.draft_id = d.id AND r.present)"""
    )


def downgrade():
    op.drop_column("pipeline_draft", "confirmed_revision")
    op.execute("ALTER TABLE pipeline_asked DROP CONSTRAINT fk_pipeline_asked_current")
    op.drop_table("pipeline_asked_revision")
    op.drop_table("pipeline_asked")
    for table in (*REVISIONS, "pipeline_observation"):
        op.drop_column(table, "heard_seq")
        op.drop_column(table, "heard")
