# Mendel — API and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Put Mendel behind an OpenAPI service with background workers and a React dashboard that renders the IR — including the red/yellow review triage that is the product's whole point.

**Architecture:** `mendel-api` is a thin FastAPI skin over the existing packages: it accepts a prompt or goal, dispatches an ARQ job, streams progress over SSE, and persists runs and decisions to Postgres. The frontend is a Vite/React SPA consuming a TypeScript client generated from `openapi.json`, so the IR types can never drift between backend and frontend. The dashboard renders the IR directly — every node and parameter already carries its tier and review level, so there is no separate explanation layer to build.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, ARQ, Redis, Postgres, React 19, TypeScript, Vite, Tailwind 4, TanStack Query, vitest, Docker Compose.

## Global Constraints

- **Plans 1 and 2 must be complete and green before starting.** This plan adds no pipeline logic.
- The purity guard must still pass. `mendel-api` may import the pure packages; never the reverse.
- **No business logic in route handlers.** Routes validate, dispatch, and serialise. Anything else belongs in the packages below.
- API schemas reuse `comeni-core` Pydantic models directly. No parallel serialiser definitions — that is the reason FastAPI was chosen over Django in the spec.
- The TypeScript client is **generated** from `openapi.json` and committed. Never hand-edit `frontend/src/api/`.
- Long work runs in ARQ, never in a request. Any endpoint that could exceed one second returns a job id.
- **This plan implements structure and behaviour, not visual design.** Components use plain semantic markup and minimal utility classes. The `frontend-design` skill runs after this plan lands.
- Review levels drive the UI contract: `required` blocks running, `advisory` is acknowledgeable, `none` collapses by default.
- **The dashboard never accepts a sample sheet, a filename or a path.** Invariant 15 says Mendel
  receives a shape, not data, and this plan is where that is most likely to be lost — "let the
  user upload their samplesheet" is a natural feature request and it would end the guarantee. If
  a task appears to need one, the design is wrong: sample identity belongs to the laboratory's
  execution environment, reaching the pipeline through `params.input` at run time.
- Every screen that can cause a model call shows the active profile, and the `guarded`
  confirmation is a real gate, not a toast. It shows the exact payload and waits.
- Telemetry stays opt-in and off by default, and can only exist in `mendel-api` — invariant 1
  makes that structural rather than a promise.
- Ruff line length 100 for Python; `tsc --noEmit` and `eslint` clean for TypeScript. Both pass before every commit.

---

## File Structure

```
packages/mendel-api/
├─ pyproject.toml
├─ alembic.ini
├─ migrations/
└─ src/mendel_api/
   ├─ __init__.py
   ├─ settings.py            env-driven config
   ├─ db.py                  engine, session, Base
   ├─ models.py              Run, Decision, ProposalRow
   ├─ schemas.py             request/response models reusing comeni-core
   ├─ worker.py              ARQ task definitions
   ├─ events.py              in-process pub/sub for SSE
   ├─ routes/
   │  ├─ builds.py           POST /builds, GET /builds/{id}
   │  ├─ events.py           GET /builds/{id}/events  (SSE)
   │  ├─ reviews.py          GET/POST review + override
   │  └─ proposals.py        forge queue over HTTP
   └─ main.py                app factory

frontend/
├─ package.json
├─ vite.config.ts
├─ tailwind.config.js
└─ src/
   ├─ api/                   GENERATED — do not edit
   ├─ lib/tiers.ts           tier -> review level -> presentation mapping
   ├─ components/
   │  ├─ PipelineGraph.tsx   DAG layout
   │  ├─ NodeInspector.tsx   parameters with tier + reason
   │  └─ ReviewQueue.tsx     red/yellow triage
   └─ routes/BuildPage.tsx

docker-compose.dev.yml, docker-compose.prod.yml, nginx/, Makefile
```

---

### Task 1: API scaffold and settings

**Files:**
- Create: `packages/mendel-api/pyproject.toml`, `src/mendel_api/__init__.py`, `settings.py`, `main.py`
- Test: `packages/mendel-api/tests/test_app.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Settings` (env-driven); `create_app() -> FastAPI`; `GET /health`; `GET /openapi.json`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from mendel_api.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_served():
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Mendel"


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("MENDEL_DATABASE_URL", "postgresql+psycopg://x/y")
    from mendel_api.settings import Settings

    assert Settings().database_url == "postgresql+psycopg://x/y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-api/tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_api'`

- [ ] **Step 3: Create the package**

`packages/mendel-api/pyproject.toml`:

```toml
[project]
name = "mendel-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "comeni-core", "mendel-resolver", "mendel-compiler", "mendel-ai", "mendel-forge",
  "fastapi>=0.115", "uvicorn[standard]>=0.32", "pydantic-settings>=2.5",
  "sqlalchemy>=2.0", "alembic>=1.13", "psycopg[binary]>=3.2", "arq>=0.26",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mendel_api"]
```

`src/mendel_api/settings.py`:

```python
"""Environment-driven configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MENDEL_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://mendel:mendel@localhost:5432/mendel"
    redis_url: str = "redis://localhost:6379"
    project_root: Path = Path.cwd()
    model: str = "claude-opus-5"
    use_ai: bool = True
```

`src/mendel_api/main.py`:

