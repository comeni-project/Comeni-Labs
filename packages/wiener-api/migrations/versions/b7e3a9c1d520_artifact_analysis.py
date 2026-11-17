"""artifact analysis

Revision ID: b7e3a9c1d520
Revises: d4b8f6a0c253
Create Date: 2026-11-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3a9c1d520'
down_revision: Union[str, Sequence[str], None] = 'd4b8f6a0c253'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Which analysis sent an artifact (#536), carried by the browser like its name. Nothing is
    back-filled: an earlier upload keeps `""` and is placed by its digest, as before."""
    op.add_column("run_artifact",
                  sa.Column("analysis", sa.String(length=64), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("run_artifact", "analysis")
