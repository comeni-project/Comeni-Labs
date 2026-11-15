"""The scripted walk goes (#463): the builder is an agent, so the walk's tables and the session's
place in it are dropped, and a stored turn keeps only the blocks the agent's thread draws.

Dropped: `pipeline_authoring_proposal` (the walk's offers), `pipeline_authoring_suggestion`
(changes a model offered beside them), `pipeline_phrasing` (a gap question's cached wording), and
the session's `phase`, `failed_from`, `at`, `pacing` and `show_gaps`.

**Turn shape 12.** A block of the walk's kinds becomes the agent's `message` when it carried
words (a narrative's text, a receipt's summary, a notice's text) and is dropped when it did not
(a goal card, a question, a step offer, a setting request, a change set): those were drawn from
proposals that no longer exist. A notice of a kind the agent does not raise becomes a message.

No backward compatibility before v0.1.0: downgrade refuses; restore a verified backup."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "e5a9c3f1b742"
down_revision = "d4b7e1a9c250"
branch_labels = None
depends_on = None

AGENT = {"message", "tool", "ask"}
NOTICES = {"refusal", "limit"}
WORDS = {"narrative": "text", "receipt": "summary", "notice": "text"}


def upgrade_pipeline_authoring_turn_11_to_12(blocks):
    """The agent's blocks stay; the walk's become a message, or go when they held no words."""
    kept = []
    for block in blocks or []:
        kind = block.get("kind")
        if kind in AGENT or (kind == "notice" and block.get("notice") in NOTICES):
            kept.append(block)
        elif kind in WORDS and block.get(WORDS[kind]):
            kept.append({"kind": "message", "id": block["id"], "text": block[WORDS[kind]]})
    return kept


def upgrade() -> None:
    if not context.is_offline_mode():
        bind = op.get_bind()
        rows = bind.execute(sa.text("SELECT id, blocks FROM pipeline_authoring_turn")).all()
        for row_id, blocks in rows:
            bind.execute(sa.text("UPDATE pipeline_authoring_turn SET blocks = "
                                 "CAST(:b AS jsonb), shape_version = 12 WHERE id = :i"),
                         {"b": json.dumps(upgrade_pipeline_authoring_turn_11_to_12(blocks)),
                          "i": row_id})
    op.alter_column("pipeline_authoring_turn", "shape_version", server_default=sa.text("12"))
    op.drop_table("pipeline_authoring_suggestion")
    op.drop_table("pipeline_authoring_proposal")
    op.drop_table("pipeline_phrasing")
    for column in ("phase", "failed_from", "at", "pacing", "show_gaps"):
        op.drop_column("pipeline_authoring_session", column)


def downgrade() -> None:
    raise RuntimeError("No backward compatibility before v0.1.0: restore a verified backup.")
