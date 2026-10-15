# Settings 2 — the store, the API and secrets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Settings chosen in the menu are kept in Mendel's Postgres, served by `GET /api/settings`, changed by `PUT /api/settings/{key}`, and a secret is sealed at rest and never returned.

**Architecture:** `mendel-api` supplies the two adapters part 1 declared as `Protocol`s: a Postgres `SettingsStore` (table `installation_setting`, one row per key) and a Fernet `SecretCodec` keyed by `COMENI_SETTINGS_KEY`. One FastAPI dependency builds the `Installation`; the routes are thin. Refusals carry new codes in an `MI0300–MI0399` band: locked is 409, illegal is 422, unknown is the existing 404.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, psycopg 3, `cryptography` (Fernet), pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-settings-design.md` (§8, §9). Issue #212, part 14.7.5.2 of #181. Needs part 1 (#211) merged on the branch.

## Global Constraints

- **The throwaway database:** `docker run -d --rm --name walk-testdb -e POSTGRES_USER=mendel -e POSTGRES_PASSWORD=mendel -e POSTGRES_DB=mendel -p 127.0.0.1:5442:5432 postgres:17-alpine`, then `cd packages/mendel-api && MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run alembic upgrade head`. Every database test command below sets `DB=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel` and passes `MENDEL_DATABASE_URL=$DB` on the command line; `.env` belongs to the operator.
- Diagnostics are declared in `diagnostics.yml` and emitted through `coded()`; regenerate the page with `uv run python tools/generate_diagnostics_doc.py`.
- No response ever carries a secret's plaintext; no log line or traceback either.
- Database tests skip when no database is reachable, by the `_database_is_reachable()` pattern in `test_authoring_service.py`.
- Run `make check`'s parts separately; a failing check in an `&&` chain once did not stop a commit.

## Review Focus

1. **`COMENI_SETTINGS_KEY` set but not a valid Fernet key** (a passphrase): must not crash startup or the menu; secrets are greyed with a `Needs` reason that says the key is malformed. Pinned in Task 3.
2. **The key rotated after a secret was stored**: opening fails; the menu must show the secret as *not set* with a `Needs` reason, never a 500. Pinned in Task 3.
3. **A `PUT` with no `value` field, or `value: null`**: a 422 in FastAPI's shape or `MI0301`, never a stored `null`. Pinned in Task 4.
4. **Two `PUT`s to different keys at the same time:** both land. Pinned in Task 2.
5. **A setting's row exists but the setting was removed from the catalogue:** `GET` ignores the row; nothing crashes. Pinned in Task 2.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/mendel-api/src/mendel_api/models.py` | `InstallationSetting` |
| Create `packages/mendel-api/migrations/versions/d5a1c7e93b20_installation_setting.py` | the table |
| Create `packages/mendel-api/src/mendel_api/services/settings_store.py` | `PostgresStore` |
| Create `packages/mendel-api/src/mendel_api/services/settings_codec.py` | `FernetCodec`, `codec_from_env` |
| Create `packages/mendel-api/src/mendel_api/services/installation.py` | `installation()` — the one place an `Installation` is built |
| Create `packages/mendel-api/src/mendel_api/routes/settings.py` | `GET /settings`, `PUT /settings/{key}` |
| Modify `packages/mendel-api/src/mendel_api/refusals.py` | `locked_handler` (409), `LOCKED` |
| Modify `packages/mendel-api/src/mendel_api/main.py` | include the router, the tag, the handler |
| Modify `packages/mendel-api/pyproject.toml` | `cryptography>=42` |
| Modify `packages/comeni-core/src/comeni_core/diagnostics.yml` | the band and `MI0300`, `MI0301`, `MI0302` |
| Modify `packages/mendel-api/tests/conftest.py` | `clean_settings` fixture |
| Create `packages/mendel-api/tests/test_settings_store.py` | store round trips (database) |
| Create `packages/mendel-api/tests/test_settings_codec.py` | the codec |
| Create `packages/mendel-api/tests/test_settings_routes.py` | the routes |
| Modify `packages/mendel-api/tests/test_openapi.py` | two operation ids |
| Create `tests/guards/test_settings_secrets.py` | a secret never leaves |
| Modify `tests/fixtures/guard-ledger.md` | the guard's row |
| Modify `.env.example` | `COMENI_SETTINGS_KEY` |
| Regenerate `frontend/src/api/schema.d.ts`, `frontend/openapi.json` | `make client` |

---

