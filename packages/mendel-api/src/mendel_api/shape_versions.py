"""Which shape each table's JSON is in (spec §3). **Numbers only, importing nothing**, so
`models.py` can stamp its tables without importing the models that type their columns.

Bump a table's number when any of its JSON columns changes shape, in the same commit as the
migration that rewrites every row of that table into the new shape (its upgrader is a plain
function in that migration, reading and returning JSON, never today's model) and sets the
stamp. `tests/test_shapes.py`'s goldens refuse a changed shape at an unchanged number.
"""

from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, mapped_column

VERSIONS: dict[str, int] = {
    "ai_invocation": 1,
    "catalogue_module": 1,
    "installation_setting": 1,
    "pipeline_authoring_proposal": 2,
    "pipeline_authoring_session": 1,
    "pipeline_authoring_suggestion": 2,
    "pipeline_authoring_turn": 4,
    "pipeline_decision_migration": 1,
    "pipeline_draft": 1,
    "pipeline_exclusion_revision": 1,
    "pipeline_input_revision": 1,
    "pipeline_observation": 1,
    "pipeline_parameter_revision": 1,
    "pipeline_phrasing": 1,
    "pipeline_producer_revision": 1,
    "pipeline_want_revision": 1,
}


def stamp(table: str) -> Mapped[int]:
    """The `shape_version` column: written by the ORM and by a raw `INSERT` alike, since the
    server default carries the number (`decisions_v1` inserts in SQL)."""
    return mapped_column(Integer, nullable=False, default=VERSIONS[table],
                         server_default=text(str(VERSIONS[table])))
