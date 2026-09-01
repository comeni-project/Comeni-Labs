"""task tag column

Revision ID: a4f1c07be5d2
Revises: 03b19a9f28d7
Create Date: 2026-09-01 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4f1c07be5d2'
down_revision: Union[str, Sequence[str], None] = '03b19a9f28d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """One derived column so a run's tasks can be filtered by tag.

    **Not indexed, and that is the design rather than an omission.** A191 earned its two
    indexes by sorting a whole deployment's rows; this filter is always inside
    `(lab_id, run_id)`, which is indexed already, so the scan is bounded by one run. A200
    withheld a search across a deployment for a patient, and an unindexed column reachable
    only under a run id cannot become one.

    **Nothing is back-filled**, for the reason 03b19a9f28d7 gives: `run_event` is the source
    of truth and an old run re-projects if anybody needs it. A null here means the honest
    thing — this run was ingested before tags were projected, so it has none.
    """
    op.add_column("run_task", sa.Column("tag", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("run_task", "tag")
