"""A tool a person keeps whole (#466, stage 6): the `whole` decision family, a subject and a
revision table like `role`, and a step in a proposal's previews says whether it runs on parts.

A suggestion's or a turn's change may now be `whole` (suggestion shape 5, turn shape 9); every
older one is already in it. Every shape-8 preview step ran whole, so its upgrader writes `null`
(proposal shape 9). A grain may now be `part`, which no stored draft graph has (draft shape 4)."""

import json

import sqlalchemy as sa
from alembic import context, op

revision = "c4e0f6a8b532"
down_revision = "b3d9e5f7a421"
branch_labels = None
depends_on = None


def upgrade_pipeline_authoring_suggestion_4_to_5(change):
    """Shape 5 lets a change be `whole`; every older one is already in it."""
    return change


def upgrade_pipeline_draft_3_to_4(graph):
    """Shape 4 lets a port's grain be `part`; no shape-3 graph has one."""
    return graph


def upgrade_pipeline_authoring_turn_8_to_9(blocks):
    """Shape 9 lets a block's change be `whole`; every older one is already in it."""
    return blocks


def _steps(value, change):
    if isinstance(value, list):
        return [_steps(v, change) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: _steps(v, change) for k, v in value.items()}
    if isinstance(out.get("settings"), list) and "ports" in out and "process" in out:
        out = change(out)
    return out


def upgrade_pipeline_authoring_proposal_8_to_9(previews):
    """Shape 9 says whether each step runs on parts; none did before."""
    return None if previews is None else _steps(previews, lambda step: {"parts": None, **step})


def _rewrite(change, stamp):
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, preview_views FROM pipeline_authoring_proposal")).all()
    for row_id, previews in rows:
        conn.execute(
            sa.text("UPDATE pipeline_authoring_proposal "
                    "SET preview_views = CAST(:previews AS jsonb), shape_version = :stamp "
                    "WHERE id = :id"),
            {"previews": None if previews is None else json.dumps(change(previews)),
             "stamp": stamp, "id": row_id})


def _stamp(table: str, stamp: int) -> None:
    if not context.is_offline_mode():
        op.get_bind().execute(sa.text(f"UPDATE {table} SET shape_version = :s"), {"s": stamp})
    op.alter_column(table, "shape_version", server_default=sa.text(str(stamp)))


def upgrade():
    op.create_table('pipeline_whole',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('draft_id', sa.String(length=32), nullable=False),
    sa.Column('subject_key', sa.String(length=400), nullable=False),
    sa.Column('position', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('current_id', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['draft_id'], ['pipeline_draft.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('draft_id', 'subject_key', name='uq_pipeline_whole_subject'),
    sa.UniqueConstraint('id', 'draft_id', name='uq_pipeline_whole_owner')
    )
    op.create_index(op.f('ix_pipeline_whole_draft_id'), 'pipeline_whole', ['draft_id'], unique=False)
    op.create_table('pipeline_whole_revision',
    sa.Column('contract', sa.String(length=200), nullable=False),
    sa.Column('whole', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('draft_id', sa.String(length=32), nullable=False),
    sa.Column('subject_id', sa.String(length=32), nullable=False),
    sa.Column('seq', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('actor_kind', sa.Enum('person', 'model', 'resolver', 'unknown', name='actor_kind', native_enum=False, create_constraint=True, length=16), server_default=sa.text("'person'"), nullable=False),
    sa.Column('who', sa.String(length=200), server_default=sa.text("''"), nullable=False),
    sa.Column('legacy', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('action', sa.Enum('select', 'retain', 'retract', 'inherit', 'import', name='action', native_enum=False, create_constraint=True, length=16), server_default=sa.text("'select'"), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('turn_id', sa.Integer(), nullable=True),
    sa.Column('proposal_id', sa.String(length=32), nullable=True),
    sa.Column('heard', sa.Text(), nullable=True),
    sa.Column('heard_seq', sa.Integer(), nullable=True),
    sa.CheckConstraint("actor_kind != 'unknown' OR legacy", name=op.f('ck_pipeline_whole_revision_unknown_is_legacy')),
    sa.ForeignKeyConstraint(['subject_id', 'draft_id'], ['pipeline_whole.id', 'pipeline_whole.draft_id'], name='fk_pipeline_whole_revision_subject', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'subject_id', 'draft_id', name='uq_pipeline_whole_revision_owner')
    )
    op.create_index(op.f('ix_pipeline_whole_revision_draft_id'), 'pipeline_whole_revision', ['draft_id'], unique=False)
    op.create_index(op.f('ix_pipeline_whole_revision_subject_id'), 'pipeline_whole_revision', ['subject_id'], unique=False)
    op.execute(
        "ALTER TABLE pipeline_whole ADD CONSTRAINT fk_pipeline_whole_current "
        "FOREIGN KEY(current_id, id, draft_id) REFERENCES pipeline_whole_revision "
        "(id, subject_id, draft_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED"
    )
    _stamp("pipeline_authoring_suggestion", 5)
    _stamp("pipeline_authoring_turn", 9)
    _stamp("pipeline_draft", 4)
    if not context.is_offline_mode():
        _rewrite(upgrade_pipeline_authoring_proposal_8_to_9, 9)
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("9"))


def downgrade():
    def drop(previews):
        return _steps(previews, lambda step: {k: v for k, v in step.items() if k != "parts"})
    if not context.is_offline_mode():
        _rewrite(drop, 8)
        op.execute("DELETE FROM pipeline_authoring_suggestion WHERE change->>'kind' = 'whole'")
    op.alter_column("pipeline_authoring_proposal", "shape_version", server_default=sa.text("8"))
    _stamp("pipeline_authoring_suggestion", 4)
    _stamp("pipeline_authoring_turn", 8)
    _stamp("pipeline_draft", 3)
    op.execute("ALTER TABLE pipeline_whole DROP CONSTRAINT fk_pipeline_whole_current")
    op.drop_index(op.f('ix_pipeline_whole_revision_subject_id'), table_name='pipeline_whole_revision')
    op.drop_index(op.f('ix_pipeline_whole_revision_draft_id'), table_name='pipeline_whole_revision')
    op.drop_table('pipeline_whole_revision')
    op.drop_index(op.f('ix_pipeline_whole_draft_id'), table_name='pipeline_whole')
    op.drop_table('pipeline_whole')
