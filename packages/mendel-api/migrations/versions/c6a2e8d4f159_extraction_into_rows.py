"""A session's stored extraction becomes rows and suggestions, and the column goes (Part I.0
spec §6.1, §6.2).

For a draft whose goal was never confirmed: each wanted type becomes a want revision written by
the model, unquoted (it waits on the goal card as it always did); the model's suggested states
and its stated candidates become pending suggestions. A confirmed draft already holds its goal in
the rows, and what the extraction suggested was settled when the card was decided. The carry is
frozen in `mendel_api.migration_data.extraction_v1`."""

import sqlalchemy as sa
from alembic import context, op

revision = "c6a2e8d4f159"
down_revision = "c1d5f9b3e264"
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():
        from mendel_api.migration_data import extraction_v1

        conn = op.get_bind()
        rows = conn.execute(sa.text(
            "SELECT s.id, s.draft_id, s.extraction FROM pipeline_authoring_session s "
            "JOIN pipeline_draft d ON d.id = s.draft_id "
            "WHERE s.extraction IS NOT NULL AND d.confirmed_revision IS NULL")).all()
        for session_id, draft_id, extraction in rows:
            extraction_v1.carry(conn, session_id, draft_id, extraction)
    op.drop_column("pipeline_authoring_session", "extraction")


def downgrade():
    op.add_column("pipeline_authoring_session",
                  sa.Column("extraction", sa.dialects.postgresql.JSONB(), nullable=True))
