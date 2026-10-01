# Settings 6 — the read-only sections — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The menu tells the truth about everything else the installation is set to: the protection level (Privacy & data), how runs execute (Running, reported by Wiener itself), where the registry and its source tokens stand (Registry & sources), and what is running (System). All read-only, each with its reason.

**Architecture:** Declarations in the catalogue, values from part 4's *reporters*. Mendel serves Privacy & data, Registry & sources and System; Wiener serves Running from its own `GET /api/wiener/settings` with the same `Installation` and an empty store, because only Wiener can read Wiener's `.env`. The frontend merges both menus by section order and says so when Wiener does not answer. No reporter ever returns a secret: a token is reported as *set* or *not set*.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, arq/Redis, React 19, TanStack Query, nginx, Vite.

**Spec:** `docs/superpowers/specs/2026-10-01-settings-design.md` (§7, §9). Issue #215, part 14.7.5.6 of #181. Needs parts 1–4.

> **One deviation from the spec, to confirm with the operator before Task 3:** the spec puts *telemetry on or off* under Privacy & data, but telemetry is Wiener's (`WIENER_OTLP_ENDPOINT`), and a section is served by one API. This plan reports it in Running, with help text that says it is a privacy matter. The alternative is a per-setting `served_by`, which makes the merge per row rather than per section.

## Global Constraints

- **A token is never a declaration's `env`.** `env=` makes the resolver read and show the value. `WIENER_API_TOKEN`, `COMENI_FORGE_GITHUB_TOKEN` and `COMENI_FORGE_DOCKERHUB_TOKEN` are reported by a reporter that answers `set` or `not set`, and the guard in Task 5 searches the served menus for their values.
- Every row here is locked, with `ReadOnlyHere` or `Designed`.
- Wiener's routes take the bearer token like every other Wiener route; `/api/wiener/settings` is not in `OPEN_PATHS`.
- nginx picks the longest matching prefix, so `/api/wiener` needs its own `location`; Vite matches in insertion order, so its proxy entry goes before `/api`.

## Review Focus

1. **Wiener down, or answering 401** (no token in the browser): the other sections still draw, and the menu says Running could not be read and why. Pinned in Task 4.
2. **The database or Redis down:** System reports *not reachable* for that row; the page still draws. Pinned in Task 2.
3. **A token set in `.env`:** its value appears in no served menu. Pinned in Task 5.
4. **The registry root not a git checkout or missing:** the Registry row reports the path and *not readable*, never a 500. Pinned in Task 2.
5. **A reporter that raises:** the row reports *could not be read*, never a 500 for the whole menu. Pinned in Task 1.

---

### Task 1: A reporter that raises is a row that says so

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/installation.py` (`resolved`, the reporter branch)
- Test: `packages/comeni-core/tests/test_settings_installation.py` (append)

- [x] **Step 1: Write the failing test**

```python
def test_a_reporter_that_raises_is_a_row_that_says_so():
    def broken():
        raise ConnectionError("redis://localhost:6379 refused")

    inst = _models(reporters={"models.where": broken})
    got = inst.resolved(WHERE)
    assert got.locked and got.value == "could not be read (ConnectionError)"
    assert "6379" not in str(got.value)
```

- [x] **Step 2: Run it to verify it fails**

Run: `uv run pytest packages/comeni-core/tests/test_settings_installation.py -q -k raises`
Expected: FAIL, `ConnectionError` propagates

- [x] **Step 3: Catch it** — in `resolved`, the reporter branch:

```python
        if setting.kind is Kind.READONLY and setting.key in self.reporters:
            try:
                value = self.reporters[setting.key]()
            except Exception as failed:  # a report must never take the menu down
                # The type, never the message: a message can carry a host, a path or a DSN.
                value = f"could not be read ({type(failed).__name__})"
            return Resolved(
                value=value, source=Source.REPORTED, locked=True,
                reason=setting.unavailable or ReadOnlyHere(why="worked out by the server"),
            )
