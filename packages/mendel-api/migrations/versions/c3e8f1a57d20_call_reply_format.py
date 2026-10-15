"""which reply format a model call used — 14.7.4 (#194)

`reply_format`: `in_prompt` when the schema was written into the prompt, or the provider format
the server enforced (`ollama`, …). A reader of a refused call needs to know whether the shape
was enforced. Old rows stay null: nothing recorded it.

Revision ID: c3e8f1a57d20
Revises: b7d2e9a41c60
Create Date: 2026-09-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e8f1a57d20"
down_revision: str | None = "b7d2e9a41c60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_invocation", sa.Column("reply_format", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_invocation", "reply_format")
