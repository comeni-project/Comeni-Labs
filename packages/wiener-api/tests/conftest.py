"""SQLite-backed fixtures, so CI needs no Postgres.

The same reason `mendel-api`'s services carry `_run` and `_directory` seams: a test that needs
a container is a test that does not run on a pull request, and a guard that does not run is
A14's concern wearing infrastructure.

**What this trades away, stated rather than implied.** SQLite is not Postgres: it does not
enforce the same types, `JSON` is a text column, and a migration that works here can fail
there. The migration is applied against real Postgres by hand (`make wiener-migrate`) and by
the compose stack; these tests are about behaviour, not about DDL.
"""


import pytest
import wiener_rows
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from wiener_api.db import Base
from wiener_api.models import Run
from wiener_api.settings import settings


@pytest.fixture(autouse=True)
def tail(monkeypatch):
    """Every test gets a real-behaving, in-process Redis.

    **Autouse, because the alternative is a test that quietly needs a container.** `record()`
    publishes and the events page reads the tail's last id, so without this the suite reaches
    `localhost:6379` — passing on a developer's machine, and in CI passing for the wrong
    reason, since a failed publish is deliberately only logged.
    """
    from fakeredis import FakeRedis
    from wiener_api.services import stream

    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(stream, "_client", fake)
    return fake


@pytest.fixture
def session(monkeypatch):
    # `StaticPool` and one connection: a bare `sqlite://` gives every connection its own empty
    # in-memory database, so `create_all` lands in one and the session opens another — which
    # fails as `no such table: run`, several layers away from the cause.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # SQLite ignores foreign keys unless asked, per connection; Postgres never does (issue 274).
    event.listen(
        engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON")
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

    # One patch, because both callers reach it as `db.session_scope()` rather than binding
    # the symbol at import — CLAUDE.md's own gotcha: `from x import f` binds past a later
    # patch of `x.f`, and the first version of this fixture patched two modules to work
    # around exactly that.
    monkeypatch.setattr(db, "session_scope", scope)
    yield session
    session.close()


@pytest.fixture
def a_run(session) -> Run:
    return wiener_rows.a_run(session)


@pytest.fixture
def ingest_client(session) -> TestClient:
    from wiener_api.main import create_ingest_app

    return TestClient(create_ingest_app())


@pytest.fixture
def client(session, tmp_path, monkeypatch) -> TestClient:
    """The public app, with the queue and the artifact store stood in for.

    `jobs.enqueue` is patched rather than Redis, for the reason `mendel_api.jobs` records: a
    route that reached Redis directly would make every route test need one.
    """
    from wiener_api import jobs
    from wiener_api.main import create_app

    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "work_root", tmp_path / "work")

    async def _enqueue(name, *args):
        queued.append((name, args))

    queued: list[tuple[str, tuple]] = []
    monkeypatch.setattr(jobs, "enqueue", _enqueue)
    test_client = TestClient(create_app())
    test_client.queued = queued          # type: ignore[attr-defined]
    return test_client


@pytest.fixture
def a_bundle() -> bytes:
    """A minimal pipeline directory, zipped in memory.

    **Its `pipeline.yml` is a stub and not a `Pipeline`** — `schema_version: 5` parses as YAML
    and fails `Pipeline.model_validate`. That is fine for everything that only needs an upload
    with a stable tree digest, and it is exactly wrong for anything reading the artifact's own
    document. Use `a_real_bundle` for that, and do not "fix" this one: two tests compare digests
    against a literal copy of these bytes.
    """
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.nf", "workflow {}\n")
        archive.writestr("pipeline.yml", "schema_version: 5\n")
        # The holes this artifact declares — what a submission must fill, exactly.
        archive.writestr("nextflow.config", "params {\n    input = null\n    fasta = null\n}\n")
    return buffer.getvalue()


@pytest.fixture
def a_real_bundle() -> bytes:
    """A bundle whose `pipeline.yml` is an actual `Pipeline`, so it has a content digest.

    Needed once `RunArtifact.pipeline_digest` started being written (2026-08-30): the key is
    `Pipeline.content_digest()` over the artifact's own document, so an artifact whose document
    does not parse honestly has none.
    """
    import io
    import zipfile

    import yaml
    from comeni_core.artifact.pipeline import Pipeline
    from comeni_core.goal.asked import Goal

    empty = Pipeline(intent=Goal().intent, facts=Goal().facts)
    document = yaml.safe_dump(empty.model_dump(mode="json"), sort_keys=False)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.nf", "workflow {}\n")
        archive.writestr("pipeline.yml", document)
        archive.writestr("nextflow.config", "params {\n    input = null\n    fasta = null\n}\n")
    return buffer.getvalue()
