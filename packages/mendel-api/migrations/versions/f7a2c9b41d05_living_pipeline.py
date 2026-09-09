"""the living pipeline — authoring sessions, turns and proposals

Three tables for the conversation and three columns on `pipeline_draft` for what the
conversation settles. The split is deliberate and is the whole design: the **draft** is what a
build reads, and the **session** is the account of how it came to look that way. Delete every
row in the three new tables and the draft still opens, still validates and still keeps.

**Every existing draft is a valid row after this migration**, which is the property worth
stating rather than assuming. `goal` is null — no goal was ever confirmed, which is true —
`provenance` is `{}`, and `revision` is 0. A draft that has had no authoring turn genuinely is
at revision 0, so the backfill is the correct value rather than a placeholder standing in for a
missing one.

`revision` and `provenance` carry server defaults as well as model defaults. The model default
covers rows this application writes; the server default is what makes the `NOT NULL` legal on a
table that already has rows, and the two must agree — `test_an_old_draft_still_opens_and_keeps`
is what says they do.

Revision ID: f7a2c9b41d05
Revises: d3b81c5a4f07
Create Date: 2026-09-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a2c9b41d05"
down_revision: str | None = "d3b81c5a4f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Three tables and three columns.

    **No cascade anywhere**, which `test_no_foreign_key_cascades` holds for the whole schema. A
    `RESTRICT` on `pipeline_draft` means deleting a draft that has a conversation is refused
    rather than silently taking the transcript with it — the delete is a decision somebody
    should have to make twice.
    """
    op.add_column("pipeline_draft", sa.Column("goal", sa.JSON(), nullable=True))
    op.add_column(
        "pipeline_draft",
        sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "pipeline_draft",
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "pipeline_authoring_session",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("draft_id", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("failed_from", sa.String(length=16), nullable=True),
        sa.Column("goal", sa.JSON(), nullable=True),
        sa.Column("blueprint", sa.JSON(), nullable=False),
        sa.Column("registry_digest", sa.String(length=64), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("who", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["pipeline_draft.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique rather than merely indexed: the MVP has one session per draft, because §2 gives a
    # session one phase and one cursor and two of them would be two answers to *where are we*.
    op.create_index(
        "ix_pipeline_authoring_session_draft_id",
        "pipeline_authoring_session",
        ["draft_id"],
        unique=True,
    )
    op.create_index(
        "ix_pipeline_authoring_session_phase", "pipeline_authoring_session", ["phase"]
    )
    op.create_index("ix_pipeline_authoring_session_who", "pipeline_authoring_session", ["who"])
    op.create_index(
        "ix_pipeline_authoring_session_created_at", "pipeline_authoring_session", ["created_at"]
    )
    op.create_index(
        "ix_pipeline_authoring_session_updated_at", "pipeline_authoring_session", ["updated_at"]
    )

    op.create_table(
        "pipeline_authoring_turn",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("blocks", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("ai_invocation_id", sa.String(length=32), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["pipeline_authoring_session.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["ai_invocation_id"], ["ai_invocation.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_authoring_turn_session_id", "pipeline_authoring_turn", ["session_id"]
    )
    op.create_index("ix_pipeline_authoring_turn_state", "pipeline_authoring_turn", ["state"])
    op.create_index("ix_pipeline_authoring_turn_at", "pipeline_authoring_turn", ["at"])
    # The transcript's order, and unique so it cannot be ambiguous even in principle. `at` is
    # not an ordering: two turns written inside one clock tick sort arbitrarily.
    op.create_index(
        "ix_pipeline_authoring_turn_order",
        "pipeline_authoring_turn",
        ["session_id", "seq"],
        unique=True,
    )

    op.create_table(
        "pipeline_authoring_proposal",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("turn_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("chosen_option", sa.String(length=64), nullable=True),
        sa.Column("by", sa.String(length=16), nullable=True),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["pipeline_authoring_session.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"], ["pipeline_authoring_turn.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_authoring_proposal_session_id",
        "pipeline_authoring_proposal",
        ["session_id"],
    )
    op.create_index("ix_pipeline_authoring_proposal_kind", "pipeline_authoring_proposal", ["kind"])
    op.create_index(
        "ix_pipeline_authoring_proposal_state", "pipeline_authoring_proposal", ["state"]
    )
    op.create_index(
        "ix_pipeline_authoring_proposal_created_at",
        "pipeline_authoring_proposal",
        ["created_at"],
    )
    # **At most one pending proposal per session**, as a partial unique index — the half of the
    # rule that holds when two requests arrive together. `services/authoring.py` refuses first
    # so a person reads a sentence rather than a constraint violation, which is exactly how
    # `ix_forge_adaptation_one_active` is built and for the same reason.
    op.create_index(
        "ix_pipeline_authoring_proposal_one_pending",
        "pipeline_authoring_proposal",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("state = 'pending'"),
    )


def downgrade() -> None:
    """Drop in dependency order — proposals point at turns, turns at sessions.

    The three `pipeline_draft` columns go too. A downgrade genuinely loses the confirmed goal
    and the provenance sidecar, which is what a downgrade is; the graph and the artifact are
    untouched, so what survives is what a build reads.
    """
    op.drop_table("pipeline_authoring_proposal")
    op.drop_table("pipeline_authoring_turn")
    op.drop_table("pipeline_authoring_session")
    op.drop_column("pipeline_draft", "revision")
    op.drop_column("pipeline_draft", "provenance")
    op.drop_column("pipeline_draft", "goal")