```python
"""FastAPI app factory. Routes validate, dispatch and serialise — nothing else."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Mendel", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

`src/mendel_api/__init__.py`:

```python
"""HTTP surface for Mendel."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv sync && uv run pytest packages/mendel-api/tests/test_app.py -v && uv run ruff check .`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-api/
git commit -m "feat(api): FastAPI scaffold with settings and health endpoint"
```

---

### Task 2: Persistence

**Files:**
- Create: `packages/mendel-api/src/mendel_api/db.py`, `models.py`, `alembic.ini`, `migrations/`
- Test: `packages/mendel-api/tests/test_models.py`

**Interfaces:**
- Consumes: `Settings` (Task 1)
- Produces: `Base`; `Run(id, status, prompt, goal_json, ir_json, source_nf, flagged_count, created_at)`; `Decision(id, run_id, key, subject, chosen, reason, confidence, resolved_by, human_override)`; `session_scope()` context manager; `RunStatus` StrEnum

- [ ] **Step 1: Write the failing test**

```python
import pytest
from mendel_api.models import Base, Decision, Run, RunStatus
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_run_defaults_to_queued(session):
    run = Run(prompt="rna-seq please")
    session.add(run)
    session.commit()
    assert run.status is RunStatus.QUEUED
    assert run.created_at is not None


def test_decisions_relate_to_their_run(session):
    run = Run(prompt="p")
    run.decisions.append(
        Decision(key="star.aligner", subject="aligner", chosen="star",
                 reason="150bp reads", confidence=0.9, resolved_by="claude-opus-5")
    )
    session.add(run)
    session.commit()
    found = session.scalar(select(Run).where(Run.id == run.id))
    assert len(found.decisions) == 1
    assert found.decisions[0].chosen == "star"


def test_human_override_defaults_to_null(session):
    run = Run(prompt="p")
    run.decisions.append(Decision(key="k", subject="s", chosen="a", reason="r",
                                  confidence=0.0, resolved_by="flag-only"))
    session.add(run)
    session.commit()
    assert run.decisions[0].human_override is None


def test_flagged_count_is_stored_for_listing_without_parsing_the_ir(session):
    run = Run(prompt="p", flagged_count=3)
    session.add(run)
    session.commit()
    assert run.flagged_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-api/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_api.models'`

- [ ] **Step 3: Write `models.py`**

```python
"""Persistence. The IR is stored as JSON — comeni-core owns its shape, not the ORM."""

import datetime as dt
import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


JSONType = JSON().with_variant(JSONB(), "postgresql")


class RunStatus(StrEnum):
    QUEUED = "queued"
    RESOLVING = "resolving"
    COMPILING = "compiling"
    REPAIRING = "repairing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _uuid() -> str:
    return str(uuid.uuid4())


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[RunStatus] = mapped_column(String(16), default=RunStatus.QUEUED)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    ir_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    source_nf: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC)
    )

    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    chosen: Mapped[Any] = mapped_column(JSONType)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    resolved_by: Mapped[str] = mapped_column(String(64))
    human_override: Mapped[Any | None] = mapped_column(JSONType, nullable=True)

    run: Mapped[Run] = relationship(back_populates="decisions")
```

- [ ] **Step 4: Write `db.py`**

```python
"""Engine and session management."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mendel_api.settings import Settings

