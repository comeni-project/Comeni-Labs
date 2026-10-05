"""blueprint without mode — a stored blueprint loses the key nothing read

`Blueprint` moved into `mendel-authoring` in 14.7.8.2 without `mode`: every Build/Spawn branch
reads the session row's `mode`, never the blueprint's. The model forbids extra keys, so a stored
blueprint still holding it would fail to load; this removes it once, in SQL, rather than leaving
a validator that drops it on every load forever.

Revision ID: e5f1a9c3b7d2
Revises: c9e4b2d71a38
Create Date: 2026-10-05

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5f1a9c3b7d2"
down_revision: str | None = "c9e4b2d71a38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE pipeline_authoring_session "
        "SET blueprint = (blueprint::jsonb - 'mode')::json "
        "WHERE blueprint::jsonb ? 'mode'"
    )


def downgrade() -> None:
    # Every blueprint ever stored was resolved under Build or Spawn; the row's own `mode` says
    # which, so the downgrade copies it back rather than guessing.
    op.execute(
        "UPDATE pipeline_authoring_session "
        "SET blueprint = (blueprint::jsonb || jsonb_build_object('mode', mode))::json "
        "WHERE blueprint::jsonb <> '{}'::jsonb AND NOT blueprint::jsonb ? 'mode'"
    )
