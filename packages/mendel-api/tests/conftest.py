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