```

- [x] **Step 4: Run it to verify it passes**

Run: `uv run pytest packages/comeni-core/tests/test_settings_installation.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add packages/comeni-core/
git commit -m "feat(settings): a report that fails is a row that says so (#215)"
```

---

### Task 2: Privacy, Registry & sources, and System — declared and reported by Mendel

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/catalogue.py`
- Create: `packages/mendel-api/src/mendel_api/services/reports.py`
- Modify: `packages/mendel-api/src/mendel_api/services/installation.py` (register the reporters)
- Test: `packages/mendel-api/tests/test_settings_reports.py`
- Regenerate: the golden menu

**Interfaces:**
- Produces (catalogue): `PROTECTION`, `REGISTRY_ROOT`, `REGISTRY_LAYERS`, `GITHUB_TOKEN`, `DOCKERHUB`, `SOURCE_CHECK`, `VERSIONS`, `DATABASE`, `REDIS`, `MODEL_SERVER`; sections `REGISTRY` (order 6) and `SYSTEM` (order 7); `PRIVACY` gains `PROTECTION` first.
- Produces (`reports.py`): `REPORTERS: dict[str, Callable[[], object]]` keyed by those settings' keys; `token_state(name: str) -> str`.

- [x] **Step 1: Declare them** (append to `catalogue.py`; `RO = "read from the server; not changed here"`)

```python
RO = ReadOnlyHere(why="reported by the server; not changed here")

PROTECTION = Setting.choice(
    key="privacy.protection",
    label="Protection level",
    help=(
        "How much of your data a model may see. Level 0 lets a model read an uploaded sample. "
        "Open, guarded and sealed send less, down to nothing at all."
    ),
    options=[
        ("level_0", "Level 0: a model may read an uploaded sample"),
        ("open", "Open"),
        ("guarded", "Guarded"),
        ("sealed", "Sealed"),
    ],
    default="level_0",
    unavailable=Designed(
        where="level 0 arrives with samples (14.7.6); open, guarded and sealed are designed "
        "(issue 71)"
    ),
)


def _reported(key: str, label: str, help: str, why: ReadOnlyHere = RO) -> Setting:
    return Setting.readonly(key=key, label=label, help=help, unavailable=why)


REGISTRY_ROOT = _reported(
    "registry.root", "Registry",
    "The folder the tools and types are read from. Set as MENDEL_REGISTRY_ROOT in .env.",
)
REGISTRY_LAYERS = _reported(
    "registry.layers", "Layers",
    "Each layer stacked on the registry, in order. A later layer can replace an earlier one's tool.",
)
GITHUB_TOKEN = _reported(
    "registry.github", "GitHub token",
    "Lets the forge read nf-core's catalogue without GitHub's anonymous rate limit. Set or not.",
    ReadOnlyHere(why="a deploy secret: set it as COMENI_FORGE_GITHUB_TOKEN in .env"),
)
DOCKERHUB = _reported(
    "registry.dockerhub", "Docker Hub account",
    "Lets the forge read all of pegi3s's images, not only the first hundred. Set or not.",
    ReadOnlyHere(why="a deploy secret: set COMENI_FORGE_DOCKERHUB_USER and _TOKEN in .env"),
)
SOURCE_CHECK = _reported(
    "registry.source_check", "Nightly source check",
    "When the worker re-reads every source to see whether an upstream tool moved.",
)
VERSIONS = _reported(
    "system.versions", "Versions", "The version of each part of this installation."
)
DATABASE = _reported("system.database", "Database", "Whether Mendel's database answers.")
REDIS = _reported("system.redis", "Job queue", "Whether the queue that runs model jobs answers.")
MODEL_SERVER = _reported(
    "system.model", "Default model's server",
    "Whether anything answers at the default model's endpoint. A hosted provider is not probed.",
)

PRIVACY = Section(
    key="privacy", title="Privacy & data", order=4, settings=(PROTECTION, WHERE_PURPOSES)
)
REGISTRY = Section(
    key="registry", title="Registry & sources", order=6,
    settings=(REGISTRY_ROOT, REGISTRY_LAYERS, GITHUB_TOKEN, DOCKERHUB, SOURCE_CHECK),
)
SYSTEM = Section(
    key="system", title="System", order=7, settings=(VERSIONS, DATABASE, REDIS, MODEL_SERVER)
)
```