### Task 1: The table and the migration

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py` (append after `QueueVisit`)
- Create: `packages/mendel-api/migrations/versions/d5a1c7e93b20_installation_setting.py`
- Test: `packages/mendel-api/tests/test_migrations.py` (already compares models to migrations; no edit)

**Interfaces:**
- Produces: `InstallationSetting` with `key: str` (primary key, `String(120)`), `value: dict | list | str | int | float | bool` (`JSON`), `updated_at: datetime` (timezone), `updated_by: str` (`String(200)`).

- [x] **Step 1: Check the migration head before writing one**

Run: `cd packages/mendel-api && uv run alembic heads`
Expected: `c3e8f1a57d20 (head)`. If it is anything else, use that revision as `down_revision` below and record the ruling.

- [x] **Step 2: Add the model**

```python
class InstallationSetting(Base):
    """One setting chosen in the menu, for the whole installation (spec §8).

    **One row per setting rather than one document**, so two people saving two different
    settings cannot overwrite each other, and each row says who changed it last. `updated_by` is
    attribution, as in `QueueVisit`, not authentication. No history table: nothing needs one yet.

    A secret's `value` is sealed text (`services/settings_codec.py`), never the secret.
    """

    __tablename__ = "installation_setting"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str] = mapped_column(String(200))
```

Add `from typing import Any` to the imports at the top of `models.py` if it is not there (`grep -n "^from typing" packages/mendel-api/src/mendel_api/models.py`).

- [x] **Step 3: Run the migrations test to watch it fail**

Run: `uv run pytest packages/mendel-api/tests/test_migrations.py -q`
Expected: FAIL, naming `installation_setting` as a model the migrations never create.

- [x] **Step 4: Write the migration**

```python
"""installation_setting — the settings menu's store (spec 2026-10-01 §8).

Revision ID: d5a1c7e93b20
Revises: c3e8f1a57d20
Create Date: 2026-10-01
"""

import sqlalchemy as sa
from alembic import op

revision: str = "d5a1c7e93b20"
down_revision: str | None = "c3e8f1a57d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installation_setting",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("installation_setting")
```

- [x] **Step 5: Run the migrations test to watch it pass, then apply to the throwaway**

Run: `uv run pytest packages/mendel-api/tests/test_migrations.py -q`
Expected: PASS

Run: `cd packages/mendel-api && MENDEL_DATABASE_URL=$DB uv run alembic upgrade head 2>&1 | tail -1`
Expected: `Running upgrade c3e8f1a57d20 -> d5a1c7e93b20, installation_setting …`

- [x] **Step 6: Commit**

```bash
git add packages/mendel-api/src/mendel_api/models.py packages/mendel-api/migrations/versions/d5a1c7e93b20_installation_setting.py
git commit -m "feat(settings): the installation_setting table (#212)"
```

---

### Task 2: The Postgres store

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/settings_store.py`
- Modify: `packages/mendel-api/tests/conftest.py` (append `clean_settings`)
- Test: `packages/mendel-api/tests/test_settings_store.py`

**Interfaces:**
- Consumes: `InstallationSetting` (Task 1); `session_scope` (`mendel_api.db`).
- Produces: `PostgresStore()` with `values() -> dict[str, object]`, `put(key: str, value: object, by: str) -> None` (an upsert), `who(key: str) -> str | None`.

- [x] **Step 1: Add the fixture** (append to `conftest.py`)

```python
@pytest.fixture
def clean_settings():
    """An empty `installation_setting` around each test. Nothing references it, so it truncates
    alone."""
    from mendel_api.db import session_scope
    from sqlalchemy import text

    with session_scope() as session:
        session.execute(text("TRUNCATE TABLE installation_setting"))
    yield
```

- [x] **Step 2: Write the failing tests**

```python
"""The settings store against the real database (spec §8)."""

import threading

import pytest
from sqlalchemy import text

from mendel_api.db import session_scope


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — see this plan's Global Constraints"
)


def test_a_value_is_read_back(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    store.put("building.pacing", "together", by="someone")
    assert store.values() == {"building.pacing": "together"}
    assert store.who("building.pacing") == "someone"


def test_a_second_put_replaces_the_first(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    store.put("building.pacing", "together", by="a")
    store.put("building.pacing", "ask", by="b")
    assert store.values() == {"building.pacing": "ask"}
    assert store.who("building.pacing") == "b"


def test_structured_values_survive(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    value = [{"name": "Local Ollama", "endpoint": "http://ollama:11434"}]
    store.put("models.connections", value, by="a")
    assert store.values()["models.connections"] == value


def test_two_saves_to_different_keys_both_land(clean_settings):
    from mendel_api.services.settings_store import PostgresStore

    store = PostgresStore()
    threads = [
        threading.Thread(target=store.put, args=(f"building.k{i}", i, "a")) for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.values() == {f"building.k{i}": i for i in range(8)}
```

