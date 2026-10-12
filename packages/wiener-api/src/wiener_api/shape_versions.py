"""Which shape each Wiener table's JSON is in (Part H spec §3). **Numbers only, importing
nothing**, so `models.py` can stamp its tables. `mendel_api.shape_versions` is the same contract;
the two services share no code, so it is written twice.

Bump a table's number when any of its JSON columns changes shape, in the same commit as the
migration that rewrites every row of that table into the new shape and sets the stamp.
`tests/test_shapes.py`'s goldens refuse a changed shape at an unchanged number.
"""

from sqlalchemy import Integer, text
from sqlalchemy.orm import Mapped, mapped_column

VERSIONS: dict[str, int] = {
    "run": 1,
    "run_event": 1,
    "run_task": 1,
}


def stamp(table: str) -> Mapped[int]:
    """The `shape_version` column, carried by the server default too, so a raw `INSERT` is
    stamped like an ORM one."""
    return mapped_column(Integer, nullable=False, default=VERSIONS[table],
                         server_default=text(str(VERSIONS[table])))
