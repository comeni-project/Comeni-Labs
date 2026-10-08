"""a run's children belong to it, in its lab

Revision ID: b9e5d1a7c320
Revises: a7d3f9b2c418
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b9e5d1a7c320'
down_revision: Union[str, Sequence[str], None] = 'a7d3f9b2c418'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHILDREN = ("run_event", "run_task", "run_intent")


def upgrade() -> None:
    """Issue 274: Wiener had no foreign key, and every child copied `lab_id` with nothing
    making it equal its parent's. Each key is `(lab_id, …)`, so a row in another lab's run
    cannot exist; RESTRICT, as Mendel's are, and nothing here deletes a row."""
    op.create_unique_constraint("uq_run_artifact_lab_id_id", "run_artifact", ["lab_id", "id"])
    op.create_unique_constraint("uq_run_lab_id_id", "run", ["lab_id", "id"])
    op.create_foreign_key("fk_run_artifact", "run", "run_artifact", ["lab_id", "artifact_id"],
                          ["lab_id", "id"], ondelete="RESTRICT")
    for child in CHILDREN:
        op.create_foreign_key(f"fk_{child}_run", child, "run", ["lab_id", "run_id"],
                              ["lab_id", "id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_run_intent_resulting_run", "run_intent", "run",
                          ["lab_id", "resulting_run_id"], ["lab_id", "id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_run_intent_resulting_run", "run_intent", type_="foreignkey")
    for child in reversed(CHILDREN):
        op.drop_constraint(f"fk_{child}_run", child, type_="foreignkey")
    op.drop_constraint("fk_run_artifact", "run", type_="foreignkey")
    op.drop_constraint("uq_run_lab_id_id", "run", type_="unique")
    op.drop_constraint("uq_run_artifact_lab_id_id", "run_artifact", type_="unique")