- [x] **Step 3: Run them to verify they fail**

Run: `MENDEL_DATABASE_URL=$DB uv run pytest packages/mendel-api/tests/test_settings_store.py -q`
Expected: FAIL, `No module named 'mendel_api.services.settings_store'` (and not *skipped*: if it says skipped, the throwaway is not up)

- [x] **Step 4: Write the implementation**

```python
"""The settings store: one row per setting in `installation_setting` (spec §8).

Implements `comeni_core.settings.SettingsStore`. **An upsert, not read-then-write**, so two
saves of the same key cannot both decide the row is missing; two saves of different keys never
touch the same row at all.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from mendel_api.db import session_scope
from mendel_api.models import InstallationSetting


class PostgresStore:
    def values(self) -> dict[str, object]:
        with session_scope() as session:
            rows = session.execute(select(InstallationSetting.key, InstallationSetting.value))
            return {key: value for key, value in rows}

    def put(self, key: str, value: object, by: str) -> None:
        now = datetime.now(UTC)
        statement = insert(InstallationSetting).values(
            key=key, value=value, updated_at=now, updated_by=by
        )
        statement = statement.on_conflict_do_update(
            index_elements=[InstallationSetting.key],
            set_={"value": value, "updated_at": now, "updated_by": by},
        )
        with session_scope() as session:
            session.execute(statement)

    def who(self, key: str) -> str | None:
        with session_scope() as session:
            return session.scalar(
                select(InstallationSetting.updated_by).where(InstallationSetting.key == key)
            )
```

- [x] **Step 5: Run them to verify they pass**

Run: `MENDEL_DATABASE_URL=$DB uv run pytest packages/mendel-api/tests/test_settings_store.py -q`
Expected: PASS, 4 passed

- [x] **Step 6: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/settings_store.py packages/mendel-api/tests/conftest.py packages/mendel-api/tests/test_settings_store.py
git commit -m "feat(settings): the Postgres store, one row per setting (#212)"
```

---

### Task 3: The secret codec

**Files:**
- Modify: `packages/mendel-api/pyproject.toml` (`dependencies`, add `"cryptography>=42",`)
- Create: `packages/mendel-api/src/mendel_api/services/settings_codec.py`
- Test: `packages/mendel-api/tests/test_settings_codec.py`
- Modify: `.env.example` (after the `COMENI_AI_*` block)

**Interfaces:**
- Produces: `FernetCodec(key: str)` with `seal(plain) -> str`, `open(sealed) -> str` (raises `UnreadableSecret`); `codec_from_env(env: Mapping[str, str]) -> FernetCodec | None`; `MalformedSettingsKey` reason helper `key_problem(env) -> str | None`.

Two failure modes from the Review Focus shape this task. A malformed key is reported, not raised, so `codec_from_env` returns `None` and `key_problem()` says why; part 1's resolver then greys every secret. A secret sealed under an old key cannot be opened; `Installation.get` would raise, so `installation()` in Task 4 wraps the codec in `Tolerant`, which turns an unreadable secret into *not set*.

- [x] **Step 1: Add the dependency**

In `packages/mendel-api/pyproject.toml`, add `"cryptography>=42",` to `dependencies` after `"pydantic-settings>=2.4",`. Then run `uv lock && uv sync`.
Expected: the lockfile changes only in `mendel-api`'s dependency list (`git diff --stat uv.lock` is small); `cryptography` was already installed transitively.

- [x] **Step 2: Write the failing tests**

```python
"""The secret codec: Fernet, keyed by COMENI_SETTINGS_KEY (spec §8)."""

import pytest
from cryptography.fernet import Fernet

from mendel_api.services.settings_codec import (
    FernetCodec,
    Tolerant,
    UnreadableSecret,
    codec_from_env,
    key_problem,
)

KEY = Fernet.generate_key().decode()


def test_a_secret_round_trips_and_the_sealed_text_is_not_the_secret():
    codec = FernetCodec(KEY)
    sealed = codec.seal("sk-abcdef1234")
    assert "sk-abcdef1234" not in sealed
    assert codec.open(sealed) == "sk-abcdef1234"


def test_no_key_means_no_codec_and_no_problem_to_report():
    assert codec_from_env({}) is None
    assert key_problem({}) is None