_settings = Settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session
```

- [ ] **Step 5: Initialise Alembic and generate the first migration**

```bash
cd packages/mendel-api
uv run alembic init migrations
```

In `migrations/env.py`, replace the metadata line with:

```python
from mendel_api.models import Base
from mendel_api.settings import Settings

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", Settings().database_url)
```

Then generate and inspect it — read the generated SQL before committing, do not trust autogenerate blindly:

```bash
uv run alembic revision --autogenerate -m "runs and decisions"
cat migrations/versions/*.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-api/tests/test_models.py -v && uv run ruff check .`
Expected: PASS, 4 tests.

- [ ] **Step 7: Commit**

```bash
git add packages/mendel-api/
git commit -m "feat(api): Run and Decision models with Alembic migrations"
```

---

### Task 3: The build worker

**Files:**
- Create: `packages/mendel-api/src/mendel_api/events.py`, `worker.py`
- Test: `packages/mendel-api/tests/test_worker.py`

**Interfaces:**
- Consumes: `resolve` (Plan 1 Task 9), `compile_with_repair` (Plan 2 Task 6), `LLMGoalExtractor` (Plan 2 Task 3), `Run`/`Decision` (Task 2)
- Produces: `EventBus.publish(run_id, event)` / `.subscribe(run_id)`; `build_pipeline(ctx, run_id) -> None`; `BuildEvent(stage, message, progress)`

- [ ] **Step 1: Write the failing test**

```python
import asyncio

import pytest
from mendel_api.events import BuildEvent, EventBus


@pytest.mark.asyncio
async def test_subscriber_receives_published_events():
    bus = EventBus()
    received = []

    async def listen():
        async for event in bus.subscribe("run-1"):
            received.append(event)
            if event.stage == "done":
                break

    task = asyncio.create_task(listen())
    await asyncio.sleep(0)
    await bus.publish("run-1", BuildEvent(stage="resolving", message="routing"))
    await bus.publish("run-1", BuildEvent(stage="done", message="finished"))
    await asyncio.wait_for(task, timeout=2)

    assert [e.stage for e in received] == ["resolving", "done"]


@pytest.mark.asyncio
async def test_events_are_isolated_per_run():
    bus = EventBus()
    received = []

    async def listen():
        async for event in bus.subscribe("run-1"):
            received.append(event)
            break

    task = asyncio.create_task(listen())
    await asyncio.sleep(0)
    await bus.publish("run-2", BuildEvent(stage="other", message="wrong run"))
    await bus.publish("run-1", BuildEvent(stage="mine", message="right run"))
    await asyncio.wait_for(task, timeout=2)

    assert [e.stage for e in received] == ["mine"]


@pytest.mark.asyncio
async def test_publishing_with_no_subscriber_does_not_raise():
    await EventBus().publish("nobody", BuildEvent(stage="x", message="y"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-api/tests/test_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_api.events'`

- [ ] **Step 3: Add `pytest-asyncio` and write `events.py`**

Add `pytest-asyncio>=0.24` to the root `[dependency-groups] dev` list, and to root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "packages"]
asyncio_mode = "auto"
```

```python
"""In-process pub/sub for streaming build progress to SSE subscribers."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from pydantic import BaseModel


class BuildEvent(BaseModel):
    stage: str
    message: str
    progress: float | None = None


class EventBus:
    """One queue per subscriber. Publishing to nobody is a no-op, not an error."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[BuildEvent]]] = defaultdict(list)

    async def publish(self, run_id: str, event: BuildEvent) -> None:
        for queue in list(self._subscribers.get(run_id, [])):
            await queue.put(event)

    async def subscribe(self, run_id: str) -> AsyncIterator[BuildEvent]:
        queue: asyncio.Queue[BuildEvent] = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[run_id].remove(queue)
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]


bus = EventBus()
```

- [ ] **Step 4: Write `worker.py`**

```python
"""ARQ task: resolve, compile, repair, persist. All the slow work lives here."""

import tempfile
from pathlib import Path
from typing import Any

from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_ai.ambiguity import LLMAmbiguityResolver
from mendel_ai.client import ModelClient, ModelConfig
from mendel_ai.extract import LLMGoalExtractor
from mendel_ai.repair import LLMRepairProposer
from mendel_ai.store import DecisionStore, ReplayingResolver
from mendel_api.db import session_scope
from mendel_api.events import BuildEvent, bus
from mendel_api.models import Decision, Run, RunStatus
from mendel_api.settings import Settings
from mendel_compiler.gates import Gate
from mendel_compiler.loop import compile_with_repair
from mendel_resolver.goal import Goal
from mendel_resolver.ports import FlagOnlyResolver
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable


async def _set_status(run_id: str, status: RunStatus, message: str) -> None:
    with session_scope() as session:
        run = session.get(Run, run_id)
        run.status = status
    await bus.publish(run_id, BuildEvent(stage=status.value, message=message))


async def build_pipeline(ctx: dict[str, Any], run_id: str) -> None:
    settings = Settings()
    root = settings.project_root
    vocab = Vocabulary.load(root / "vocabularies")
    registry = Registry.load(root / "contracts", vocab)
    rules = RuleTable.load(root / "rules" / "rnaseq.yml")

    with session_scope() as session:
        run = session.get(Run, run_id)
        prompt, goal_json = run.prompt, run.goal_json

    try:
        await _set_status(run_id, RunStatus.RESOLVING, "resolving modules and parameters")

        client = ModelClient(ModelConfig(model=settings.model)) if settings.use_ai else None
        workdir = Path(tempfile.mkdtemp(prefix=f"mendel-{run_id}-"))
        store = DecisionStore(workdir / "decisions.jsonl")
        inner = LLMAmbiguityResolver(client) if client else FlagOnlyResolver()
        resolver = ReplayingResolver(inner, store)

        if goal_json is not None:
            goal = Goal.model_validate(goal_json)
        else:
            goal = LLMGoalExtractor(client, vocab).extract(prompt)

        ir = resolve(goal, registry, rules, resolver=resolver)

        await _set_status(run_id, RunStatus.COMPILING, "generating Nextflow")
        proposer = LLMRepairProposer(client, registry) if client else None
        outcome = compile_with_repair(ir, registry, workdir, proposer=proposer, gate=Gate.STUB)

        with session_scope() as session:
            run = session.get(Run, run_id)
            run.goal_json = goal.model_dump(mode="json")
            run.ir_json = outcome.ir.model_dump(mode="json")
            run.source_nf = outcome.source
            run.flagged_count = len(outcome.ir.needs_review())
            run.status = RunStatus.SUCCEEDED if outcome.passed else RunStatus.FAILED
            for record in outcome.ir.decisions:
                run.decisions.append(
                    Decision(
                        key=record.key, subject=record.subject, chosen=record.chosen,
                        reason=record.reason, confidence=record.confidence,
                        resolved_by=record.resolved_by,
                    )
                )

        await bus.publish(
            run_id,
            BuildEvent(
                stage="done",
                message=f"{len(outcome.ir.nodes)} modules, {len(outcome.ir.needs_review())} need review",
                progress=1.0,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — the run must record why it died
        with session_scope() as session:
            run = session.get(Run, run_id)
            run.status = RunStatus.FAILED
            run.error = str(exc)
        await bus.publish(run_id, BuildEvent(stage="failed", message=str(exc)))


class WorkerSettings:
    functions = [build_pipeline]

    @staticmethod
    def redis_settings():
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(Settings().redis_url)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-api/tests/test_worker.py -v && uv run ruff check .`
Expected: PASS, 3 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-api/ pyproject.toml
git commit -m "feat(api): ARQ build worker with SSE event bus"
```

---

### Task 4: Build endpoints and SSE

**Files:**
- Create: `packages/mendel-api/src/mendel_api/schemas.py`, `routes/builds.py`, `routes/events.py`
- Modify: `packages/mendel-api/src/mendel_api/main.py`
- Test: `packages/mendel-api/tests/test_builds.py`

**Interfaces:**
- Consumes: `Run` (Task 2), `bus` (Task 3)
- Produces: `POST /builds` accepting `{prompt}` or `{goal}` → `202 {run_id, status}`; `GET /builds/{id}` → `BuildResponse`; `GET /builds` → list; `GET /builds/{id}/events` → SSE stream

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi.testclient import TestClient
from mendel_api.db import get_session
from mendel_api.main import create_app
from mendel_api.models import Base, Run
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(engine, expire_on_commit=False)

    dispatched = []

    async def fake_enqueue(name, run_id):
        dispatched.append((name, run_id))

    app = create_app()

    def override():
        with TestSession() as session:
            yield session
            session.commit()

    app.dependency_overrides[get_session] = override
    monkeypatch.setattr("mendel_api.routes.builds.enqueue_build", fake_enqueue)
    test_client = TestClient(app)
    test_client.dispatched = dispatched
    return test_client


def test_post_build_with_a_prompt_returns_202_and_a_run_id(client):
    response = client.post("/builds", json={"prompt": "rna-seq, counts matrix"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["run_id"]


def test_post_build_dispatches_a_job(client):
    run_id = client.post("/builds", json={"prompt": "x"}).json()["run_id"]
    assert client.dispatched == [("build_pipeline", run_id)]


def test_post_build_requires_prompt_or_goal(client):
    assert client.post("/builds", json={}).status_code == 422


def test_get_build_returns_flagged_count_and_status(client):
    run_id = client.post("/builds", json={"prompt": "x"}).json()["run_id"]
    body = client.get(f"/builds/{run_id}").json()
    assert body["status"] == "queued"
    assert body["flagged_count"] == 0


def test_get_unknown_build_returns_404(client):
    assert client.get("/builds/does-not-exist").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-api/tests/test_builds.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_api.routes'`

- [ ] **Step 3: Write `schemas.py`**

```python
"""Request and response models. Reuses comeni-core types rather than redefining them."""

from typing import Any

from pydantic import BaseModel, model_validator

from comeni_core.ir import PipelineIR
from mendel_resolver.goal import Goal


class BuildRequest(BaseModel):
    prompt: str | None = None
    goal: Goal | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "BuildRequest":
        if (self.prompt is None) == (self.goal is None):
            raise ValueError("provide exactly one of 'prompt' or 'goal'")
        return self


class BuildAccepted(BaseModel):
    run_id: str
    status: str


class DecisionResponse(BaseModel):
    key: str
    subject: str
    chosen: Any
    reason: str
    confidence: float
    resolved_by: str
    human_override: Any = None


class BuildResponse(BaseModel):
    run_id: str
    status: str
    prompt: str | None
    ir: PipelineIR | None
    source_nf: str | None
    flagged_count: int
    error: str | None
    decisions: list[DecisionResponse]
```

- [ ] **Step 4: Write `routes/builds.py`**

```python
"""Build endpoints. Validate, dispatch, serialise."""

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from mendel_api.db import get_session
from mendel_api.models import Run
from mendel_api.schemas import BuildAccepted, BuildRequest, BuildResponse, DecisionResponse
from mendel_api.settings import Settings

router = APIRouter(prefix="/builds", tags=["builds"])


async def enqueue_build(name: str, run_id: str) -> None:
    pool = await create_pool(RedisSettings.from_dsn(Settings().redis_url))
    await pool.enqueue_job(name, run_id)


def _to_response(run: Run) -> BuildResponse:
    return BuildResponse(
        run_id=run.id,
        status=run.status,
        prompt=run.prompt,
        ir=run.ir_json,
        source_nf=run.source_nf,
        flagged_count=run.flagged_count,
        error=run.error,
        decisions=[
            DecisionResponse(
                key=d.key, subject=d.subject, chosen=d.chosen, reason=d.reason,
                confidence=d.confidence, resolved_by=d.resolved_by,
                human_override=d.human_override,
            )
            for d in run.decisions
        ],
    )


@router.post("", status_code=202, response_model=BuildAccepted)
async def create_build(
    request: BuildRequest, session: Session = Depends(get_session)
) -> BuildAccepted:
    run = Run(
        prompt=request.prompt,
        goal_json=request.goal.model_dump(mode="json") if request.goal else None,
    )
    session.add(run)
    session.flush()
    await enqueue_build("build_pipeline", run.id)
    return BuildAccepted(run_id=run.id, status=run.status)


@router.get("", response_model=list[BuildResponse])
def list_builds(session: Session = Depends(get_session)) -> list[BuildResponse]:
    runs = session.scalars(select(Run).order_by(Run.created_at.desc()).limit(50)).all()
    return [_to_response(run) for run in runs]


@router.get("/{run_id}", response_model=BuildResponse)
def get_build(run_id: str, session: Session = Depends(get_session)) -> BuildResponse:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _to_response(run)
```

- [ ] **Step 5: Write `routes/events.py`**

```python
"""Server-sent events: build progress and streamed model reasoning."""

from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from mendel_api.events import bus

router = APIRouter(prefix="/builds", tags=["events"])


@router.get("/{run_id}/events")
async def stream_events(run_id: str) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        async for event in bus.subscribe(run_id):
            yield f"data: {event.model_dump_json()}\n\n"
            if event.stage in ("done", "failed"):
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 6: Register the routers in `main.py`**

```python
    from mendel_api.routes import builds, events

    app.include_router(builds.router)
    app.include_router(events.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-api/tests/ -v && uv run ruff check .`
Expected: PASS, 5 new tests.

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-api/
git commit -m "feat(api): build endpoints with SSE progress streaming"
```

---

### Task 5: Review and override endpoints

**Files:**
- Create: `packages/mendel-api/src/mendel_api/routes/reviews.py`
- Test: `packages/mendel-api/tests/test_reviews.py`

**Interfaces:**
- Consumes: `Run`/`Decision` (Task 2), `ReviewLevel`/`Tier` (Plan 1 Task 4)
- Produces: `GET /builds/{id}/review` → `ReviewSummary(required, advisory)`; `POST /builds/{id}/review/{key}/override` → re-dispatches the build with the override recorded

The override endpoint is what makes the dashboard more than a viewer: a human correction becomes a stored decision that all future runs replay.

- [ ] **Step 1: Write the failing test**

```python
def test_review_groups_items_by_level(client, seeded_run):
    body = client.get(f"/builds/{seeded_run}/review").json()
    assert [item["key"] for item in body["required"]] == ["star_align.seq_platform"]
    assert [item["key"] for item in body["advisory"]] == ["featurecounts.strandedness"]


def test_review_item_carries_reason_and_tier(client, seeded_run):
    item = client.get(f"/builds/{seeded_run}/review").json()["required"][0]
    assert item["tier"] == 4
    assert item["reason"] != ""


def test_override_records_the_human_choice(client, seeded_run):
    response = client.post(
        f"/builds/{seeded_run}/review/star_align.seq_platform/override",
        json={"value": "nanopore", "by": "rafael"},
    )
    assert response.status_code == 202
    body = client.get(f"/builds/{seeded_run}").json()
    decision = next(d for d in body["decisions"] if d["key"] == "star_align.seq_platform")
    assert decision["human_override"] == "nanopore"


def test_override_of_unknown_key_returns_404(client, seeded_run):
    response = client.post(
        f"/builds/{seeded_run}/review/nope.nothing/override",
        json={"value": "x", "by": "rafael"},
    )
    assert response.status_code == 404
```

Add to the test module a `seeded_run` fixture that creates a `Run` with `ir_json` containing one tier-3 and one tier-4 parameter, plus matching `Decision` rows:

```python
import pytest
from mendel_api.models import Decision, Run

IR = {
    "nodes": [
        {"id": "featurecounts", "contract_id": "c1", "params": {
            "strandedness": {"value": 2, "tier": 3, "reason": "rule strandedness-reverse",
                             "review_level": "advisory"}}},
        {"id": "star_align", "contract_id": "c2", "params": {
            "seq_platform": {"value": "illumina", "tier": 4, "reason": "no rule covered it",
                             "review_level": "required"}}},
    ],
    "edges": [], "decisions": [], "diverged": False,
}


@pytest.fixture
def seeded_run(client):
    from mendel_api.db import get_session

    session = next(client.app.dependency_overrides[get_session]())
    run = Run(prompt="p", ir_json=IR, flagged_count=1)
    run.decisions.append(Decision(key="star_align.seq_platform", subject="seq_platform",
                                  chosen="illumina", reason="no rule", confidence=0.0,
                                  resolved_by="flag-only"))
    session.add(run)
    session.commit()
    return run.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/mendel-api/tests/test_reviews.py -v`
Expected: FAIL — `/review` returns 404, the route does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
"""Review triage and human overrides."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mendel_api.db import get_session
from mendel_api.models import Run
from mendel_api.routes import builds

router = APIRouter(prefix="/builds", tags=["review"])


class ReviewItem(BaseModel):
    key: str
    node_id: str
    param_name: str
    value: Any
    tier: int
    reason: str


class ReviewSummary(BaseModel):
    required: list[ReviewItem]
    advisory: list[ReviewItem]


class OverrideRequest(BaseModel):
    value: Any
    by: str


def _items(run: Run, level: str) -> list[ReviewItem]:
    ir = run.ir_json or {"nodes": []}
    return [
        ReviewItem(
            key=f"{node['id']}.{name}",
            node_id=node["id"],
            param_name=name,
            value=param["value"],
            tier=param["tier"],
            reason=param["reason"],
        )
        for node in ir["nodes"]
        for name, param in sorted(node.get("params", {}).items())
        if param.get("review_level") == level
    ]


@router.get("/{run_id}/review", response_model=ReviewSummary)
def get_review(run_id: str, session: Session = Depends(get_session)) -> ReviewSummary:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return ReviewSummary(required=_items(run, "required"), advisory=_items(run, "advisory"))


@router.post("/{run_id}/review/{key}/override", status_code=202)
async def override(
    run_id: str,
    key: str,
    request: OverrideRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    decision = next((d for d in run.decisions if d.key == key), None)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"no decision named {key}")

    decision.human_override = request.value
    session.flush()
    # Import the module, not the symbol: tests monkeypatch builds.enqueue_build,
    # and a `from ... import enqueue_build` here would bind past the patch.
    await builds.enqueue_build("build_pipeline", run.id)
    return {"status": "rebuilding", "key": key}
```

Register in `main.py`: `app.include_router(reviews.router)`.

The `client` fixture from Task 4 already monkeypatches `mendel_api.routes.builds.enqueue_build`; import it into this test module rather than redefining it, so the override endpoint dispatches through the same fake and no test touches Redis.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/mendel-api/tests/ -v && uv run ruff check .`
Expected: PASS, 4 new tests.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-api/
git commit -m "feat(api): review triage and human override endpoints"
```

---

### Task 6: Frontend scaffold and generated client

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`, `index.html`, `src/main.tsx`, `src/lib/tiers.ts`
- Create: `frontend/src/api/` (generated)
- Test: `frontend/src/lib/tiers.test.ts`

**Interfaces:**
- Consumes: `openapi.json` from the running API
- Produces: generated `BuildResponse`, `ReviewSummary` types; `presentationFor(reviewLevel)` returning `{ label, tone, collapsedByDefault, blocksRun }`

`tiers.ts` is the single place the review-level contract is encoded on the frontend. Components read from it; they never switch on tier numbers themselves.

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, expect, it } from "vitest";
import { presentationFor } from "./tiers";

describe("presentationFor", () => {
  it("marks required items as blocking", () => {
    expect(presentationFor("required").blocksRun).toBe(true);
  });

  it("does not block on advisory items", () => {
    expect(presentationFor("advisory").blocksRun).toBe(false);
  });

  it("collapses resolved items by default", () => {
    expect(presentationFor("none").collapsedByDefault).toBe(true);
  });

  it("keeps items needing attention expanded", () => {
    expect(presentationFor("advisory").collapsedByDefault).toBe(false);
    expect(presentationFor("required").collapsedByDefault).toBe(false);
  });

  it("gives every level a distinct tone", () => {
    const tones = (["none", "advisory", "required"] as const).map((l) => presentationFor(l).tone);
    expect(new Set(tones).size).toBe(3);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm install && npx vitest run src/lib/tiers.test.ts`
Expected: FAIL — `frontend/` does not exist yet.

- [ ] **Step 3: Scaffold the frontend**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install @tanstack/react-query react-router-dom
npm install -D tailwindcss @tailwindcss/vite vitest @testing-library/react @testing-library/jest-dom jsdom
```

`vite.config.ts`:

```typescript
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/builds": "http://localhost:8000", "/health": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true },
});
```

- [ ] **Step 4: Write `src/lib/tiers.ts`**

```typescript
/**
 * The review-level contract, encoded once.
 *
 * Tier 3 is advisory rather than silent on purpose: a rule match is only as good
 * as the measurement behind it, so the user should glance at it even though the
 * machinery worked. Components must read from here rather than switching on tiers.
 */
