"""What each Wiener JSON column holds, and the refusal of a row in an older shape (spec §3).

`SHAPES` is what the golden test pins; the load check reads only `VERSIONS`. **A row is refused,
never misread.** `run_event.payload` is Nextflow's, shaped by `admit()`, so it is registered as
the open object it is.
"""

from dataclasses import dataclass
from typing import Any

from comeni_core.diagnostics import coded
from pydantic import JsonValue
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB

from wiener_api.shape_versions import VERSIONS

Json = JSON().with_variant(JSONB(), "postgresql")
"""Every JSON column's type: `JSONB` in Postgres, plain JSON in the SQLite the suite runs on."""


@dataclass(frozen=True)
class Shape:
    table: str
    column: str
    model: Any  # a type a `TypeAdapter` accepts


class StaleShape(RuntimeError):
    """A row whose `shape_version` is not its table's. Raised on load."""


def _shapes() -> tuple[Shape, ...]:
    from wiener_core.events import EventKind
    from wiener_core.state import Attempt

    return (
        Shape("run", "terminal_seen", list[EventKind]),
        Shape("run_event", "payload", dict[str, JsonValue]),
        Shape("run_task", "attempts", list[Attempt] | None),
        Shape("run_task", "labels", list[str]),
        Shape("wiener_setting", "value", JsonValue),
    )


class _Lazy:
    def __iter__(self):
        return iter(_shapes())

    def __bool__(self):
        return True


SHAPES = _Lazy()


def _check(target, _context) -> None:
    table = getattr(target, "__tablename__", None)
    if table not in VERSIONS:
        return
    found = getattr(target, "shape_version", None)
    if found != VERSIONS[table]:
        raise StaleShape(coded(
            "MW0100",
            f"{table} row {getattr(target, 'id', getattr(target, 'run_id', '?'))} is in shape "
            f"{found}, and this server reads shape {VERSIONS[table]}: run the migrations",
        ))


def install(base) -> None:
    """Refuse every loaded row in an older shape. Called once, from `db.py`."""
    event.listen(base, "load", _check, propagate=True)
    event.listen(base, "refresh", lambda target, context, attrs: _check(target, context),
                 propagate=True)
