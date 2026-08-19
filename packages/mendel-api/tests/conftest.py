"""Fixtures for the API tests."""

import pytest


@pytest.fixture
def clean_db():
    """A truncated `queue_visit` around each test.

    These tests need the real database because they are about a stored baseline; mocking the
    session would test the mock. Truncating rather than recreating keeps them fast, and
    leaving rows behind makes them order-dependent.
    """
    from mendel_api.db import session_scope
    from sqlalchemy import text

    with session_scope() as session:
        session.execute(text("TRUNCATE TABLE queue_visit"))
    yield


@pytest.fixture
def broken_registry_copy(tmp_path):
    """The API-side twin of the forge's `broken_registry`.

    Duplicated rather than imported across packages: a test fixture reaching into another
    package's `tests/` directory is an import path that works only because both happen to be
    on `sys.path` in this workspace. Six lines is cheaper than that coupling.

    The copy is made once and mutated in place, so two calls break two fields of one registry.
    """
    import shutil
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]

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