export type ReviewLevel = "none" | "advisory" | "required";

export interface Presentation {
  label: string;
  tone: "resolved" | "check" | "decide";
  collapsedByDefault: boolean;
  blocksRun: boolean;
}

const PRESENTATION: Record<ReviewLevel, Presentation> = {
  none: {
    label: "Resolved",
    tone: "resolved",
    collapsedByDefault: true,
    blocksRun: false,
  },
  advisory: {
    label: "Check the premise",
    tone: "check",
    collapsedByDefault: false,
    blocksRun: false,
  },
  required: {
    label: "Needs your decision",
    tone: "decide",
    collapsedByDefault: false,
    blocksRun: true,
  },
};

export function presentationFor(level: ReviewLevel): Presentation {
  return PRESENTATION[level];
}

export function tierDescription(tier: number): string {
  return (
    {
      1: "Forced by your inputs — no choice existed",
      2: "Standard practice for this kind of analysis",
      3: "Chosen from a rule matched against your data",
      4: "Mendel had to choose — please confirm",
    }[tier] ?? "Unknown"
  );
}
```

- [ ] **Step 5: Generate the API client**

With the API running (`uv run uvicorn mendel_api.main:create_app --factory`):

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts
```

Add to `package.json` scripts so it is reproducible:

```json
"generate:api": "openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts"
```

