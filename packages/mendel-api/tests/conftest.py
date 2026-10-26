"""Fixtures for the API tests."""

import pytest
from mendel_api_tests.canvas_scenarios import authoring_case as authoring_case
from mendel_api_tests.database import truncate
from support.paths import ROOT as REPOSITORY_ROOT


@pytest.fixture
def clean_invocations():
    """Start each requested scenario with empty invocation-related tables.

    PostgreSQL requires these tables in one TRUNCATE because their foreign keys use RESTRICT.
    Pipeline-authoring turns reference the shared `ai_invocation` table; authoring proposals
    reference those turns. Any new table referencing these rows must join the truncation list.
    """
    from mendel_api.db import session_scope

    tables = (
        "ai_invocation, pipeline_authoring_proposal, pipeline_authoring_turn"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


@pytest.fixture
def broken_registry_copy(tmp_path):
    """A copy of the repository's registry that a test can break one field at a time.

    The copy is made once and mutated in place, so two calls break two fields of one registry.
    """
    import shutil
    from pathlib import Path

    root = REPOSITORY_ROOT

    def _break(relative: str, was: str, now: str) -> Path:
        copy = tmp_path / "registry"
        if not copy.exists():
            shutil.copytree(root / "registry", copy, ignore=shutil.ignore_patterns(".git"))
        contract = copy / relative
        text = contract.read_text()
        assert was in text, f"{relative} does not contain {was!r} — the fixture is stale"
        contract.write_text(text.replace(was, now))
        return copy

    return _break


@pytest.fixture
def clean_settings():
    """An empty `installation_setting` around each test. Nothing references it, so it truncates
    alone."""
    from mendel_api.db import session_scope

    with session_scope() as session:
        session.execute(truncate("TRUNCATE TABLE installation_setting"))
    yield


class _MemoryStore:
    def __init__(self):
        self.rows = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value


@pytest.fixture(autouse=True)
def settings_in_memory(request, monkeypatch):
    """Isolate installation settings in memory unless the test uses `real_settings`.

    Model access consults this store. Starting empty lets environment-configured model tests
    run without database access or settings left by another case. Yield the store so a test
    can explicitly configure an installation value.
    """
    if request.node.get_closest_marker("real_settings"):
        yield None
        return
    from mendel_api.services import installation

    store = _MemoryStore()
    monkeypatch.setattr(installation, "_store", lambda: store)
    yield store