def test_a_malformed_key_means_no_codec_and_says_why():
    env = {"COMENI_SETTINGS_KEY": "correct horse battery staple"}
    assert codec_from_env(env) is None
    assert "COMENI_SETTINGS_KEY" in key_problem(env)


def test_a_secret_sealed_under_another_key_is_unreadable():
    sealed = FernetCodec(Fernet.generate_key().decode()).seal("sk-old")
    with pytest.raises(UnreadableSecret):
        FernetCodec(KEY).open(sealed)


def test_tolerant_turns_an_unreadable_secret_into_nothing():
    sealed = FernetCodec(Fernet.generate_key().decode()).seal("sk-old")
    assert Tolerant(FernetCodec(KEY)).open(sealed) == ""


def test_the_codec_never_prints_its_key():
    codec = FernetCodec(KEY)
    assert KEY not in repr(codec) and KEY not in str(codec)
```

- [x] **Step 3: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_settings_codec.py -q`
Expected: FAIL, `No module named 'mendel_api.services.settings_codec'`

- [x] **Step 4: Write the implementation**

```python
"""Sealing secrets stored from the menu (spec §8).

**Fernet**, keyed by `COMENI_SETTINGS_KEY` in `.env`. Generate one with
`uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

**A missing or malformed key is reported, never raised.** `codec_from_env` returns `None` and the
resolver greys every secret with a reason; `key_problem` is that reason's text when the key is
present but unusable. A menu that crashed because `.env` held a passphrase would hide the one
message that says how to fix it.

