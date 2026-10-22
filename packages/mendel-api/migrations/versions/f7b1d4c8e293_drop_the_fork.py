"""No fork (one builder, #395): a hand edit is intent in the goal, so nothing a re-plan does can
lose it, and a correction never moves to a linked copy. `ownership` and the four fork columns go.

No backward compatibility before v0.1.0: a draft forked before this stays a separate pipeline,
no longer linked to the one it came from. The downgrade puts the columns back empty."""

from alembic import op

revision = "f7b1d4c8e293"
down_revision = "e5c3a9d7b2f1"
branch_labels = None
depends_on = None


def upgrade():
    for constraint in ("ck_pipeline_draft_complete_fork", "uq_pipeline_draft_fork",
                       "fk_pipeline_draft_forked_from", "ck_pipeline_draft_ownership"):
        op.execute(f"ALTER TABLE pipeline_draft DROP CONSTRAINT IF EXISTS {constraint}")
    for column in ("fork_key", "fork_sequence", "fork_at", "forked_from", "ownership"):
        op.execute(f"ALTER TABLE pipeline_draft DROP COLUMN {column}")


def downgrade():
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN ownership VARCHAR(16) "
               "DEFAULT 'authored' NOT NULL")
    op.execute("ALTER TABLE pipeline_draft ADD CONSTRAINT ck_pipeline_draft_ownership "
               "CHECK (ownership IN ('authored', 'manual'))")
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN forked_from VARCHAR(32)")
    op.execute("ALTER TABLE pipeline_draft ADD CONSTRAINT fk_pipeline_draft_forked_from "
               "FOREIGN KEY (forked_from) REFERENCES pipeline_draft(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN fork_key VARCHAR(64)")
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN fork_sequence INTEGER")
    op.execute("ALTER TABLE pipeline_draft ADD COLUMN fork_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE pipeline_draft ADD CONSTRAINT uq_pipeline_draft_fork "
               "UNIQUE (forked_from, fork_key)")
    op.execute(
        "ALTER TABLE pipeline_draft ADD CONSTRAINT ck_pipeline_draft_complete_fork CHECK "
        "((forked_from IS NULL AND fork_key IS NULL AND fork_sequence IS NULL AND fork_at IS NULL) "
        "OR (forked_from IS NOT NULL AND fork_key IS NOT NULL AND fork_sequence IS NOT NULL "
        "AND fork_at IS NOT NULL AND forked_from != id))")