Replace part 4's `PRIVACY` with this one (it now leads with `PROTECTION`) and add `REGISTRY`, `SYSTEM` to `CATALOGUE`.

- [x] **Step 2: Write the failing reporter tests**

```python
"""What Mendel reports in the read-only sections (spec §7)."""

import pytest
from comeni_core.settings import catalogue as c

from mendel_api.services import reports


def test_every_mendel_read_only_setting_has_a_reporter():
    served = [
        s for section in c.CATALOGUE.served_by("mendel") for s in section.settings
        if s.kind == "readonly"
    ]
    assert served, "nothing is read-only — this test is measuring nothing"
    assert {s.key for s in served} <= set(reports.REPORTERS)


def test_a_token_is_reported_as_set_never_as_itself(monkeypatch):
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN", "ghp_secret_value_1234")
    assert reports.REPORTERS["registry.github"]() == "set"
    monkeypatch.delenv("COMENI_FORGE_GITHUB_TOKEN")
    assert reports.REPORTERS["registry.github"]() == "not set"


def test_docker_hub_needs_both_halves(monkeypatch):
    monkeypatch.setenv("COMENI_FORGE_DOCKERHUB_USER", "someone")
    monkeypatch.delenv("COMENI_FORGE_DOCKERHUB_TOKEN", raising=False)
    assert reports.REPORTERS["registry.dockerhub"]() == "not set (needs both the user and the token)"


def test_versions_name_every_package():
    names = {row["part"] for row in reports.REPORTERS["system.versions"]()}
    assert {"comeni-core", "mendel-api", "comeni-ai"} <= names


def test_a_registry_that_cannot_be_read_says_so(monkeypatch, tmp_path):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "registry_root", tmp_path / "nowhere")
    assert reports.REPORTERS["registry.layers"]().startswith("not readable")


def test_the_source_check_time_is_the_workers_own():
    assert reports.REPORTERS["registry.source_check"]() == "every day at 03:00"


def test_a_database_that_does_not_answer_says_so(monkeypatch):
    from mendel_api import db

    def refuse():
        raise ConnectionRefusedError()

    monkeypatch.setattr(db, "session_scope", refuse)
    assert reports.REPORTERS["system.database"]() == "not reachable"
```

- [x] **Step 3: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_settings_reports.py -q`
Expected: FAIL, `No module named 'mendel_api.services.reports'`

- [x] **Step 4: Write `reports.py`**

```python
"""What Mendel reports in the read-only sections (spec §7).

**A token is reported as set or not set, never as itself**, and is never a declaration's `env`
(which would make the resolver serve it). Every reporter is cheap or bounded: the menu calls
each one on every read.
"""

import asyncio
import contextlib
import os
from collections.abc import Callable
from importlib import metadata

from sqlalchemy import text

from mendel_api import db, worker
from mendel_api.settings import settings

PARTS = (
    "comeni-core", "comeni-ai", "mendel-resolver", "mendel-compiler", "mendel-forge",
    "mendel-api", "dag-core",
)


def token_state(*names: str) -> str:
    present = [bool(os.environ.get(n, "").strip()) for n in names]
    if all(present):
        return "set"
    if any(present):
        return "not set (needs both the user and the token)"
    return "not set"


def _versions() -> list[dict]:
    rows = []
    for part in PARTS:
        try:
            rows.append({"part": part, "version": metadata.version(part)})
        except metadata.PackageNotFoundError:
            rows.append({"part": part, "version": "not installed"})
    return rows


def _layers() -> object:
    from mendel_api.services import registry

    try:
        return [str(p) for p in registry.stack().paths]
    except Exception as failed:
        return f"not readable ({type(failed).__name__}) at {settings.registry_root}"


def _first(value: int | set[int] | None) -> int:
    """arq keeps `hour`/`minute` as given: a number (checked 2026-10-01: `hour: 3`) or a set."""
    if value is None:
        return 0
    return value if isinstance(value, int) else min(value)


