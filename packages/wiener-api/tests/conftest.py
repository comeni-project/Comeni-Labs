"""SQLite-backed fixtures, so CI needs no Postgres.

The same reason `mendel-api`'s services carry `_run` and `_directory` seams: a test that needs
a container is a test that does not run on a pull request, and a guard that does not run is
A14's concern wearing infrastructure.

**What this trades away, stated rather than implied.** SQLite is not Postgres: it does not
enforce the same types, `JSON` is a text column, and a migration that works here can fail
there. The migration is applied against real Postgres by hand (`make wiener-migrate`) and by
the compose stack; these tests are about behaviour, not about DDL.
"""

import secrets
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from wiener_api.db import Base
from wiener_api.models import Run
from wiener_api.settings import settings


@pytest.fixture
def session(monkeypatch):
    # `StaticPool` and one connection: a bare `sqlite://` gives every connection its own empty
    # in-memory database, so `create_all` lands in one and the session opens another — which
    # fails as `no such table: run`, several layers away from the cause.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()

    # `session_scope` is what the routes open, so point it at this same in-memory database.
    import contextlib

    import wiener_api.db as db

    @contextlib.contextmanager
    def scope():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    monkeypatch.setattr(db, "session_scope", scope)
    import wiener_api.routes.ingest as ingest_module

    monkeypatch.setattr(ingest_module, "session_scope", scope)
    yield session
    session.close()


@pytest.fixture
def a_run(session) -> Run:
    row = Run(
        id=secrets.token_hex(16),
        lab_id=settings.lab_id,
        artifact_id=secrets.token_hex(16),
        submitted_by="test",
        submitted_at=datetime.now(UTC),
        phase="queued",
        executor="local",
        ingest_secret=secrets.token_hex(16),
    )
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def ingest_client(session) -> TestClient:
    from wiener_api.main import create_ingest_app

    return TestClient(create_ingest_app())