**An unreadable secret is not set.** Rotating the key leaves every sealed value unopenable;
`Tolerant` turns that into an empty value, which `Installation.shown` reports as *not set*, so
the person is asked for the key again rather than shown a 500.
"""

from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken
from comeni_core.settings import SETTINGS_KEY_ENV


class UnreadableSecret(ValueError):
    """A sealed value this key cannot open. Its message never includes the value."""


class FernetCodec:
    def __init__(self, key: str):
        self._fernet = Fernet(key.encode())

    def __repr__(self) -> str:
        return "FernetCodec(<key hidden>)"

    __str__ = __repr__

    def seal(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode()).decode()

    def open(self, sealed: str) -> str:
        try:
            return self._fernet.decrypt(sealed.encode()).decode()
        except InvalidToken:
            raise UnreadableSecret("a stored secret was sealed under another key") from None


class Tolerant:
    """A codec whose `open` answers `""` for a secret it cannot read."""

    def __init__(self, inner: FernetCodec):
        self._inner = inner

    def seal(self, plain: str) -> str:
        return self._inner.seal(plain)

    def open(self, sealed: str) -> str:
        try:
            return self._inner.open(sealed)
        except UnreadableSecret:
            return ""


def _key(env: Mapping[str, str]) -> str:
    return env.get(SETTINGS_KEY_ENV, "").strip()


def codec_from_env(env: Mapping[str, str]) -> FernetCodec | None:
    key = _key(env)
    if not key:
        return None
    try:
        return FernetCodec(key)
    except (ValueError, TypeError):
        return None


def key_problem(env: Mapping[str, str]) -> str | None:
    """Why the key in `.env` cannot be used, or `None` when it can or is absent."""
    if _key(env) and codec_from_env(env) is None:
        return (
            f"{SETTINGS_KEY_ENV} in .env is not a Fernet key; generate one with "
            "Fernet.generate_key()"
        )
    return None
```

- [x] **Step 5: Make an unreadable secret read as not set in part 1's facade**

`Installation.shown` treats `get()`'s `""` as set. Change it in `packages/comeni-core/src/comeni_core/settings/installation.py`, in `shown()`:

```python
        plain = self.get(setting) or None  # "" is a secret the codec could not open: not set
```

and add to `packages/comeni-core/tests/test_settings_installation.py`:

```python
def test_a_secret_the_codec_cannot_open_is_shown_as_not_set():
    class Forgetful(Reversing):
        def open(self, sealed):
            return ""

    inst = Installation(CATALOGUE, MemoryStore(), {}, codec=Forgetful())
    inst.store.rows["models.key"] = "sealed:anything"
    shown = inst.shown(KEY)
    assert (shown.set, shown.last4) == (False, None)
```

Run: `uv run pytest packages/comeni-core/tests/test_settings_installation.py -q` before the change (Expected: the new test FAILS, `set` is `True`) and after (Expected: PASS).

- [x] **Step 6: Run the codec tests to verify they pass**

Run: `uv run pytest packages/mendel-api/tests/test_settings_codec.py -q`
Expected: PASS, 6 passed

- [x] **Step 7: Document the key in `.env.example`**

After the `COMENI_AI_MAX_CONCURRENT_JOBS` lines, add:

```bash

# ── secrets typed into the settings menu ──────────────────────────────────────────────────
#
# **Unset means the menu cannot store a secret**, and says so beside every key field: put the
# key in this file instead (COMENI_AI_API_KEY), or set this. A Fernet key, generated with:
#   uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Changing it makes every stored secret unreadable; the menu then asks for them again.
COMENI_SETTINGS_KEY=
```

- [x] **Step 8: Commit**

```bash
git add packages/mendel-api/pyproject.toml uv.lock packages/mendel-api/src/mendel_api/services/settings_codec.py packages/mendel-api/tests/test_settings_codec.py packages/comeni-core/src/comeni_core/settings/installation.py packages/comeni-core/tests/test_settings_installation.py .env.example
git commit -m "feat(settings): secrets sealed with Fernet; a bad or rotated key greys, never crashes (#212)"
```

---

### Task 4: The routes, the codes and the 409

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/installation.py`
- Create: `packages/mendel-api/src/mendel_api/routes/settings.py`
- Modify: `packages/mendel-api/src/mendel_api/refusals.py` (append `locked_handler`, `LOCKED`)
- Modify: `packages/mendel-api/src/mendel_api/main.py` (import, tag, handler, router)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (band line in the header; three entries)
- Modify: `packages/mendel-api/tests/test_openapi.py` (two ids)
- Test: `packages/mendel-api/tests/test_settings_routes.py`

**Interfaces:**
- Consumes: `Installation`, `Menu`, `Shown`, `SettingLocked`, `IllegalValue`, `CATALOGUE`, `Needs` (part 1); `PostgresStore` (Task 2); `codec_from_env`, `Tolerant`, `key_problem` (Task 3).
- Produces: `installation() -> Installation` (a FastAPI dependency; tests override it); `GET /api/settings` → `Menu` (operation `readSettings`); `PUT /api/settings/{key}` with body `{"value": ...}` → `Shown` (operation `writeSetting`); `MI0300` locked (409), `MI0301` no value (422), `MI0302` illegal value (422).

- [x] **Step 1: Declare the codes**

In `diagnostics.yml`'s header band list, after the `MI0200-MI0299` line, add:

```yaml
#   MI0300-MI0399  the API: settings — what the menu may change
```

Append, in code order beside the other `MI` entries:

```yaml
MI0300:
  emitted_by: api
  concern: settings
  says: "this setting is locked and cannot be changed here"
  fires_on: [settings]
  refuses: true
  fix: |
    Read the reason beside the setting. If it is pinned by .env, change the variable there and
    restart; if it is not built yet, it cannot be changed anywhere.
  explanation: |
    A value in .env beats the menu, so a deployment's files stay the truth. A setting that is
    designed but not built is shown so the menu says what is coming, and refuses a change
    because nothing would read it.
MI0301:
  emitted_by: api
  concern: settings
  says: "a setting was saved with no value"
  fires_on: [settings]
  refuses: true
  fix: |
    Send {"value": ...}. To go back to the default, choose the default value.
  explanation: |
    An empty save would store nothing a person chose, and the menu would then report a value
    nobody set.
MI0302:
  emitted_by: api
  concern: settings
  says: "this value is not one this setting can hold"
  fires_on: [settings]
  refuses: true
  fix: |
    Choose one of the values the setting offers, or a number inside its bounds.
  explanation: |
    Every setting declares what it can hold, and a value outside that is refused before it is
    stored, so the code that reads the setting never meets one.
```

Run: `uv run python tools/generate_diagnostics_doc.py`

- [x] **Step 2: Write the failing route tests**

```python
"""The settings routes (spec §8). The catalogue and store are overridden: these tests are about
the transport, and the store has its own tests."""

import pytest
from fastapi.testclient import TestClient

from comeni_core.settings import Catalogue, Installation, Section, Setting

from mendel_api.main import create_app
from mendel_api.services.installation import installation

HELP = "How the build walks you through its steps, one at a time or all at once."
PACING = Setting.choice(
    key="building.pacing", label="Pacing", help=HELP,
    options=[("together", "Together"), ("ask", "Ask")], default="ask", env="COMENI_BUILD_PACING",
)
KEY = Setting.secret(key="models.key", label="Key", help=HELP)
CATALOGUE = Catalogue(
    sections=(
        Section(key="building", title="Building", order=1, settings=(PACING,)),
        Section(key="models", title="Models", order=2, settings=(KEY,)),
    )
)


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value


class Reversing:
    def seal(self, plain):
        return "sealed:" + plain[::-1]

    def open(self, sealed):
        return sealed.removeprefix("sealed:")[::-1]


@pytest.fixture
def made():
    return {"env": {}, "store": MemoryStore()}


@pytest.fixture
def client(made):
    app = create_app()
    app.dependency_overrides[installation] = lambda: Installation(
        CATALOGUE, made["store"], made["env"], codec=Reversing()
    )
    return TestClient(app)


def test_the_menu_lists_every_section_with_values_and_sources(client):
    body = client.get("/api/settings").json()
    assert [s["key"] for s in body["sections"]] == ["building", "models"]
    entry = body["sections"][0]["entries"][0]
    assert entry["setting"]["key"] == "building.pacing"
    assert entry["shown"] == {
        "value": "ask", "source": "default", "locked": False, "reason": None,
        "set": None, "last4": None,
    }


def test_a_put_is_stored_and_answered_with_what_is_now_shown(client, made):
    answer = client.put("/api/settings/building.pacing", json={"value": "together"})
    assert answer.status_code == 200
    assert answer.json()["source"] == "installation"
    assert made["store"].rows == {"building.pacing": "together"}


def test_a_locked_setting_answers_409_with_its_code_and_reason(client, made):
    made["env"]["COMENI_BUILD_PACING"] = "together"
    answer = client.put("/api/settings/building.pacing", json={"value": "ask"})
    assert answer.status_code == 409
    assert answer.json()["detail"].startswith("MI0300")
    assert "COMENI_BUILD_PACING" in answer.json()["detail"]


def test_an_illegal_value_answers_422_with_its_code(client):
    answer = client.put("/api/settings/building.pacing", json={"value": "sometimes"})
    assert answer.status_code == 422
    assert answer.json()["detail"].startswith("MI0302")


@pytest.mark.parametrize("body", [{}, {"value": None}])
def test_a_put_with_no_value_answers_422(client, made, body):
    answer = client.put("/api/settings/building.pacing", json=body)
    assert answer.status_code == 422
    assert made["store"].rows == {}


def test_an_unknown_setting_answers_404(client):
    assert client.put("/api/settings/building.nothing", json={"value": 1}).status_code == 404


def test_a_secret_comes_back_as_set_and_last_four(client, made):
    answer = client.put("/api/settings/models.key", json={"value": "sk-abcdef1234"})
    assert answer.json()["value"] is None and answer.json()["last4"] == "1234"
    assert "sk-abcdef1234" not in client.get("/api/settings").text
    assert made["store"].rows["models.key"] != "sk-abcdef1234"
```

- [x] **Step 3: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_settings_routes.py -q`
Expected: FAIL, `No module named 'mendel_api.services.installation'`

- [x] **Step 4: Write the dependency**

`services/installation.py`:

```python
"""The one place an `Installation` is built (spec §8).