def _source_check() -> str:
    for job in worker.WorkerSettings.cron_jobs:
        if job.coroutine.__name__ == "check_sources":
            return f"every day at {_first(job.hour):02d}:{_first(job.minute):02d}"
    return "not scheduled"


def _database() -> str:
    try:
        with db.session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return "not reachable"
    return "answers"


def _redis() -> str:
    from mendel_api.routes.health import _worker_and_depth

    try:
        alive, depth = asyncio.run(_worker_and_depth())
    except Exception:
        return "not reachable"
    return f"answers; worker {'running' if alive else 'not running'}; {depth} waiting"


def _model() -> str:
    from mendel_api.services import probe
    from mendel_api.settings import model_access

    access = model_access()
    if access is None:
        return "no model configured"
    if not access.base_url:
        return f"{access.model}: a hosted provider, not probed"
    with contextlib.suppress(Exception):
        if asyncio.run(probe.answers(access.base_url)):
            return f"{access.model}: answers"
    return f"{access.model}: nothing answered"


REPORTERS: dict[str, Callable[[], object]] = {
    "registry.root": lambda: str(settings.registry_root),
    "registry.layers": _layers,
    "registry.github": lambda: token_state("COMENI_FORGE_GITHUB_TOKEN"),
    "registry.dockerhub": lambda: token_state(
        "COMENI_FORGE_DOCKERHUB_USER", "COMENI_FORGE_DOCKERHUB_TOKEN"
    ),
    "registry.source_check": _source_check,
    "system.versions": _versions,
    "system.database": _database,
    "system.redis": _redis,
    "system.model": _model,
}
```

`asyncio.run` is safe here: FastAPI runs a sync route in a worker thread with no loop of its own.

In `services/installation.py`, merge them: `inst.reporters = {"privacy.where": lambda: where_purposes(inst), **reports.REPORTERS}`.

- [x] **Step 5: Run them, regenerate the golden menu, run the package**

Run: `uv run pytest packages/mendel-api/tests/test_settings_reports.py -q`
Expected: PASS, 7 passed

Run: `SETTINGS_GOLDEN=update uv run pytest packages/comeni-core/tests/test_settings_catalogue.py -q && git diff --stat packages/comeni-core/tests/golden/`
Expected: PASS; read the diff.

Run: `MENDEL_DATABASE_URL=$DB uv run pytest packages/mendel-api packages/comeni-core -q 2>&1 | tail -2`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add packages/comeni-core/ packages/mendel-api/
git commit -m "feat(settings): Privacy, Registry & sources and System, reported (#215)"
```

---

### Task 3: Running — Wiener reports its own

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/catalogue.py` (`RUNNING`, `served_by="wiener"`)
- Create: `packages/wiener-api/src/wiener_api/routes/settings.py`
- Modify: `packages/wiener-api/src/wiener_api/main.py` (include the router)
- Modify: `packages/wiener-api/tests/test_wiener_openapi.py`
- Modify: `ops/nginx/default.conf`, `frontend/vite.config.ts`, `tests/repo/test_compose.py`
- Test: `packages/wiener-api/tests/test_settings_route.py`

**Interfaces:**
- Produces (catalogue): `CONTAINER_RUNTIME`, `LOST_AFTER`, `EXECUTOR`, `API_TOKEN`, `TELEMETRY`, `RUNNING` (order 5, `served_by="wiener"`).
- Produces (Wiener): `GET /api/wiener/settings` → `Menu` (operation `readWienerSettings`).

- [x] **Step 1: Declare Running**

```python
WIENER_ENV = ReadOnlyHere(why="Wiener reads this from its own .env")

