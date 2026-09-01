"""artifact name

Revision ID: c8e2b1d94f37
Revises: a4f1c07be5d2
Create Date: 2026-09-01 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e2b1d94f37'
down_revision: Union[str, Sequence[str], None] = 'a4f1c07be5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """What a person called this pipeline, carried across the courier — Plan 6 phase 2.

    **Nothing is back-filled and nothing can be.** The name lives in `mendel-api`'s
    `pipeline_draft` table, in the other service's database; an artifact already uploaded has
    no route back to the draft it came from. Every existing row keeps `""`, which the run
    header reads as *no name* and draws `run <id>` — the same thing it drew yesterday.

    Default `""` rather than nullable: an unnamed pipeline and a pipeline named nothing are the
    same fact here, and two spellings of one absence is what a reader has to remember.
    """
    op.add_column("run_artifact",
                  sa.Column("name", sa.String(length=200), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("run_artifact", "name")
