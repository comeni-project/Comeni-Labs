"""A measured fact may say how much of the data it was read from (`coverage`, #465), wherever a
fact or its evidence is stored: proposals (shape 4), turns (6), the draft's graph, observations
and catalogue modules (2).

The field is absent on every older row and reads as unset, so every older row is already in the
new shape: each upgrader returns it unchanged and the migration moves the stamps."""

import sqlalchemy as sa
from alembic import context, op

revision = "d4a7c2e9b815"
down_revision = "b8e2d4f6a1c3"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_proposal_3_to_4(preview_views):
    """Shape 4 adds a premise's and an evidence's coverage, absent until a measurer sets it."""
    return preview_views


def upgrade_pipeline_authoring_turn_5_to_6(blocks):
    """Shape 6 adds an inspected fact's coverage, absent until a measurer sets it."""
    return blocks


def upgrade_pipeline_draft_1_to_2(graph):
    """Shape 2 adds a premise's and an evidence's coverage, absent until a measurer sets it."""
    return graph


def upgrade_pipeline_observation_1_to_2(evidence):
    """Shape 2 adds evidence's coverage, absent on every fact recorded before it."""
    return evidence


def upgrade_catalogue_module_1_to_2(document):
    """Shape 2 adds coverage to the evidence a module's document may carry."""
    return document


def _stamp(table, stamp):
    op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": stamp})


_MOVES = (
    ("pipeline_authoring_proposal", 3, 4),
    ("pipeline_authoring_turn", 5, 6),
    ("pipeline_draft", 1, 2),
    ("pipeline_observation", 1, 2),
    ("catalogue_module", 1, 2),
)


def upgrade():
    for table, _, new in _MOVES:
        if not context.is_offline_mode():
            _stamp(table, new)
        op.alter_column(table, "shape_version", server_default=sa.text(str(new)))


def downgrade():
    for table, old, _ in _MOVES:
        if not context.is_offline_mode():
            _stamp(table, old)
        op.alter_column(table, "shape_version", server_default=sa.text(str(old)))