**Built per request, never held**: the store is read on every use, and `.env` is read at call
time for the reason `settings.model_access` gives. A test overrides this dependency rather than
monkeypatching the store.
"""

import os

from comeni_core.settings import CATALOGUE, Installation

from mendel_api.services.settings_codec import Tolerant, codec_from_env
from mendel_api.services.settings_store import PostgresStore


def installation() -> Installation:
    codec = codec_from_env(os.environ)
    return Installation(
        CATALOGUE, PostgresStore(), os.environ, codec=Tolerant(codec) if codec else None
    )
```

- [x] **Step 5: Write the refusal and the routes**

Append to `refusals.py`:

```python
async def locked_handler(request: Request, exc: Exception) -> JSONResponse:
    """A setting that is locked is a 409: the request was well formed and the resource's state
    refuses it. The detail is coded and carries the reason a person reads beside the field."""
    from comeni_core.diagnostics import coded

    return JSONResponse(status_code=409, content={"detail": coded("MI0300", str(exc))})


#: Attach to an operation that can meet a locked setting.
LOCKED: dict[int | str, dict[str, Any]] = {
    409: {"model": Refusal, "description": "`MI0300`: the setting is locked; the detail says why."}
}
```

`routes/settings.py`:

```python
"""The settings menu's API (spec §8): read every section, change one setting.

