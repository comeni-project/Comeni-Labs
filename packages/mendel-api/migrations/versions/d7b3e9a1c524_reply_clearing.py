"""A model call can say why its reply text is gone: its draft was deleted, or retention (Part H)."""

import sqlalchemy as sa
from alembic import op

revision = "d7b3e9a1c524"
down_revision = "c4e8a2f6d913"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_invocation", sa.Column("response_cleared", sa.String(16), nullable=True))
    op.add_column("ai_invocation", sa.Column("response_cleared_at", sa.DateTime(timezone=True),
                                             nullable=True))
    op.create_check_constraint(op.f("ck_ai_invocation_response_cleared"), "ai_invocation",
                               "response_cleared IN ('deleted', 'retention')")


def downgrade():
    op.drop_constraint("ck_ai_invocation_response_cleared", "ai_invocation", type_="check")
    op.drop_column("ai_invocation", "response_cleared_at")
    op.drop_column("ai_invocation", "response_cleared")
