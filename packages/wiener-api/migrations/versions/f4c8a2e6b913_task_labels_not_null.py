"""run_task.labels is never null, as the model has always said

Revision ID: f4c8a2e6b913
Revises: e6b2c4d8f103
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4c8a2e6b913'
down_revision: Union[str, Sequence[str], None] = 'e6b2c4d8f103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Issue 279: the first migration left `labels` nullable while the model declared it not,
    and `alembic check` was the first thing to compare them."""
    op.execute("UPDATE run_task SET labels = '[]' WHERE labels IS NULL")
    op.alter_column("run_task", "labels", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    op.alter_column("run_task", "labels", existing_type=sa.JSON(), nullable=True)