**Thin on purpose.** The resolver, the checks and the sealing are `comeni_core.settings`; this
file turns their refusals into codes and status codes and adds nothing else.
"""

from typing import Annotated

from comeni_core.diagnostics import coded
from comeni_core.settings import IllegalValue, Installation, Menu, Shown
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, JsonValue

from mendel_api.identity import default_author
from mendel_api.refusals import LOCKED, REFUSES
from mendel_api.services.installation import installation

router = APIRouter(prefix="/settings", tags=["settings"])


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JsonValue = None


@router.get("", operation_id="readSettings", summary="Every setting, its value and its source")
def read_settings(inst: Annotated[Installation, Depends(installation)]) -> Menu:
    return inst.menu("mendel")


@router.put(
    "/{key}",
    operation_id="writeSetting",
    summary="Change one setting for this installation",
    responses={**REFUSES, **LOCKED},
)
def write_setting(
    key: str, change: Change, inst: Annotated[Installation, Depends(installation)]
) -> Shown:
    if change.value is None:
        raise ValueError(coded("MI0301", f"{key} was saved with no value"))
    try:
        return inst.put(key, change.value, by=default_author())
    except IllegalValue as refused:
        raise ValueError(coded("MI0302", f"{key}: {refused}")) from None
```

In `main.py`:
- import `from mendel_api.routes import settings as settings_routes` and `from comeni_core.settings import SettingLocked`;
- add `locked_handler` to the `from mendel_api.refusals import ...` line;
- add to `TAGS`: `{"name": "settings", "description": "What this installation may change, and where each value came from."},`
- after the `KeyError` handler: `app.add_exception_handler(SettingLocked, locked_handler)`
- after the authoring router: `app.include_router(settings_routes.router, prefix="/api")`

`IllegalValue` subclasses `ValueError`; it is caught in the route so it gets its code, and never reaches the plain `ValueError` handler uncoded.

- [x] **Step 6: Name the operations in `test_openapi.py`**

Add to the dict in `test_every_operation_is_named_by_hand`:

```python
        ("/api/settings", "get"): "readSettings",
        ("/api/settings/{key}", "put"): "writeSetting",
```

- [x] **Step 7: Run everything this task touched**

Run: `uv run pytest packages/mendel-api/tests/test_settings_routes.py packages/mendel-api/tests/test_openapi.py tests/diagnostics -q 2>&1 | tail -3`
Expected: PASS. If `tests/diagnostics` reports a code declared but never emitted, the emission is in the wrong package; the ownership test reads `packages/mendel-api/src`.

Run against the real store: `MENDEL_DATABASE_URL=$DB uv run python -c "from fastapi.testclient import TestClient; from mendel_api.main import create_app; print(TestClient(create_app()).get('/api/settings').json()['sections'][0]['key'])"`
Expected: `appearance`

- [x] **Step 8: Commit**

```bash
git add packages/mendel-api/src/mendel_api/services/installation.py packages/mendel-api/src/mendel_api/routes/settings.py packages/mendel-api/src/mendel_api/refusals.py packages/mendel-api/src/mendel_api/main.py packages/comeni-core/src/comeni_core/diagnostics.yml docs/handbook/reference/diagnostics.md packages/mendel-api/tests/test_settings_routes.py packages/mendel-api/tests/test_openapi.py
git commit -m "feat(settings): GET and PUT /api/settings, locked is MI0300 and a 409 (#212)"
```

(Check the generated diagnostics page's path with `git status` before adding; `CLAUDE.md` names `docs/handbook/reference/diagnostics.md`.)

---

### Task 5: The guard — a secret never leaves

**Files:**
- Create: `tests/guards/test_settings_secrets.py`
- Modify: `tests/fixtures/guard-ledger.md` (one row)

**Interfaces:**
- Consumes: `create_app`, `installation` (Task 4); `Installation`, `Setting`, `Catalogue`, `Section` (part 1); `FernetCodec` (Task 3).

- [x] **Step 1: Write the guard**

```python
"""A secret typed into the settings menu never leaves through the API (spec §8, §9).

