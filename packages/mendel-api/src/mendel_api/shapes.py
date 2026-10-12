"""What each JSON column holds, and the refusal of a row in an older shape (spec §3).

`SHAPES` is what the golden test pins: a column's JSON Schema at its table's version. The load
check reads only `VERSIONS`. **A row is refused, never misread**: a stale stamp means a
migration did not run over it, and guessing its shape is the failure issue 276 named.
"""

from dataclasses import dataclass
from typing import Any

from comeni_core.diagnostics import coded
from pydantic import JsonValue
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB

from mendel_api.shape_versions import VERSIONS

Json = JSON().with_variant(JSONB(), "postgresql")
"""Every JSON column's type: `JSONB` in Postgres, plain JSON where a test runs on SQLite."""


@dataclass(frozen=True)
class Shape:
    table: str
    column: str
    model: Any  # a type a `TypeAdapter` accepts


class StaleShape(RuntimeError):
    """A row whose `shape_version` is not its table's. Raised on load."""


def _shapes() -> tuple[Shape, ...]:
    from comeni_core.goal.profile import Evidence
    from comeni_core.plan.draft import DraftGraph
    from comeni_core.spell.marks import ParamValue
    from mendel_authoring.payloads import Extraction
    from mendel_forge.ai.schemas import Citation
    from mendel_forge.catalogue import CatalogueItem

    from mendel_api.authoring.canvas import AlternativePreview
    from mendel_api.authoring.types import AskedGap, Block
    from mendel_api.migration_data.decisions_v1 import Snapshot

    loose = dict[str, JsonValue]
    return (
        Shape("ai_invocation", "input_digests", dict[str, str]),
        Shape("forge_catalogue_item", "metadata", CatalogueItem),
        Shape("forge_message", "citations", list[Citation]),
        Shape("forge_revision", "manifest", loose),
        Shape("forge_revision", "validation", loose),
        Shape("forge_revision", "prompt_versions", dict[str, str]),
        Shape("forge_source_snapshot", "counts", loose),
        Shape("forge_source_snapshot", "filters", list[loose]),
        Shape("forge_source_snapshot", "warnings", list[loose]),
        Shape("installation_setting", "value", JsonValue),
        Shape("pipeline_authoring_proposal", "payload", loose),
        Shape("pipeline_authoring_proposal", "preview_views", dict[str, AlternativePreview] | None),
        Shape("pipeline_authoring_session", "extraction", Extraction | None),
        Shape("pipeline_authoring_session", "blueprint", loose),
        Shape("pipeline_authoring_turn", "blocks", list[Block]),
        Shape("pipeline_decision_migration", "snapshot", Snapshot),
        Shape("pipeline_draft", "graph", DraftGraph),
        Shape("pipeline_draft", "provenance", loose),
        Shape("pipeline_input_revision", "states", list[str]),
        Shape("pipeline_observation", "value", ParamValue | list[ParamValue] | None),
        Shape("pipeline_observation", "pieces", list[str]),
        Shape("pipeline_observation", "evidence", Evidence | None),
        Shape("pipeline_parameter_revision", "value", JsonValue),
        Shape("pipeline_phrasing", "asked", AskedGap | None),
        Shape("pipeline_producer_revision", "states", list[str]),
        Shape("pipeline_want_revision", "states", list[str]),
    )


class _Lazy:
    """`SHAPES` imports the models lazily, so importing this module from `db.py` cycles nothing."""

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
            "MI0400",
            f"{table} row {getattr(target, 'id', getattr(target, 'key', '?'))} is in shape "
            f"{found}, and this server reads shape {VERSIONS[table]}: run the migrations",
        ))


def install(base) -> None:
    """Refuse every loaded row in an older shape. Called once, from `db.py`."""
    event.listen(base, "load", _check, propagate=True)
    event.listen(base, "refresh", lambda target, context, attrs: _check(target, context),
                 propagate=True)