CONTAINER_RUNTIME = _reported(
    "running.runtime", "Container runtime",
    "What runs each step's container: docker or singularity. WIENER_CONTAINER_PROFILE.", WIENER_ENV,
)
LOST_AFTER = _reported(
    "running.lost_after", "Call a run lost after",
    "How long a run may say nothing before it is called lost. Longer than the slowest step.",
    WIENER_ENV,
)
EXECUTOR = Setting.choice(
    key="running.executor", label="Where runs execute",
    help="This machine, a Kubernetes cluster or AWS Batch. Only this machine launches today.",
    options=[("local", "This machine"), ("k8s", "Kubernetes"), ("awsbatch", "AWS Batch")],
    default="local",
    unavailable=Designed(where="k8s and awsbatch profiles are emitted, not launched"),
)
API_TOKEN = _reported(
    "running.token", "Who may submit runs",
    "Whether Wiener asks for a token. Open is fine on a laptop; anything reachable needs one.",
    WIENER_ENV,
)
TELEMETRY = _reported(
    "running.telemetry", "Telemetry",
    "Whether run traces and metrics are sent anywhere. Off unless WIENER_OTLP_ENDPOINT is set; "
    "a privacy matter, kept here because Wiener is what sends them.",
    WIENER_ENV,
)
RUNNING = Section(
    key="running", title="Running", order=5, served_by="wiener",
    settings=(EXECUTOR, CONTAINER_RUNTIME, LOST_AFTER, API_TOKEN, TELEMETRY),
)
```

Add `RUNNING` to `CATALOGUE`. The golden test serves `menu("mendel")`, so its file does not change; check with `uv run pytest packages/comeni-core -q`.

- [x] **Step 2: Write the failing Wiener tests**

```python
"""Wiener reports its own settings (spec §7)."""

from fastapi.testclient import TestClient

from wiener_api.main import create_app
from wiener_api.settings import settings


def test_running_is_reported_with_each_value(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "")
    monkeypatch.setattr(settings, "otlp_endpoint", "")
    body = TestClient(create_app()).get("/api/wiener/settings").json()
    assert [s["key"] for s in body["sections"]] == ["running"]
    rows = {e["setting"]["key"]: e["shown"] for e in body["sections"][0]["entries"]}
    assert rows["running.runtime"]["value"] == settings.container_profile
    assert rows["running.token"]["value"].startswith("open")
    assert rows["running.telemetry"]["value"] == "off"
    assert all(shown["locked"] for shown in rows.values())


def test_the_token_is_never_served(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "wiener-secret-token-5678")
    client = TestClient(create_app())
    answer = client.get(
        "/api/wiener/settings", headers={"Authorization": "Bearer wiener-secret-token-5678"}
    )
    assert answer.status_code == 200
    assert "wiener-secret-token-5678" not in answer.text
    assert client.get("/api/wiener/settings").status_code == 401
```

- [x] **Step 3: Run them to verify they fail**

Run: `uv run pytest packages/wiener-api/tests/test_settings_route.py -q`
Expected: FAIL, 404 on `/api/wiener/settings`

- [x] **Step 4: Write the route**

```python
"""Running, as Wiener has it (spec §7). **Wiener reports its own** because only Wiener reads
Wiener's `.env`; Mendel's menu merges this by section order."""

from comeni_core.settings import CATALOGUE, Installation, Menu
from fastapi import APIRouter

from wiener_api.settings import settings

router = APIRouter(prefix="/api/wiener", tags=["settings"])


class _Nothing:
    """Running is read-only: nothing is stored, so the store is empty and refuses writes."""

    def values(self):
        return {}

    def put(self, key, value, by):
        raise PermissionError("Wiener's settings are read-only")


def _reporters() -> dict:
    return {
        "running.runtime": lambda: settings.container_profile,
        "running.lost_after": lambda: f"{settings.lost_after_ms // 60000} minutes",
        "running.token": lambda: (
            "a token is required" if settings.api_token
            else "open: anyone who can reach this API can submit runs"
        ),
        "running.telemetry": lambda: "on" if settings.otlp_endpoint else "off",
    }


@router.get("/settings", operation_id="readWienerSettings", summary="Running, as Wiener has it")
def read_settings() -> Menu:
    return Installation(CATALOGUE, _Nothing(), {}, reporters=_reporters()).menu("wiener")
