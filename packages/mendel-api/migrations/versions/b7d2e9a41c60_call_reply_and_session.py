"""a model call's reply, its session, and its cached tokens — 14.7.4 (#182, #191)

Three nullable columns on `ai_invocation`:

- `response`: exactly what the model returned, admitted or refused. **A level-0 store** (#182):
  a reply can echo the person's words, so each future protection level decides whether it is
  kept. Every model finding in the 14.7.3 walk had to be re-called by hand to be read.
- `session_id`: the authoring session a builder call belongs to, so the page can total a
  conversation's tokens (#191). **No foreign key**: a forge row has none, and deleting a session
  must not take its audit rows with it.
- `cached_tokens`: input tokens the provider served from its prompt cache (#183).

Old rows stay null in all three, which is true rather than a placeholder: nothing was kept.

Revision ID: b7d2e9a41c60
Revises: a4c8e1f26b93
Create Date: 2026-09-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2e9a41c60"
down_revision: str | None = "a4c8e1f26b93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_invocation", sa.Column("response", sa.Text(), nullable=True))
    op.add_column("ai_invocation", sa.Column("session_id", sa.String(32), nullable=True))
    op.add_column("ai_invocation", sa.Column("cached_tokens", sa.Integer(), nullable=True))
    op.create_index("ix_ai_invocation_session_id", "ai_invocation", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_invocation_session_id", table_name="ai_invocation")
    op.drop_column("ai_invocation", "cached_tokens")
    op.drop_column("ai_invocation", "session_id")
    op.drop_column("ai_invocation", "response")