Create `src/api/client.ts`:

```typescript
import type { components } from "./schema";

export type BuildResponse = components["schemas"]["BuildResponse"];
export type ReviewSummary = components["schemas"]["ReviewSummary"];
export type ReviewItem = components["schemas"]["ReviewItem"];

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export const api = {
  createBuild: (body: { prompt?: string }) =>
    fetch("/builds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<{ run_id: string; status: string }>),

  getBuild: (id: string) => fetch(`/builds/${id}`).then(json<BuildResponse>),

  getReview: (id: string) => fetch(`/builds/${id}/review`).then(json<ReviewSummary>),

  override: (id: string, key: string, value: unknown, by: string) =>
    fetch(`/builds/${id}/review/${encodeURIComponent(key)}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, by }),
    }).then(json<{ status: string }>),
};
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS, 5 tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Vite scaffold, generated API client, review-level contract"
```

---

### Task 7: Pipeline graph and node inspector

**Files:**
- Create: `frontend/src/components/PipelineGraph.tsx`, `NodeInspector.tsx`
- Test: `frontend/src/components/PipelineGraph.test.tsx`, `NodeInspector.test.tsx`

**Interfaces:**
- Consumes: `BuildResponse`, `presentationFor`, `tierDescription` (Task 6)
- Produces: `<PipelineGraph ir={ir} onSelect={fn} selectedId={id} />`; `<NodeInspector node={node} onOverride={fn} />`

Structure and behaviour only — layout is a simple vertical chain. The `frontend-design` skill reshapes this later.

- [ ] **Step 1: Write the failing test**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PipelineGraph } from "./PipelineGraph";

const ir = {
  nodes: [
    { id: "trimgalore", contract_id: "nf-core/trimgalore@0.6.10", params: {} },
    {
      id: "featurecounts",
      contract_id: "nf-core/subread/featurecounts@2.0.6",
      params: {
        strandedness: { value: 2, tier: 3, reason: "rule", review_level: "advisory" },
        seq_platform: { value: "x", tier: 4, reason: "none", review_level: "required" },
      },
    },
  ],
  edges: [
    { from_node: "trimgalore", from_port: "reads", to_node: "featurecounts",
      to_port: "bam", type_id: "fastq.reads", states: ["trimmed"] },
  ],
  decisions: [],
  diverged: false,
};

describe("PipelineGraph", () => {
  it("renders one element per node", () => {
    render(<PipelineGraph ir={ir} onSelect={() => {}} />);
    expect(screen.getAllByRole("button", { name: /trimgalore|featurecounts/ })).toHaveLength(2);
  });

  it("shows the worst review level present on a node", () => {
    render(<PipelineGraph ir={ir} onSelect={() => {}} />);
    expect(screen.getByTestId("status-featurecounts")).toHaveTextContent("Needs your decision");
    expect(screen.getByTestId("status-trimgalore")).toHaveTextContent("Resolved");
  });

  it("calls onSelect with the node id when clicked", async () => {
    const onSelect = vi.fn();
    render(<PipelineGraph ir={ir} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: /featurecounts/ }));
    expect(onSelect).toHaveBeenCalledWith("featurecounts");
  });

  it("labels edges with their type and state", () => {
    render(<PipelineGraph ir={ir} onSelect={() => {}} />);
    expect(screen.getByText(/fastq.reads \[trimmed\]/)).toBeInTheDocument();
  });

  it("warns when the pipeline has diverged from its IR", () => {
    render(<PipelineGraph ir={{ ...ir, diverged: true }} onSelect={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/diverged/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/PipelineGraph.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `PipelineGraph.tsx`**

```tsx
import { presentationFor, type ReviewLevel } from "../lib/tiers";