**Every response the settings routes can give is searched for the plaintext**, after the secret
is stored through the real Fernet codec. The leak this refuses is a serializer that dumps the
resolved value: one line, and the most likely way a key would reach a browser.
"""

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from comeni_core.settings import Catalogue, Installation, Section, Setting
from mendel_api.main import create_app
from mendel_api.services.installation import installation
from mendel_api.services.settings_codec import FernetCodec

PLAIN = "sk-guard-0123456789"
HELP = "The key a provider asks for. Stored sealed, and shown only as its last four."
KEY = Setting.secret(key="models.key", label="Key", help=HELP)
CATALOGUE = Catalogue(sections=(Section(key="models", title="Models", order=1, settings=(KEY,)),))


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value


def _client(store):
    codec = FernetCodec(Fernet.generate_key().decode())
    app = create_app()
    app.dependency_overrides[installation] = lambda: Installation(CATALOGUE, store, {}, codec)
    return TestClient(app)


def test_no_settings_response_and_no_stored_row_holds_the_plaintext():
    store = MemoryStore()
    client = _client(store)
    answers = [
        client.put("/api/settings/models.key", json={"value": PLAIN}),
        client.get("/api/settings"),
        client.put("/api/settings/models.key", json={"value": PLAIN + "x"}),
    ]
    assert answers, "nothing was asked — this guard is measuring nothing"
    for answer in answers:
        assert answer.status_code == 200, answer.text
        assert PLAIN not in answer.text, f"{answer.request.method} leaked the secret"
    assert all(PLAIN not in str(value) for value in store.rows.values()), "stored unsealed"
```

- [x] **Step 2: Run it to watch it pass**

Run: `uv run pytest tests/guards/test_settings_secrets.py -q`
Expected: PASS, 1 passed

- [x] **Step 3: Watch it fail against the defect**

Break the code under test: in `packages/comeni-core/src/comeni_core/settings/installation.py`, in `shown()`, change `value=None,` (the secret branch) to `value=plain,`.

Run: `uv run pytest tests/guards/test_settings_secrets.py -q`
Expected: FAIL with `PUT leaked the secret`. Copy the message.

Restore `value=None,` and re-run. Expected: PASS.

- [x] **Step 4: Record it in the ledger**

Append a row to the newest table in `tests/fixtures/guard-ledger.md` (read its last section first and match its columns):

```markdown
| 2026-10-?? | `tests/guards/test_settings_secrets.py` | `Installation.shown` returned the plaintext as `value` for a secret | failed on the first PUT | `PUT leaked the secret` |
```

- [x] **Step 5: Commit**

```bash
git add tests/guards/test_settings_secrets.py tests/fixtures/guard-ledger.md
git commit -m "test(settings): a secret never leaves the settings API — watched failing (#212)"
```

---

### Task 6: The generated client, and the whole check

**Files:**
- Regenerate: `frontend/openapi.json`, `frontend/src/api/schema.d.ts` (and Wiener's, unchanged)

- [x] **Step 1: Regenerate the clients**

Run: `make client && git diff --stat frontend/`
Expected: `frontend/src/api/schema.d.ts` and `frontend/openapi.json` change; the diff names `readSettings`, `writeSetting`, `Menu`, `Shown`, `Setting`.

- [x] **Step 2: Type-check the frontend**

Run: `cd frontend && npx tsc -b`
Expected: no errors (nothing consumes the new types yet)

- [x] **Step 3: Run the checks, one at a time**

Run each, reading each result before the next:
- `uv run ruff check .` → clean
- `MENDEL_DATABASE_URL=$DB uv run pytest packages/mendel-api packages/comeni-core tests/guards tests/diagnostics -q 2>&1 | tail -3` → all pass, none skipped for want of a database in the settings files
- `make types docs links doc-paths doc-sizes` → pass

- [x] **Step 4: Commit**

```bash
git add frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "chore(client): regenerate for the settings API (#212)"
```

---

## Execution record

Executed 2026-10-01, in one hand. Commits 748859d..9bf87b6.

- **Task 3, ruling:** `cryptography` was **not** already in the project's environment; the check
  that said so read a conda environment. It is now a real dependency of `mendel-api`
  (cryptography 50.0.2, with cffi and pycparser in `uv.lock`).
- **Task 4, rulings:** the settings `Option` collided with the authoring `Option` in the OpenAPI
  schema and is `ChoiceOption`; `tools/generate_diagnostics_doc.py` needed a heading for the new
  `settings` concern.
- **Task 6, ruling:** `test_models.py` holds a literal list of tables; `installation_setting` is
  added with its argument.
- **Found, not caused here:** five failures exist on the commit before this plan (`748859d`):
  four in `test_forge_jobs.py` (`MF0001: 'fake' is not a catalogue source`) and
  `test_full_cycle.py::test_the_loop_closes`.
- **Final review** (plans 1 and 2 together, fresh reviewer): 0 critical, 4 important, all fixed
  test-first — a malformed `COMENI_SETTINGS_KEY` now says so; a rotated key shows *not set* with
  a reason, and `get()` raises rather than handing out `""` (`Tolerant` removed); secrets are
  handed over as `SecretStr`; a setting another server serves is never written here. A fifth,
  re-graded from minor, also fixed: a key under 12 characters shows no last four. Six minors
  deferred: NaN/inf accepted by an unbounded number, a malformed body's 422 echoing its input,
  `refusals.py` layout, a non-text secret's message, and the guard covering only good bodies.
