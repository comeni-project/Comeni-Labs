"""Every Wiener JSON column is registered, its shape is pinned, and a row in an older shape is
refused (Part H spec §3). `mendel_api`'s `test_shapes.py` is the same contract: the two
services share no code, so it is written twice.
"""

import json
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
import wiener_rows
from pydantic import TypeAdapter
from sqlalchemy.orm import sessionmaker
from wiener_api import models  # noqa: F401 — fills Base.metadata
from wiener_api.db import Base
from wiener_postgres import URL, reachable

GOLDEN = Path(__file__).parent / "golden" / "shapes"
needs_db = pytest.mark.skipif(not reachable(), reason="needs WIENER_TEST_DATABASE_URL")


@pytest.fixture
def pg_session():
    engine = sa.create_engine(URL)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.rollback()
    session.close()
    engine.dispose()


def _json_columns() -> set[tuple[str, str]]:
    found = {(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns
             if isinstance(c.type, sa.JSON)}
    assert found, "the census found no JSON column — the models were not imported"
    return found


def _structure(schema):
    """A JSON Schema without its prose: a docstring is not a shape."""
    if isinstance(schema, dict):
        return {k: ({n: _structure(f) for n, f in v.items()} if k == "properties"
                    else _structure(v))
                for k, v in schema.items() if k not in ("description", "title")}
    if isinstance(schema, list):
        return [_structure(v) for v in schema]
    return schema


def test_every_json_column_is_registered():
    from wiener_api.shapes import SHAPES

    assert _json_columns() == {(s.table, s.column) for s in SHAPES}


def test_every_registered_table_carries_a_stamp_at_its_version():
    from wiener_api.shape_versions import VERSIONS
    from wiener_api.shapes import SHAPES

    tables = {s.table for s in SHAPES}
    assert tables, "nothing is registered"
    assert set(VERSIONS) == tables
    for table in tables:
        column = Base.metadata.tables[table].c.shape_version
        assert column.server_default.arg.text == str(VERSIONS[table]), table


def test_each_shape_matches_its_golden():
    """A changed model at an unchanged version fails here. `COMENI_WRITE_GOLDEN=1` writes a
    missing golden."""
    from wiener_api.shape_versions import VERSIONS
    from wiener_api.shapes import SHAPES

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
            "bump it in shape_versions.py and add a migration that rewrites the rows")


@needs_db
def test_a_run_in_an_older_shape_is_refused(pg_session):
    from wiener_api import repository
    from wiener_api.settings import settings
    from wiener_api.shapes import StaleShape

    row = wiener_rows.a_run(pg_session)
    pg_session.execute(sa.text("UPDATE run SET shape_version = 0 WHERE id = :id"), {"id": row.id})
    pg_session.expire_all()
    with pytest.raises(StaleShape, match="MW0100"):
        repository.run(pg_session, settings.lab_id, row.id)


@needs_db
def test_every_json_column_is_jsonb_in_the_database(pg_session):
    rows = pg_session.execute(sa.text(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND data_type IN ('json', 'jsonb')")).all()
    assert rows, "no JSON column in the database"
    narrow = [tuple(r) for r in rows if r.data_type != "jsonb"]
    assert {r.data_type for r in rows} == {"jsonb"}, narrow


@needs_db
def test_the_attempt_filters_count_a_task_with_no_attempts_as_one(pg_session):
    """`jsonb_array_length` refuses a scalar where `json_array_length` was asked of a JSON
    `null`: a task with `attempts = null` must still count as attempt 1, not fail the query."""
    from wiener_api import repository
    from wiener_api.models import RunTask
    from wiener_api.settings import settings
    from wiener_api.task_query import TaskQuery
    from wiener_core.events import TaskStatus

    run = wiener_rows.a_run(pg_session, phase="running")
    for task_id, attempts in ((1, None), (2, []), (3, [{}, {}])):
        pg_session.add(RunTask(run_id=run.id, lab_id=settings.lab_id, task_id=task_id,
                               process="P", status=TaskStatus.COMPLETED, attempts=attempts,
                               last_change_ms=0))
    pg_session.flush()
    first = repository.tasks_page(pg_session, settings.lab_id, run.id, TaskQuery(attempt=1))
    retried = repository.tasks_page(pg_session, settings.lab_id, run.id,
                                    TaskQuery(retried_only=True))
    assert sorted(t.task_id for t in first) == [1, 2]
    assert [t.task_id for t in retried] == [3]