interface ResolvedValue {
  value: unknown;
  tier: number;
  reason: string;
  review_level: ReviewLevel;
}

export interface IRNode {
  id: string;
  contract_id: string;
  params: Record<string, ResolvedValue>;
}

interface IREdge {
  from_node: string;
  from_port: string;
  to_node: string;
  to_port: string;
  type_id: string;
  states: string[];
}

export interface IR {
  nodes: IRNode[];
  edges: IREdge[];
  diverged: boolean;
}

const SEVERITY: Record<ReviewLevel, number> = { none: 0, advisory: 1, required: 2 };

export function worstLevel(node: IRNode): ReviewLevel {
  return Object.values(node.params).reduce<ReviewLevel>(
    (worst, param) => (SEVERITY[param.review_level] > SEVERITY[worst] ? param.review_level : worst),
    "none",
  );
}

export function PipelineGraph({
  ir,
  onSelect,
  selectedId,
}: {
  ir: IR;
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {ir.diverged && (
        <div role="alert" className="border p-2">
          This pipeline diverged from its plan — generated code was patched directly.
        </div>
      )}
      {ir.nodes.map((node, index) => {
        const level = worstLevel(node);
        const presentation = presentationFor(level);
        const incoming = ir.edges.find((edge) => edge.to_node === node.id);
        return (
          <div key={node.id} className="flex flex-col items-start gap-1">
            {incoming && (
              <span className="text-xs opacity-70">
                {incoming.type_id}
                {incoming.states.length > 0 && ` [${incoming.states.join(", ")}]`}
              </span>
            )}
            <button
              type="button"
              onClick={() => onSelect(node.id)}
              aria-current={selectedId === node.id}
              data-tone={presentation.tone}
              className="border p-2 text-left w-full"
            >
              <span className="font-medium">{node.id}</span>
              <span data-testid={`status-${node.id}`} className="block text-xs">
                {presentation.label}
              </span>
            </button>
            {index < ir.nodes.length - 1 && <span aria-hidden="true">↓</span>}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Write the failing test for `NodeInspector`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NodeInspector } from "./NodeInspector";

const node = {
  id: "featurecounts",
  contract_id: "nf-core/subread/featurecounts@2.0.6",
  params: {
    strandedness: { value: 2, tier: 3, reason: "rule strandedness-reverse", review_level: "advisory" as const },
    seq_platform: { value: "illumina", tier: 4, reason: "no rule covered it", review_level: "required" as const },
  },
};

describe("NodeInspector", () => {
  it("shows every parameter with its reason", () => {
    render(<NodeInspector node={node} onOverride={() => {}} />);
    expect(screen.getByText("rule strandedness-reverse")).toBeInTheDocument();
    expect(screen.getByText("no rule covered it")).toBeInTheDocument();
  });

  it("explains what the tier means in plain language", () => {
    render(<NodeInspector node={node} onOverride={() => {}} />);
    expect(screen.getByText(/Mendel had to choose/)).toBeInTheDocument();
  });

  it("submits an override with the parameter key", async () => {
    const onOverride = vi.fn();
    render(<NodeInspector node={node} onOverride={onOverride} />);
    const input = screen.getByLabelText("Override seq_platform");
    await userEvent.clear(input);
    await userEvent.type(input, "nanopore");
    await userEvent.click(screen.getByRole("button", { name: /save seq_platform/i }));
    expect(onOverride).toHaveBeenCalledWith("featurecounts.seq_platform", "nanopore");
  });
});
```

- [ ] **Step 5: Write `NodeInspector.tsx`**

```tsx
import { useState } from "react";
import { presentationFor, tierDescription } from "../lib/tiers";
import type { IRNode } from "./PipelineGraph";

export function NodeInspector({
  node,
  onOverride,
}: {
  node: IRNode;
  onOverride: (key: string, value: string) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  return (
    <section>
      <h2 className="font-medium">{node.id}</h2>
      <p className="text-xs opacity-70">{node.contract_id}</p>
      <dl className="flex flex-col gap-3 mt-3">
        {Object.entries(node.params).map(([name, param]) => {
          const presentation = presentationFor(param.review_level);
          const key = `${node.id}.${name}`;
          const draft = drafts[name] ?? String(param.value);
          return (
            <div key={name} data-tone={presentation.tone} className="border p-2">
              <dt className="font-medium">{name}</dt>
              <dd>
                <p className="text-sm">{tierDescription(param.tier)}</p>
                <p className="text-xs opacity-70">{param.reason}</p>
                <label className="block mt-2 text-xs" htmlFor={`override-${name}`}>
                  Override {name}
                </label>
                <input
                  id={`override-${name}`}
                  className="border p-1"
                  value={draft}
                  onChange={(event) =>
                    setDrafts({ ...drafts, [name]: event.target.value })
                  }
                />
                <button
                  type="button"
                  className="border p-1 ml-1"
                  onClick={() => onOverride(key, draft)}
                >
                  Save {name}
                </button>
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS, 8 tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/
git commit -m "feat(frontend): pipeline graph and node inspector with tier explanations"
```

---

### Task 8: Review queue and build page

**Files:**
- Create: `frontend/src/components/ReviewQueue.tsx`, `frontend/src/routes/BuildPage.tsx`
- Modify: `frontend/src/main.tsx`
- Test: `frontend/src/components/ReviewQueue.test.tsx`

**Interfaces:**
- Consumes: `api` (Task 6), `PipelineGraph`/`NodeInspector` (Task 7)
- Produces: `<ReviewQueue summary={summary} onOverride={fn} onAcknowledge={fn} />`; `<BuildPage />` route at `/builds/:id`

- [ ] **Step 1: Write the failing test**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReviewQueue } from "./ReviewQueue";

const summary = {
  required: [{ key: "star_align.seq_platform", node_id: "star_align", param_name: "seq_platform",
               value: "illumina", tier: 4, reason: "no rule covered it" }],
  advisory: [{ key: "featurecounts.strandedness", node_id: "featurecounts", param_name: "strandedness",
               value: 2, tier: 3, reason: "rule strandedness-reverse" }],
};

describe("ReviewQueue", () => {
  it("lists required items before advisory ones", () => {
    render(<ReviewQueue summary={summary} onOverride={() => {}} onAcknowledge={() => {}} />);
    const headings = screen.getAllByRole("heading").map((h) => h.textContent);
    expect(headings[0]).toMatch(/decision/i);
    expect(headings[1]).toMatch(/check/i);
  });

  it("blocks running while required items remain", () => {
    render(<ReviewQueue summary={summary} onOverride={() => {}} onAcknowledge={() => {}} />);
    expect(screen.getByRole("button", { name: /run pipeline/i })).toBeDisabled();
  });

  it("allows running once nothing is required", () => {
    render(<ReviewQueue summary={{ ...summary, required: [] }} onOverride={() => {}} onAcknowledge={() => {}} />);
    expect(screen.getByRole("button", { name: /run pipeline/i })).toBeEnabled();
  });

  it("acknowledges all advisory items at once", async () => {
    const onAcknowledge = vi.fn();
    render(<ReviewQueue summary={summary} onOverride={() => {}} onAcknowledge={onAcknowledge} />);
    await userEvent.click(screen.getByRole("button", { name: /acknowledge all/i }));
    expect(onAcknowledge).toHaveBeenCalledWith(["featurecounts.strandedness"]);
  });

  it("says so when there is nothing to review", () => {
    render(<ReviewQueue summary={{ required: [], advisory: [] }} onOverride={() => {}} onAcknowledge={() => {}} />);
    expect(screen.getByText(/nothing needs your attention/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ReviewQueue.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write `ReviewQueue.tsx`**

```tsx
import type { ReviewItem, ReviewSummary } from "../api/client";
import { tierDescription } from "../lib/tiers";

function ItemRow({
  item,
  onOverride,
}: {
  item: ReviewItem;
  onOverride: (key: string, value: string) => void;
}) {
  return (
    <li className="border p-2">
      <p className="font-medium">
        {item.node_id} · {item.param_name}
      </p>
      <p className="text-sm">
        Currently <code>{String(item.value)}</code> — {tierDescription(item.tier)}
      </p>
      <p className="text-xs opacity-70">{item.reason}</p>
      <button
        type="button"
        className="border p-1 mt-1"
        onClick={() => onOverride(item.key, String(item.value))}
      >
        Change {item.param_name}
      </button>
    </li>
  );
}

export function ReviewQueue({
  summary,
  onOverride,
  onAcknowledge,
}: {
  summary: ReviewSummary;
  onOverride: (key: string, value: string) => void;
  onAcknowledge: (keys: string[]) => void;
}) {
  const nothingToDo = summary.required.length === 0 && summary.advisory.length === 0;

  return (
    <section className="flex flex-col gap-4">
      {nothingToDo && <p>Nothing needs your attention — every choice was resolved.</p>}

      {summary.required.length > 0 && (
        <div>
          <h3>Needs your decision ({summary.required.length})</h3>
          <ul className="flex flex-col gap-2">
            {summary.required.map((item) => (
              <ItemRow key={item.key} item={item} onOverride={onOverride} />
            ))}
          </ul>
        </div>
      )}

      {summary.advisory.length > 0 && (
        <div>
          <h3>Check the premise ({summary.advisory.length})</h3>
          <ul className="flex flex-col gap-2">
            {summary.advisory.map((item) => (
              <ItemRow key={item.key} item={item} onOverride={onOverride} />
            ))}
          </ul>
          <button
            type="button"
            className="border p-1 mt-2"
            onClick={() => onAcknowledge(summary.advisory.map((item) => item.key))}
          >
            Acknowledge all
          </button>
        </div>
      )}

      <button type="button" className="border p-2" disabled={summary.required.length > 0}>
        Run pipeline
      </button>
    </section>
  );
}
```

- [ ] **Step 4: Write `BuildPage.tsx`**

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { NodeInspector } from "../components/NodeInspector";
import { PipelineGraph } from "../components/PipelineGraph";
import { ReviewQueue } from "../components/ReviewQueue";

export function BuildPage() {
  const { id = "" } = useParams();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const [progress, setProgress] = useState<string>("");

  const build = useQuery({ queryKey: ["build", id], queryFn: () => api.getBuild(id) });
  const review = useQuery({ queryKey: ["review", id], queryFn: () => api.getReview(id) });

  useEffect(() => {
    const source = new EventSource(`/builds/${id}/events`);
    source.onmessage = (message) => {
      const event = JSON.parse(message.data);
      setProgress(event.message);
      if (event.stage === "done" || event.stage === "failed") {
        source.close();
        queryClient.invalidateQueries({ queryKey: ["build", id] });
        queryClient.invalidateQueries({ queryKey: ["review", id] });
      }
    };
    return () => source.close();
  }, [id, queryClient]);

  if (build.isLoading || !build.data) return <p>{progress || "Loading…"}</p>;

  const ir = build.data.ir;
  const node = ir?.nodes.find((candidate) => candidate.id === selected);

  const handleOverride = async (key: string, value: string) => {
    await api.override(id, key, value, "me");
    queryClient.invalidateQueries({ queryKey: ["build", id] });
  };

  return (
    <main className="grid grid-cols-3 gap-6 p-6">
      <div>{ir && <PipelineGraph ir={ir} onSelect={setSelected} selectedId={selected} />}</div>
      <div>{node && <NodeInspector node={node} onOverride={handleOverride} />}</div>
      <div>
        {review.data && (
          <ReviewQueue
            summary={review.data}
            onOverride={handleOverride}
            onAcknowledge={() => {}}
          />
        )}
      </div>
    </main>
  );
}
```

Wire the router in `src/main.tsx` with a `QueryClientProvider` and a route at `/builds/:id`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npx eslint .`
Expected: PASS, 13 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): review queue and build page with SSE progress"
```

---

### Task 9: Compose, Makefile and CI

**Files:**
- Create: `docker-compose.dev.yml`, `nginx/default.conf`, `.github/workflows/ci.yml`
- Modify: `Makefile`
- Test: `tests/test_compose_config.py`

**Interfaces:**
- Consumes: everything
- Produces: `make dev` bringing up Postgres, Redis, API, worker, frontend; CI running the full suite

- [ ] **Step 1: Write the failing test**

```python
import pathlib

import yaml

ROOT = pathlib.Path(__file__).parent.parent


def test_compose_defines_every_service_the_stack_needs():
    compose = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text())
    assert set(compose["services"]) >= {"postgres", "redis", "api", "worker", "frontend"}


def test_worker_and_api_share_the_same_database():
    compose = yaml.safe_load((ROOT / "docker-compose.dev.yml").read_text())
    api = compose["services"]["api"]["environment"]["MENDEL_DATABASE_URL"]
    worker = compose["services"]["worker"]["environment"]["MENDEL_DATABASE_URL"]
    assert api == worker


def test_ci_runs_both_python_and_frontend_suites():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "uv run pytest" in ci
    assert "vitest run" in ci
    assert "ruff check" in ci
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_compose_config.py -v`
Expected: FAIL with `FileNotFoundError: docker-compose.dev.yml`

- [ ] **Step 3: Write `docker-compose.dev.yml`**

```yaml
services:
  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: mendel
      POSTGRES_PASSWORD: mendel
      POSTGRES_DB: mendel
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mendel"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: { context: ., dockerfile: Dockerfile }
    command: uv run uvicorn mendel_api.main:create_app --factory --host 0.0.0.0 --port 8000
    environment: &backend_env
      MENDEL_DATABASE_URL: postgresql+psycopg://mendel:mendel@postgres:5432/mendel
      MENDEL_REDIS_URL: redis://redis:6379
      MENDEL_PROJECT_ROOT: /app
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    volumes: [".:/app"]
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }

  worker:
    build: { context: ., dockerfile: Dockerfile }
    command: uv run arq mendel_api.worker.WorkerSettings
    environment: *backend_env
    volumes: [".:/app"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }

  frontend:
    image: node:22-alpine
    working_dir: /app/frontend
    command: sh -c "npm install && npm run dev -- --host"
    volumes: [".:/app"]
    ports: ["5173:5173"]
    depends_on: [api]
```

- [ ] **Step 4: Extend the Makefile**

```make
.PHONY: test lint fmt dev migrate front-test
test:
	uv run pytest -v
lint:
	uv run ruff check .
fmt:
	uv run ruff format .
dev:
	docker compose -f docker-compose.dev.yml up --build
migrate:
	cd packages/mendel-api && uv run alembic upgrade head
front-test:
	cd frontend && npx vitest run && npx tsc --noEmit
```

- [ ] **Step 5: Write `.github/workflows/ci.yml`**

```yaml
name: CI
on: [push, pull_request]

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
        working-directory: frontend
      - run: npx vitest run
        working-directory: frontend
      - run: npx tsc --noEmit
        working-directory: frontend

  stub-run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - uses: nf-core/setup-nextflow@v2
      - run: uv sync
      - run: uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --no-ai --gate stub
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_compose_config.py -v && uv run ruff check .`
Expected: PASS, 3 tests.

- [ ] **Step 7: Bring the stack up and verify by hand**

```bash
make dev
```

Then in another terminal: `curl -X POST localhost:8000/builds -H 'Content-Type: application/json' -d '{"prompt":"human paired-end RNA-seq, 12 samples, counts matrix"}'`, and open `http://localhost:5173/builds/<run_id>`. Confirm the graph renders, red items block the run button, and progress streams.

- [ ] **Step 8: Commit**

```bash
git add docker-compose.dev.yml Makefile .github/ tests/test_compose_config.py
git commit -m "chore: dev compose stack, Makefile targets and CI"
```

---

## Self-Review

**Spec coverage.** The sections Plans 1 and 2 deferred:

| Spec section | Covered by |
|---|---|
| §4.4 `mendel-api` package | Tasks 1–5 |
| §6.4 the dashboard falls out of the IR | Tasks 7, 8 — components read the IR directly |
| §6.1 review levels drive triage | Task 6 (`tiers.ts`), Task 8 (blocking behaviour) |
| §5.4 human override of decisions | Task 5 (API), Task 7 (UI) |
| §7.1 `diverged` surfaced to the user | Task 7 (`role="alert"`) |
| §9 FastAPI, ARQ, SQLAlchemy, Alembic, React/Vite/Tailwind/TanStack Query | Tasks 1, 2, 3, 6 |
| §9 generated TypeScript client | Task 6 |
| §11 testing | Tasks 1–9; CI runs both suites plus a `--no-ai` stub-run |

**Clinical data-protection spec coverage.** Amendments to tasks already written, applied while
implementing them:

- **Task 4 (build endpoints)** accepts a profile per build, defaulting to the deployment's, and
  refuses `sealed` without an actor. `POST /builds` takes a typed goal or a prompt; under
  `guarded` a prompt returns `409` with the exact `PromptRequest` payload for confirmation
  rather than sending it, and under `sealed` it returns `400` pointing at typed goals.
- **Task 5 (review endpoints)** records the acting `Actor` on every override. This also settles
  the `by="me"` hardcoding named below: the deployment asserts identity, so the value comes from
  the request context rather than a literal.
- **Task 7 (node inspector)** shows the profile badge, and renders `shadowed` and
  `registry_layers` so a reviewer at another institution can see the build was not stock.
- **New component, `ConfirmEgress.tsx`** — the `guarded` gate. Renders the payload field by
  field, states the destination provider and model, and requires an explicit action. It must not
  be dismissible by clicking away: the whole point is that someone looked.
- **New screen, the egress log** — `EgressRecord`s for a build, showing door, profile, actor,
  destination and digest. This is what an auditor asks for, and it is cheap because the records
  already exist.

**Known gaps, stated rather than hidden:**
- **The forge queue has no HTTP surface.** `routes/proposals.py` appears in the file structure but no task builds it — approval stays CLI-only (`forge pending` / `forge approve`) for now. Adding it is a straight copy of Task 5's shape once the CLI flow has been used enough to know what the UI needs.
- **`onAcknowledge` is wired but inert** in Task 8's `BuildPage`. Acknowledgement needs a persistence decision (per-user? per-run?) that this plan does not make. The button and its test exist so the shape is settled; the handler is a one-line addition once that question is answered.
- **No authentication.** The spec scopes v1 to single-tenant deployment (§12). `by="me"` is hardcoded in `BuildPage`. Do not expose this to a network without addressing that.

**Placeholder scan.** No TBDs. Every code step is runnable. The two inert items above are named explicitly rather than left as silent stubs.

**Type consistency.** `ReviewLevel` is `"none" | "advisory" | "required"` in both `comeni_core.ir.ReviewLevel` (Plan 1) and `frontend/src/lib/tiers.ts`. `ReviewItem` fields match between `routes/reviews.py` and `ReviewQueue.tsx` because the latter imports the generated type. `IRNode` is defined in `PipelineGraph.tsx` and imported by `NodeInspector.tsx` — one definition, not two. `enqueue_build` is defined in `routes/builds.py` and imported by `routes/reviews.py`, so the test monkeypatch in Task 4 targets the right module.

---

## Verification

```bash
make dev                                  # postgres, redis, api, worker, frontend
make migrate                              # apply schema
uv run pytest -v && uv run ruff check .   # backend
make front-test                           # frontend

curl -X POST localhost:8000/builds \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"human paired-end RNA-seq, 12 samples, I want a counts matrix"}'
```

This plan is complete when: the dashboard at `/builds/<id>` streams progress live, renders the DAG with each node showing its worst review level, blocks "Run pipeline" while any red item remains, and an override submitted in the UI triggers a rebuild whose decision record shows `resolved_by: human`.

**Next:** run the `frontend-design` skill over `frontend/src/` to give the dashboard an actual visual identity. Everything above is deliberately unstyled.
