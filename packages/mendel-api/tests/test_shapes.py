"""Every JSON column is registered, its shape is pinned, and a row in an older shape is refused.

Spec §3. A shape change without a version bump fails the golden; a column added without a
registration fails the census; a stale stamp is refused on load, never misread.
"""

import json
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from mendel_api import models  # noqa: F401 — fills Base.metadata (and imports decision_models)
from mendel_api.db import Base, session_scope
from mendel_postgres import reachable
from pydantic import TypeAdapter

GOLDEN = Path(__file__).parent / "golden" / "shapes"
needs_db = pytest.mark.skipif(not reachable(), reason="no database")


def _json_columns() -> set[tuple[str, str]]:
    found = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns
             if isinstance(c.type, sa.JSON) or isinstance(getattr(c.type, "impl", None), sa.JSON)
             or c.type.__class__.__name__ in ("JSONB", "Variant")}
    assert found, "the census found no JSON column — the models were not imported"
    return found


def test_every_json_column_is_registered():
    from mendel_api.shapes import SHAPES

    registered = {(s.table, s.column) for s in SHAPES}
    assert _json_columns() == registered


def test_every_registered_table_carries_a_stamp_at_its_version():
    from mendel_api.shape_versions import VERSIONS
    from mendel_api.shapes import SHAPES

    tables = {s.table for s in SHAPES}
    assert tables, "nothing is registered"
    assert set(VERSIONS) == tables
    for table in tables:
        column = Base.metadata.tables[table].c.shape_version
        assert column.server_default.arg.text == str(VERSIONS[table]), table


def _structure(schema):
    """A JSON Schema without its prose: a docstring is not a shape, and editing one must not
    demand a version bump."""
    if isinstance(schema, dict):
        return {k: ({n: _structure(f) for n, f in v.items()} if k == "properties"
                    else _structure(v))
                for k, v in schema.items() if k not in ("description", "title")}
    if isinstance(schema, list):
        return [_structure(v) for v in schema]
    return schema


def test_each_shape_matches_its_golden():
    """A changed model with an unchanged version fails here: bump the version, write an
    upgrader and its migration (spec §3.3). `COMENI_WRITE_GOLDEN=1` writes a missing golden."""
    from mendel_api.shape_versions import VERSIONS
    from mendel_api.shapes import SHAPES

    assert SHAPES
    for shape in SHAPES:
        path = GOLDEN / f"{shape.table}.{shape.column}.v{VERSIONS[shape.table]}.json"
        schema = json.dumps(_structure(TypeAdapter(shape.model).json_schema()), indent=2,
                            sort_keys=True)
        if os.environ.get("COMENI_WRITE_GOLDEN") == "1" and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(schema + "\n")
        assert path.exists(), f"{path.name} missing: run with COMENI_WRITE_GOLDEN=1 and review"
        assert path.read_text() == schema + "\n", (
            f"{shape.table}.{shape.column} changed shape at version {VERSIONS[shape.table]}: "
            "bump it in shape_versions.py and add an upgrader and a migration")


@needs_db
def test_a_row_in_an_older_shape_is_refused_not_misread():
    from mendel_api.models import InstallationSetting
    from mendel_api.shapes import StaleShape

    with session_scope() as db:
        db.execute(sa.text("DELETE FROM installation_setting WHERE key = 'test.stale'"))
        db.execute(sa.text(
            "INSERT INTO installation_setting (key, value, updated_at, updated_by, shape_version) "
            "VALUES ('test.stale', '1'::jsonb, now(), 't', 0)"))
    with pytest.raises(StaleShape, match="MI0400"), session_scope() as db:
        db.get(InstallationSetting, "test.stale")
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM installation_setting WHERE key = 'test.stale'"))


@needs_db
def test_every_json_column_is_jsonb_in_the_database():
    with session_scope() as db:
        rows = db.execute(sa.text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND data_type IN ('json', 'jsonb')")).all()
    assert rows, "no JSON column in the database"
    narrow = [tuple(r) for r in rows if r.data_type != "jsonb"]
    assert {r.data_type for r in rows} == {"jsonb"}, narrow


def _canon(value):
    """A JSON value with every object's keys sorted and every list left as it is: what JSONB
    keeps (values, list order) and nothing it does not (object key order)."""
    if isinstance(value, dict):
        return {k: _canon(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canon(v) for v in value]
    return value


@needs_db
def test_a_walked_offer_keeps_every_value_and_list_order_through_a_reload(g_case):
    """JSONB orders object keys by length, then bytes; it keeps lists. Nothing a person sees
    reads an object's key order: cards draw lists, the API sorts option ids
    (`routes/authoring.py`), and a gap's prompt rebuilds its options from the engine. So the
    guard is that every value and every list survives, and the options read back sorted."""
    from mendel_api.authoring import envelopes
    from mendel_api.models import PipelineAuthoringProposal
    from mendel_api.services import session as facade

    with session_scope() as db:
        stored, views = db.execute(
            sa.select(PipelineAuthoringProposal.payload, PipelineAuthoringProposal.preview_views)
            .where(PipelineAuthoringProposal.id == g_case.proposal_id)).one()
    written = envelopes.parse(stored, kind=stored["offer"]).model_dump(mode="json")
    assert _canon(stored) == _canon(written)
    assert stored["preview_options"], "no alternative was previewed — measuring nothing"
    assert sorted(views) == sorted(stored["preview_options"])
    shown = facade.read(g_case.session_id)["pending_proposal"]
    assert shown["payload"]["preview_options"] == written["preview_options"]