```

`env={}` on purpose: every Running row is reported, so nothing reads Wiener's environment by name here, and a token cannot be served through a declaration. Include the router in `create_app()` beside `runs_router`; add `("/api/wiener/settings", "get"): "readWienerSettings",` to `test_wiener_openapi.py`. `wiener-api` depends on `comeni-core`? Check `packages/wiener-api/pyproject.toml`; if not, add `"comeni-core>=0.1.0"` and `uv lock`, and record it.

- [x] **Step 5: Route it through nginx and Vite**

`ops/nginx/default.conf`, beside `location /api/artifacts`:

```nginx
  location /api/wiener {
    set $wiener http://wiener-api:8001;
    proxy_pass $wiener$request_uri;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
```

`frontend/vite.config.ts`, before `"/api": …`: `"/api/wiener": "http://localhost",`

`tests/repo/test_compose.py`, in `test_nginx_routes_both_halves_of_the_api`: `assert "location /api/wiener" in conf`.

- [x] **Step 6: Run them**

Run: `uv run pytest packages/wiener-api/tests/test_settings_route.py packages/wiener-api/tests/test_wiener_openapi.py tests/repo/test_compose.py -q`
Expected: PASS

- [x] **Step 7: Commit**

```bash
git add packages/comeni-core/ packages/wiener-api/ ops/nginx/default.conf frontend/vite.config.ts tests/repo/test_compose.py uv.lock
git commit -m "feat(settings): Running, reported by Wiener itself (#215)"
```

---

### Task 4: The menu merges both

**Files:**
- Modify: `frontend/src/preferences/usePreferences.ts` (`useWienerMenu`)
- Modify: `frontend/src/preferences/Preferences.tsx` (merge; a note when Wiener did not answer)
- Regenerate: `make client` (Wiener's schema gains `readWienerSettings`)
- Test: `frontend/src/preferences/Preferences.test.tsx` (append)

- [x] **Step 1: Write the failing tests** (append; reuse `MENU`, `at`)

```tsx
const RUNNING = { sections: [{ key: "running", title: "Running", order: 5, served_by: "wiener", entries: [{
  setting: { key: "running.runtime", label: "Container runtime", help: HELP, kind: "readonly",
             default: null, env: null, options: [], minimum: null, maximum: null, unavailable: null, where: "installation" },
  shown: { value: "docker", source: "reported", locked: true, reason: null, set: null, last4: null },
}] }] };

const both = (wiener: { ok: boolean; status: number; json: () => Promise<unknown> }) =>
  vi.fn().mockImplementation((url: string) => Promise.resolve(
    url === "/api/wiener/settings" ? wiener : { ok: true, status: 200, json: async () => MENU }));

it("adds Wiener's sections in their order", async () => {
  at("/settings/running", both({ ok: true, status: 200, json: async () => RUNNING }));
  expect(await screen.findByText("docker")).toBeTruthy();
  const links = (await screen.findAllByRole("link")).map((a) => a.textContent);
  expect(links.indexOf("Running")).toBeGreaterThan(links.indexOf("Other"));
});

it("still draws Mendel's sections when Wiener does not answer, and says so", async () => {
  at("/settings/lab", both({ ok: false, status: 401, json: async () => ({}) }));
  expect(await screen.findByText("Flavour")).toBeTruthy();
  expect(await screen.findByText(/Running could not be read/)).toBeTruthy();
});
```

- [x] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/preferences/Preferences.test.tsx`
Expected: FAIL, `docker` never appears

- [x] **Step 3: Write it**

`usePreferences.ts`:

```ts
import { get as wienerGet } from "../wiener/api/client";

/** Running comes from Wiener, which reads its own `.env` (spec §7). Its own query, so a Wiener
 *  that is down or wants a token costs one section, not the page. */
export function useWienerMenu() {
  return useQuery({ queryKey: ["settings", "wiener"], queryFn: () => wienerGet<Menu>("/api/wiener/settings"), retry: false });
}
```

`Preferences.tsx`: call `const wiener = useWienerMenu();`, build `const sections = [...(menu.data?.sections ?? []), ...(wiener.data?.sections ?? [])].sort((a, b) => a.order - b.order);`, and under the section nav add:

```tsx
        {wiener.error && (
          <p className="text-secondary text-ink-3 md:mt-4">
            Running could not be read: {wiener.error instanceof Error ? wiener.error.message : "no answer"}.
          </p>
        )}
```

Writes are only offered for Mendel's sections: every Wiener row is locked, so the row never calls `onWrite`.

- [x] **Step 4: Run them, the suite, the type check**

Run: `make client && cd frontend && npx vitest run && npx tsc -b`
Expected: PASS; no type errors

- [x] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(settings): the menu merges Wiener's Running, and says so when it cannot (#215)"
```

---

### Task 5: The secret guard covers every reported token

**Files:**
- Modify: `tests/guards/test_settings_secrets.py` (append)
- Modify: `tests/fixtures/guard-ledger.md` (one row)

- [x] **Step 1: Extend the guard**

```python
def test_no_reported_token_reaches_the_menu(monkeypatch):
    """Tokens that live in `.env` are reported as set or not set. A reporter written as
    `lambda: os.environ["…TOKEN"]` is the defect this refuses."""
    from mendel_api.services import installation as made

    values = {
        "COMENI_FORGE_GITHUB_TOKEN": "ghp_guard_github_0001",
        "COMENI_FORGE_DOCKERHUB_USER": "guard-user",
        "COMENI_FORGE_DOCKERHUB_TOKEN": "dckr_guard_hub_0002",
        "COMENI_AI_API_KEY": "sk-guard-provider-0003",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(made, "_store", lambda: MemoryStore())
    body = TestClient(create_app()).get("/api/settings").text
    leaked = [n for n, v in values.items() if v in body]
    assert not leaked, f"the menu served {leaked}"
```

- [x] **Step 2: Run it, then watch it fail**

Run: `uv run pytest tests/guards/test_settings_secrets.py -q`
Expected: PASS

Break: in `reports.py`, change `"registry.github": lambda: token_state("COMENI_FORGE_GITHUB_TOKEN"),` to `"registry.github": lambda: os.environ["COMENI_FORGE_GITHUB_TOKEN"],`.
Run it again. Expected: FAIL, `the menu served ['COMENI_FORGE_GITHUB_TOKEN']`. Restore, re-run, PASS.

- [x] **Step 3: Record it and commit**

Add a row to the guard ledger as in part 2, Task 5.

```bash
git add tests/guards/test_settings_secrets.py tests/fixtures/guard-ledger.md
git commit -m "test(settings): no reported token reaches the menu — watched failing (#215)"
```

---

### Task 6: Walk it

- [x] **Step 1:** `make dev`; rebuild `wiener-api` (it is baked): `docker compose build wiener-api && docker compose up -d wiener-api`; reload nginx's config (`docker compose restart web`).
- [x] **Step 2:** Open every section at 1280px and 390px. Check: Privacy shows level 0 with *not built*; Running shows the operator's runtime and *open* or *a token is required*; Registry shows the registry path and the tokens as set or not; System shows versions and three health rows. With Wiener stopped (`docker compose stop wiener-api`), the other sections still draw and the note says Running could not be read.
- [x] **Step 3:** Screenshots to the operator; findings become issues under #210 unless they block. Run the checks separately, comment on #215 with the commits, close it.

---

## Execution record

Executed 2026-10-01, in one hand; #215 closed.

- **Telemetry under Running** (the deviation the plan flagged): approved with the plans.
- **Task 2, ruling:** a missing registry folder loads as an empty registry rather than raising;
  the Layers row checks the folder first. The coverage test reads `installation()`'s reporters.
- **Task 4, ruling:** an older test stubbed every fetch with Mendel's menu, so sections doubled
  once Wiener's was merged; its stub answers Wiener separately.
- **Task 6, the walk:** `wiener-api` and `web` were rebuilt (nginx's config is baked into the web
  image). Running answered through nginx; every section fit 390 px; with Wiener stopped the other
  sections drew and the nav said *Running could not be read: … → 502*.
- **Final review** (with plan 5, fresh reviewer): 0 critical, 2 important, both fixed test-first
  — the queue row said Redis answered when it was down; a packet-dropping database held the page
  130 s (the row now has its own 2 s connect timeout). Four minors deferred: no place to enter
  Wiener's token from the 401 note, a direct link to Running flashing *no such section*, Wiener's
  `Installation` built without `server="wiener"`, and the registry re-digested on every read.
