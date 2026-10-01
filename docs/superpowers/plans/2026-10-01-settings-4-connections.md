# Settings 4 — connections and a model per purpose — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In Settings → Models a person adds connections (a model server or a provider, each with a Test button), picks a model for each purpose from every connection's model list, and every AI call then uses its purpose's model. Settings → Privacy & data shows where each purpose's data goes.

**Architecture:** Part 1's declarations gain two kinds: `collection` (a list of records, here connections, with secret fields sealed per record and a locked *From .env* record built from the environment) and `model` (a `{connection, model}` choice that names a record of a collection). The `Installation` facade gains *reporters* (server-computed read-only values) and per-record *actions* (`test`, `models`) behind one generic route. In `mendel-api`, `model_access(agent, purpose)` maps each call to a menu purpose and builds its `ModelAccess` from the chosen connection; every call site passes its purpose. The frontend gains a generic collection editor, a model picker and a table for list-valued read-only settings.

**Tech Stack:** Python 3.12, pydantic 2, FastAPI, httpx, React 19, TanStack Query 5, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-01-settings-design.md` (§6, §7, §9). Issue #214, part 14.7.5.4 of #181. Needs parts 1–3.

> **Written before parts 1–3 exist.** Every interface consumed below is the one parts 1–3's plans produce. Read their execution records first: a ruling there that renamed or reshaped something changes this plan, and the change is recorded here as a ruling.

## Global Constraints

- Invariant 13: the self-hosted and hosted lanes differ by configuration only. No `if hosted:` branch decides how a call is made; only *where each purpose goes* (a report) reads the server kind.
- Invariant 12: no subscription OAuth. A connection holds an endpoint and an API key, nothing else.
- Invariant 14: a connection adds no door. A model call leaves through the door its `AiPoint` already declares; `FREE_TEXT_FIELDS` in `tests/guards/test_egress.py` does not change.
- A health check never sends a prompt: *Test* opens a socket; *models* lists `/v1/models`; neither carries data.
- `.env` keeps working unchanged: `COMENI_AI_MODEL`, `_BASE_URL`, `_API_KEY` (and the deprecated `MENDEL_*` names `comeni_ai.access` still reads) configure the default model as before.
- Model calls in tests use recorded fixtures or fakes, never a live model.
- The throwaway database and `DB=…` as in part 2's Global Constraints.

## Review Focus

1. **Only deprecated `MENDEL_MODEL` set** (an installation not yet migrated): `model_access()` must still return that model, as today. Pinned in Task 4.
2. **A purpose chosen, no default model:** the purpose's calls use it, and `model_access()` (*is anything configured*) answers yes. Pinned in Task 4.
3. **A connection renamed or removed while a purpose points at it:** the purpose shows a `Needs` note and its calls fall back to the default, never a 500. Pinned in Tasks 2 and 4.
4. **Saving the connections list without retyping each key:** a record sent with `key: null` keeps its stored key. Pinned in Task 2.
5. **An endpoint that hangs on `/v1/models`:** the action answers within its timeout with `ok: false`, and the picker still offers *Other…*. Pinned in Task 5.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `packages/comeni-core/src/comeni_core/settings/declare.py` | `Kind.MODEL`, `Kind.COLLECTION`, `EnvItem`, `FROM_ENV`, the `fields`/`item_name`/`from_env`/`actions`/`of` fields, their checks |
| Modify `packages/comeni-core/src/comeni_core/settings/resolve.py` | `Source.REPORTED` |
| Modify `packages/comeni-core/src/comeni_core/settings/installation.py` | reporters; collections (env record, sealing per field, masking); a model naming a missing record |
| Modify `packages/comeni-core/src/comeni_core/settings/catalogue.py` | Models (connections, six purposes), Privacy & data (*where each purpose goes*) |
| Modify `packages/comeni-core/src/comeni_core/settings/__init__.py` | export the new names |
| Create `packages/mendel-api/src/mendel_api/services/models.py` | `PURPOSES` map, `access_for`, `where_purposes` |
| Create `packages/mendel-api/src/mendel_api/services/probe.py` | `answers(base_url)` (moved from `routes/health.py`), `listed(endpoint, server)` |
| Create `packages/mendel-api/src/mendel_api/services/settings_actions.py` | `ACTIONS`, `ActionResult` |
| Modify `packages/mendel-api/src/mendel_api/settings.py` | `model_access(agent=None, purpose=None)` |
| Modify `packages/mendel-api/src/mendel_api/services/installation.py` | reporters; `_store` seam |
| Modify `packages/mendel-api/src/mendel_api/routes/settings.py` | `POST /settings/{key}/items/{name}/{action}` |
| Modify `packages/mendel-api/src/mendel_api/routes/health.py` | import `answers` from `probe` |
| Modify `packages/mendel-api/src/mendel_api/services/authoring_jobs.py`, `authoring_ai.py`, `forge_jobs.py` | pass the purpose |
| Modify `packages/mendel-api/tests/conftest.py` | autouse: an empty in-memory store unless a test asks for the real one |
| Create `frontend/src/preferences/Collection.tsx`, `ModelPicker.tsx`, `Report.tsx`, `useAction.ts` | the new controls |

---

### Task 1: Two new kinds — model and collection

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/declare.py`
- Test: `packages/comeni-core/tests/test_settings_declare.py` (append)

**Interfaces:**
- Produces: `Kind.MODEL = "model"`, `Kind.COLLECTION = "collection"`; `FROM_ENV = "From .env"`; `EnvItem(name: str, present_when: str, fields: dict[str, str])`; new `Setting` fields `fields: tuple[Setting, ...] = ()`, `item_name: str = "name"`, `from_env: EnvItem | None = None`, `actions: tuple[str, ...] = ()`, `of: str | None = None`; `Setting.field_name -> str` (the key's last segment); factories `Setting.model(...)`, `Setting.collection(...)`.

A model value is `None` (*same as the default*) or `{"connection": str, "model": str}`. A collection value is a list of records keyed by field name; a record's secret field holds sealed text, `None` (*keep what is stored*) or `""` (*clear it*), and the facade (Task 2) turns those into stored values.

- [ ] **Step 1: Write the failing tests** (append)

```python
from comeni_core.settings.declare import FROM_ENV, EnvItem

NAME = Setting.text(key="connection.name", label="Name", help=HELP)
ENDPOINT = Setting.text(key="connection.endpoint", label="Endpoint", help=HELP)
SECRET = Setting.secret(key="connection.key", label="Key", help=HELP)


def _connections(**over):
    return Setting.collection(
        key="models.connections", label="Connections", help=HELP,
        fields=(NAME, ENDPOINT, SECRET), actions=("test",), **over,
    )


def test_a_collection_holds_records_with_unique_names():
    connections = _connections()
    assert connections.default == []
    good = [{"name": "Local", "endpoint": "http://ollama:11434", "key": None}]
    assert connections.check(good) == good
    with pytest.raises(IllegalValue, match="twice"):
        connections.check(good + good)


def test_a_record_with_an_unknown_field_is_refused():
    with pytest.raises(IllegalValue, match="colour"):
        _connections().check([{"name": "Local", "colour": "red"}])


def test_a_record_needs_a_name():
    with pytest.raises(IllegalValue, match="name"):
        _connections().check([{"name": "", "endpoint": "x"}])


def test_a_missing_field_takes_its_default():
    assert _connections().check([{"name": "Local"}]) == [
        {"name": "Local", "endpoint": "", "key": None}
    ]


def test_a_collection_names_its_record_field():
    with pytest.raises(ValidationError, match="name"):
        Setting.collection(
            key="models.connections", label="C", help=HELP, fields=(ENDPOINT,)
        )


def test_a_model_is_the_default_or_a_connection_and_a_model():
    want = Setting.model(
        key="models.want", label="Want", help=HELP, of="models.connections",
        env="COMENI_AI_MODEL_WANT",
    )
    assert want.check(None) is None
    assert want.check({"connection": "Local", "model": "ollama_chat/gemma3:4b"})
    with pytest.raises(IllegalValue):
        want.check({"connection": "Local"})
    assert want.parse_env("ollama_chat/gemma3:4b") == {
        "connection": FROM_ENV, "model": "ollama_chat/gemma3:4b",
    }


def test_a_model_says_which_collection_it_picks_from():
    with pytest.raises(ValidationError, match="of"):
        Setting.model(key="models.want", label="Want", help=HELP)


def test_an_env_record_names_fields_the_collection_has():
    with pytest.raises(ValidationError, match="colour"):
        _connections(from_env=EnvItem(
            name=FROM_ENV, present_when="COMENI_AI_MODEL", fields={"colour": "X"}
        ))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/comeni-core/tests/test_settings_declare.py -q`
Expected: FAIL, `ImportError: cannot import name 'FROM_ENV'`

- [ ] **Step 3: Write the implementation** — additions to `declare.py`

Add to `Kind`:

```python
    MODEL = "model"
    """`None` — the default model — or `{"connection": name, "model": id}`."""
    COLLECTION = "collection"
    """A list of records, each keyed by field name. Connections are one."""
```

Add above `class Setting`:

```python
FROM_ENV = "From .env"
"""The name of the record `.env` supplies. Locked: it is changed in `.env`, never in the menu."""


class EnvItem(BaseModel):
    """A record built from the environment, shown first and locked (spec §6).

    `fields` maps a record field to the variable that fills it; the record exists when
    `present_when` is set. Declared, so the facade needs no code that knows about models.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    present_when: str
    fields: dict[str, str]
```

Add to `Setting`'s fields:

```python
    fields: tuple["Setting", ...] = ()
    """A collection's record fields. Each is a declaration; its key's last segment is the name."""
    item_name: str = "name"
    from_env: EnvItem | None = None
    actions: tuple[str, ...] = ()
    """What a record can be asked to do — `test`, `models`. Served by the API, drawn as buttons."""
    of: str | None = None
    """For a model: the key of the collection whose records it picks from."""

    @property
    def field_name(self) -> str:
        return self.key.rsplit(".", 1)[1]
```

In `_coherent`, before the `if self.kind not in (Kind.SECRET, Kind.READONLY):` check, add:

```python
        if self.kind is Kind.COLLECTION:
            names = [f.field_name for f in self.fields]
            if self.item_name not in names:
                raise ValueError(f"a collection's records need a {self.item_name!r} field")
            if self.from_env and set(self.from_env.fields) - set(names):
                raise ValueError(
                    f"from_env names fields the records do not have: "
                    f"{sorted(set(self.from_env.fields) - set(names))}"
                )
        elif self.fields or self.from_env or self.actions:
            raise ValueError("fields, from_env and actions belong to a collection only")
        if self.kind is Kind.MODEL and not self.of:
            raise ValueError("a model setting says which collection it picks from, as `of`")
```

Add to `check`'s `match`:

```python
            case Kind.MODEL:
                if value is not None and (
                    not isinstance(value, dict)
                    or set(value) != {"connection", "model"}
                    or not all(isinstance(v, str) and v.strip() for v in value.values())
                ):
                    raise IllegalValue("a model is a connection and a model id, or the default")
            case Kind.COLLECTION:
                return self._records(value)
```

Add the method and the factories:

```python
    def _records(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not all(isinstance(r, dict) for r in value):
            raise IllegalValue("a list of records")
        by_name = {f.field_name: f for f in self.fields}
        records, seen = [], set()
        for record in value:
            unknown = set(record) - set(by_name)
            if unknown:
                raise IllegalValue(f"no field called {', '.join(sorted(unknown))}")
            name = record.get(self.item_name)
            if not isinstance(name, str) or not name.strip():
                raise IllegalValue(f"every record needs a {self.item_name}")
            if name in seen:
                raise IllegalValue(f"{name!r} is named twice")
            seen.add(name)
            clean = {}
            for field_name, field in by_name.items():
                raw = record.get(field_name, field.default)
                if field.kind is Kind.SECRET:
                    if raw is not None and not isinstance(raw, str):
                        raise IllegalValue(f"{field_name} is text")
                    clean[field_name] = raw
                else:
                    clean[field_name] = field.check(raw)
            records.append(clean)
        return records
```

```python
    @classmethod
    def model(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.MODEL, **fields)

    @classmethod
    def collection(cls, **fields: Any) -> "Setting":
        return cls(kind=Kind.COLLECTION, **{"default": [], **fields})
```

In `parse_env`, before `return raw`:

```python
        if self.kind is Kind.MODEL:
            return {"connection": FROM_ENV, "model": raw}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest packages/comeni-core/tests/test_settings_declare.py -q`
Expected: PASS (part 1's 20 and these 8)

- [ ] **Step 5: Commit**

```bash
git add packages/comeni-core/src/comeni_core/settings/declare.py packages/comeni-core/tests/test_settings_declare.py
git commit -m "feat(settings): model and collection kinds (#214)"
```

---

### Task 2: The facade — reporters, collections and a model's connection

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/resolve.py` (`Source.REPORTED`)
- Modify: `packages/comeni-core/src/comeni_core/settings/installation.py`
- Test: `packages/comeni-core/tests/test_settings_installation.py` (append)

**Interfaces:**
- Consumes: Task 1's kinds and fields; part 1's `Installation`, `SettingLocked`, `Needs`, `ReadOnlyHere`, `SETTINGS_KEY_ENV`.
- Produces: `Source.REPORTED = "reported"`; `Installation(..., reporters: Mapping[str, Callable[[], object]] | None = None)`; `Installation.record(setting, name) -> dict | None` (secrets opened); collection behaviour below.

Behaviour, each a test:
- A collection's resolved value is the stored records, with the *From .env* record first when its `present_when` variable is set. That record carries `"locked": True`; stored records carry nothing extra.
- `put` on a collection ignores a record named `FROM_ENV`; for a secret field, `None` keeps the stored sealed value of the record with the same name, `""` clears it, other text is sealed. Text to seal with no codec raises `SettingLocked` with the settings-key `Needs`.
- `shown` masks each record's secret fields as `{"set": bool, "last4": str | None}`.
- `get` returns records with secrets opened; the env record's key comes from its variable.
- A model whose connection is not a record of its `of` collection resolves to `None` with `Needs(what="the connection '<name>' is gone; choose another")`, unlocked.
- A read-only setting with a reporter resolves to the reporter's value, `Source.REPORTED`, locked, with its declared reason.

- [ ] **Step 1: Write the failing tests** (append; the file already has `MemoryStore`, `Reversing`, `HELP`)

```python
from comeni_core.settings import ReadOnlyHere, Source
from comeni_core.settings.declare import FROM_ENV, EnvItem

CONNECTIONS = Setting.collection(
    key="models.connections", label="Connections", help=HELP,
    fields=(
        Setting.text(key="connection.name", label="Name", help=HELP),
        Setting.text(key="connection.endpoint", label="Endpoint", help=HELP),
        Setting.secret(key="connection.key", label="Key", help=HELP),
    ),
    from_env=EnvItem(
        name=FROM_ENV, present_when="COMENI_AI_MODEL",
        fields={"endpoint": "COMENI_AI_BASE_URL", "key": "COMENI_AI_API_KEY"},
    ),
)
WANT = Setting.model(key="models.want", label="Want", help=HELP, of="models.connections")
WHERE = Setting.readonly(
    key="models.where", label="Where", help=HELP, unavailable=ReadOnlyHere(why="worked out"),
)
MODELS = Catalogue(
    sections=(Section(key="models", title="Models", order=1, settings=(CONNECTIONS, WANT, WHERE)),)
)
LOCAL = {"name": "Local", "endpoint": "http://ollama:11434", "key": None}


def _models(env=None, codec=Reversing(), reporters=None):
    return Installation(MODELS, MemoryStore(), env or {}, codec=codec, reporters=reporters)


def test_the_env_record_comes_first_and_locked():
    inst = _models(env={"COMENI_AI_MODEL": "ollama_chat/gemma3:12b", "COMENI_AI_BASE_URL": "http://o"})
    inst.put("models.connections", [LOCAL], by="a")
    records = inst.shown(CONNECTIONS).value
    assert [r["name"] for r in records] == [FROM_ENV, "Local"]
    assert records[0]["locked"] is True and "locked" not in records[1]


def test_a_put_never_stores_the_env_record():
    inst = _models(env={"COMENI_AI_MODEL": "m"})
    inst.put("models.connections", [{"name": FROM_ENV, "endpoint": "x"}, LOCAL], by="a")
    assert [r["name"] for r in inst.store.rows["models.connections"]] == ["Local"]


def test_a_record_key_is_sealed_kept_on_null_and_cleared_on_empty():
    inst = _models()
    inst.put("models.connections", [{**LOCAL, "key": "sk-abcdef1234"}], by="a")
    sealed = inst.store.rows["models.connections"][0]["key"]
    assert sealed != "sk-abcdef1234"
    inst.put("models.connections", [{**LOCAL, "endpoint": "http://new"}], by="a")
    assert inst.store.rows["models.connections"][0]["key"] == sealed
    assert inst.record(CONNECTIONS, "Local")["key"] == "sk-abcdef1234"
    inst.put("models.connections", [{**LOCAL, "key": ""}], by="a")
    assert inst.store.rows["models.connections"][0]["key"] is None


def test_a_record_key_is_shown_masked():
    inst = _models()
    inst.put("models.connections", [{**LOCAL, "key": "sk-abcdef1234"}], by="a")
    shown = inst.shown(CONNECTIONS).value[0]
    assert shown["key"] == {"set": True, "last4": "1234"}
    assert "sk-abcdef1234" not in inst.menu().model_dump_json()


def test_a_record_key_without_a_codec_is_refused():
    with pytest.raises(SettingLocked):
        _models(codec=None).put("models.connections", [{**LOCAL, "key": "sk-1"}], by="a")


def test_the_env_record_key_comes_from_env():
    inst = _models(env={"COMENI_AI_MODEL": "m", "COMENI_AI_API_KEY": "sk-env-9999"})
    assert inst.record(CONNECTIONS, FROM_ENV)["key"] == "sk-env-9999"
    assert inst.shown(CONNECTIONS).value[0]["key"] == {"set": True, "last4": "9999"}


def test_a_model_naming_a_gone_connection_needs_another():
    inst = _models()
    inst.put("models.connections", [LOCAL], by="a")
    inst.put("models.want", {"connection": "Local", "model": "ollama_chat/gemma3:4b"}, by="a")
    inst.put("models.connections", [], by="a")
    got = inst.resolved(WANT)
    assert (got.value, got.locked) == (None, False)
    assert "Local" in got.reason.what


def test_a_model_cannot_be_put_naming_a_connection_that_does_not_exist():
    with pytest.raises(IllegalValue, match="Nowhere"):
        _models().put("models.want", {"connection": "Nowhere", "model": "m"}, by="a")


def test_a_reported_value_comes_from_its_reporter():
    inst = _models(reporters={"models.where": lambda: [{"purpose": "Want", "goes": "here"}]})
    got = inst.resolved(WHERE)
    assert (got.source, got.locked) == (Source.REPORTED, True)
    assert got.value == [{"purpose": "Want", "goes": "here"}]
```

Add `IllegalValue` to the file's imports if missing.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/comeni-core/tests/test_settings_installation.py -q`
Expected: FAIL, `TypeError: Installation.__init__() got an unexpected keyword argument 'reporters'`

- [ ] **Step 3: Add `Source.REPORTED`** in `resolve.py`:

```python
    REPORTED = "reported"
    """Computed by the server on each read — *where each purpose goes*, versions, health."""
```

- [ ] **Step 4: Extend `installation.py`**

Constructor gains `reporters: Mapping[str, Callable[[], object]] | None = None` (stored as `self.reporters = reporters or {}`; import `Callable` from `collections.abc`). Then replace `resolved`, `get`, `shown` and `put`, and add the helpers:

```python
    def resolved(self, setting: Setting) -> Resolved:
        if setting.kind is Kind.READONLY and setting.key in self.reporters:
            return Resolved(
                value=self.reporters[setting.key](),
                source=Source.REPORTED,
                locked=True,
                reason=setting.unavailable or ReadOnlyHere(why="worked out by the server"),
            )
        got = resolve(
            setting, self.store.values(), self.env, secrets_available=self.codec is not None
        )
        if setting.kind is Kind.COLLECTION:
            records = list(got.value or [])
            own = self._env_record(setting)
            return got.model_copy(update={"value": ([own] if own else []) + records})
        if setting.kind is Kind.MODEL and isinstance(got.value, dict):
            names = {r["name"] for r in self._records_of(setting)}
            if got.value["connection"] not in names:
                gone = got.value["connection"]
                return Resolved(
                    value=None,
                    source=Source.DEFAULT,
                    locked=False,
                    reason=Needs(what=f"the connection {gone!r} is gone; choose another"),
                )
        return got

    def _env_record(self, setting: Setting) -> dict | None:
        spec = setting.from_env
        if spec is None or not self.env.get(spec.present_when, "").strip():
            return None
        record = {f.field_name: f.default for f in setting.fields}
        record[setting.item_name] = spec.name
        for field_name, variable in spec.fields.items():
            record[field_name] = self.env.get(variable, "").strip() or None
        return {**record, "locked": True}

    def _records_of(self, model: Setting) -> list[dict]:
        return list(self.resolved(self.catalogue.setting(model.of)).value or [])

    def _secret_fields(self, setting: Setting) -> list[str]:
        return [f.field_name for f in setting.fields if f.kind is Kind.SECRET]

    def record(self, setting: Setting, name: str) -> dict | None:
        """One record with its secrets opened — what the code that uses a connection calls."""
        for record in self.resolved(setting).value or []:
            if record[setting.item_name] != name:
                continue
            opened = {k: v for k, v in record.items() if k != "locked"}
            if not record.get("locked"):
                for field in self._secret_fields(setting):
                    if opened.get(field):
                        assert self.codec is not None
                        opened[field] = self.codec.open(opened[field]) or None
            return opened
        return None

    def get(self, setting: Setting) -> object:
        """The value for the code that uses it. **The only place a secret is opened.**"""
        if setting.kind is Kind.COLLECTION:
            return [
                self.record(setting, r[setting.item_name])
                for r in self.resolved(setting).value or []
            ]
        got = self.resolved(setting)
        if setting.kind is Kind.SECRET and got.source is Source.INSTALLATION:
            assert self.codec is not None
            return self.codec.open(str(got.value))
        return got.value

    def shown(self, setting: Setting) -> Shown:
        got = self.resolved(setting)
        if setting.kind is Kind.COLLECTION:
            masked = []
            for record in got.value or []:
                plain = self.record(setting, record[setting.item_name]) or {}
                view = dict(record)
                for field in self._secret_fields(setting):
                    value = plain.get(field)
                    view[field] = {"set": bool(value), "last4": value[-4:] if value else None}
                masked.append(view)
            return Shown(value=masked, source=got.source, locked=got.locked, reason=got.reason)
        if setting.kind is not Kind.SECRET:
            return Shown(value=got.value, source=got.source, locked=got.locked, reason=got.reason)
        plain = self.get(setting) or None
        return Shown(
            value=None, source=got.source, locked=got.locked, reason=got.reason,
            set=plain is not None, last4=str(plain)[-4:] if plain is not None else None,
        )

    def put(self, key: str, value: object, by: str) -> Shown:
        setting = self.catalogue.setting(key)
        if setting.where is Where.BROWSER:
            raise SettingLocked(setting, BROWSER_ONLY)
        got = self.resolved(setting)
        if got.locked:
            assert got.reason is not None
            raise SettingLocked(setting, got.reason)
        if setting.kind is Kind.COLLECTION:
            checked = self._sealed_records(setting, value)
        else:
            checked = setting.check(value)
        if setting.kind is Kind.MODEL and checked is not None:
            names = {r["name"] for r in self._records_of(setting)}
            if checked["connection"] not in names:
                raise IllegalValue(f"no connection called {checked['connection']!r}")
        if setting.kind is Kind.SECRET:
            assert self.codec is not None
            checked = self.codec.seal(checked)
        self.store.put(key, checked, by)
        return self.shown(setting)

    def _sealed_records(self, setting: Setting, value: object) -> list[dict]:
        own = setting.from_env.name if setting.from_env else None
        incoming = [r for r in (value or []) if isinstance(r, dict) and r.get(setting.item_name) != own]
        records = setting.check(incoming)
        stored = {
            r[setting.item_name]: r for r in self.store.values().get(setting.key, []) or []
        }
        for record in records:
            for field in self._secret_fields(setting):
                given = record[field]
                if given is None:
                    record[field] = stored.get(record[setting.item_name], {}).get(field)
                elif given == "":
                    record[field] = None
                else:
                    if self.codec is None:
                        raise SettingLocked(
                            setting,
                            Needs(what=f"set {SETTINGS_KEY_ENV} in .env to store keys here"),
                        )
                    record[field] = self.codec.seal(given)
        return records
```

Import `Needs` and `SETTINGS_KEY_ENV`, `IllegalValue`, `Resolved` where missing.

- [ ] **Step 5: Run the facade's tests and part 1's**

Run: `uv run pytest packages/comeni-core/tests/test_settings_installation.py packages/comeni-core/tests/test_settings_resolve.py -q`
Expected: PASS, every test

- [ ] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/settings/ packages/comeni-core/tests/test_settings_installation.py
git commit -m "feat(settings): collections with sealed keys, an env record, reporters (#214)"
```

---

### Task 3: The Models and Privacy sections

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/catalogue.py`
- Modify: `packages/comeni-core/src/comeni_core/settings/__init__.py` (export `FROM_ENV`, `EnvItem`, and the new constants)
- Regenerate: `packages/comeni-core/tests/golden/settings-menu.json`

**Interfaces:**
- Produces in `comeni_core.settings.catalogue`: `CONNECTIONS`, `DEFAULT_MODEL`, `MODEL_WANT`, `MODEL_TALK`, `MODEL_TIER4`, `MODEL_READBACK`, `MODEL_FORGE`, `PURPOSE_SETTINGS: tuple[Setting, ...]` (the five purposes, not the default), `WHERE_PURPOSES`, `MODELS`, `PRIVACY`.

- [ ] **Step 1: Declare them** — append to `catalogue.py` and replace `CATALOGUE`:

```python
from comeni_core.settings.declare import FROM_ENV, EnvItem
from comeni_core.settings.reasons import ReadOnlyHere

CONNECTIONS = Setting.collection(
    key="models.connections",
    label="Connections",
    help=(
        "Where models are reached: a model server on this machine or your network, or a "
        "provider with a key. Add one, test it, then choose a model for each purpose below."
    ),
    fields=(
        Setting.text(
            key="connection.name", label="Name",
            help="What this connection is called here, e.g. Local Ollama.",
        ),
        Setting.choice(
            key="connection.server", label="Server",
            help="What answers at the endpoint. It decides how model ids are written.",
            options=[
                ("ollama", "Ollama"),
                ("openai_compatible", "Another OpenAI-compatible server (vLLM, LM Studio)"),
                ("hosted", "A hosted provider"),
            ],
            default="ollama",
        ),
        Setting.text(
            key="connection.endpoint", label="Endpoint",
            help="The server's address, e.g. http://ollama:11434. Empty for a hosted provider.",
        ),
        Setting.secret(
            key="connection.key", label="Key",
            help="The provider's API key. Stored sealed; shown only as its last four characters.",
        ),
    ),
    from_env=EnvItem(
        name=FROM_ENV,
        present_when="COMENI_AI_MODEL",
        fields={"endpoint": "COMENI_AI_BASE_URL", "key": "COMENI_AI_API_KEY"},
    ),
    actions=("test", "models"),
)


def _purpose(name: str, label: str, help: str) -> Setting:
    return Setting.model(
        key=f"models.{name}", label=label, help=help, of="models.connections",
        env=f"COMENI_AI_MODEL_{name.upper()}",
    )


DEFAULT_MODEL = Setting.model(
    key="models.default",
    label="Default model",
    help=(
        "The model every purpose uses unless it names its own. COMENI_AI_MODEL in .env sets "
        "it, through the From .env connection."
    ),
    of="models.connections",
    env="COMENI_AI_MODEL",
)
MODEL_WANT = _purpose(
    "want", "Understanding what you want",
    "Reads what you asked for and picks what it should produce. The call most worth a strong model.",
)
MODEL_TALK = _purpose(
    "talk", "Talking with you",
    "Phrases the questions the build asks you and reads your replies. A small model is enough.",
)
MODEL_TIER4 = _purpose(
    "tier4", "Choosing where the rules cannot",
    "Proposes an answer to a choice no rule settles (tier 4). Always shown to you as a model's.",
)
MODEL_READBACK = _purpose(
    "readback", "Reading the plan back",
    "Says back, in a sentence, what the pipeline will do, so you can check it was understood.",
)
MODEL_FORGE = _purpose(
    "forge", "Adapting tools",
    "Drafts a new tool's contract in the registry's workshop, for a person to review.",
)
PURPOSE_SETTINGS = (MODEL_WANT, MODEL_TALK, MODEL_TIER4, MODEL_READBACK, MODEL_FORGE)

WHERE_PURPOSES = Setting.readonly(
    key="privacy.where",
    label="Where each purpose goes",
    help=(
        "For each purpose, whether what it sends stays on this machine or your network, or "
        "goes to a provider. Worked out from the connection each purpose uses."
    ),
    unavailable=ReadOnlyHere(why="worked out from Settings → Models"),
)

MODELS = Section(
    key="models", title="Models", order=3,
    settings=(CONNECTIONS, DEFAULT_MODEL, *PURPOSE_SETTINGS),
)
PRIVACY = Section(key="privacy", title="Privacy & data", order=4, settings=(WHERE_PURPOSES,))

CATALOGUE = Catalogue(sections=(APPEARANCE, MODELS, PRIVACY))
```

Remove the old one-line `CATALOGUE = Catalogue(sections=(APPEARANCE,))`. Update the module docstring's second paragraph: Models and Privacy arrive here.

- [ ] **Step 2: Regenerate and read the golden menu**

Run: `SETTINGS_GOLDEN=update uv run pytest packages/comeni-core/tests/test_settings_catalogue.py -q && git diff --stat packages/comeni-core/tests/golden/`
Expected: PASS; the diff adds the `models` and `privacy` sections. Read it: every purpose's `env` is `COMENI_AI_MODEL_<NAME>`, the default's is `COMENI_AI_MODEL`.

Run: `uv run pytest packages/comeni-core -q 2>&1 | tail -2`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/comeni-core/src/comeni_core/settings/ packages/comeni-core/tests/golden/settings-menu.json
git commit -m "feat(settings): Models — connections and a model per purpose; where each purpose goes (#214)"
```

---

### Task 4: Every call uses its purpose's model

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/models.py`
- Modify: `packages/mendel-api/src/mendel_api/settings.py` (`model_access`)
- Modify: `packages/mendel-api/src/mendel_api/services/installation.py` (`_store` seam, reporters)
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_jobs.py:69-72` and its seven `_client()` calls
- Modify: `packages/mendel-api/src/mendel_api/services/authoring_ai.py:480-492` (`_call`'s fallback)
- Modify: `packages/mendel-api/src/mendel_api/services/forge_jobs.py:449-485` (`_client`, `_model_id`)
- Modify: `packages/mendel-api/tests/conftest.py` (autouse `settings_in_memory`)
- Test: `packages/mendel-api/tests/test_models_per_purpose.py`

**Interfaces:**
- Consumes: Task 3's catalogue names; `Installation.record`, `Installation.get` (Task 2); `ModelAccess.from_env` (`comeni_ai`); `Purpose` (`mendel_api.services.authoring_ai`); `InvocationPurpose` (`mendel_forge.workflow`).
- Produces: `PURPOSES: dict[tuple[str, str], Setting]` (`("builder", "goal") → MODEL_WANT`, …); `access_for(inst, env, agent=None, purpose=None) -> ModelAccess | None`; `where_purposes(inst) -> list[dict]`; `model_access(agent: str | None = None, purpose: str | None = None) -> ModelAccess | None`.

The map, from the two enums as they are today (re-read both before writing it):

| agent | purposes | menu setting |
|---|---|---|
| `builder` | `goal`, `family` | `MODEL_WANT` |
| `builder` | `chat`, `gap`, `ask` | `MODEL_TALK` |
| `builder` | `tier4` | `MODEL_TIER4` |
| `builder` | `readback` | `MODEL_READBACK` |
| `forge` | `analysis`, `implementation`, `repair`, `chat` | `MODEL_FORGE` |

The fallback order for one call: the purpose's own model → the default model → the legacy environment (`ModelAccess.from_env(os.environ)`, which still reads `MENDEL_*`). With no agent and no purpose (*is anything configured?*): the default → the first purpose that has one → the legacy environment.

- [ ] **Step 1: The in-memory seam for the suite**

In `services/installation.py`, split the store out so tests can replace it:

```python
def _store():
    """The store `installation()` reads. A seam: the suite swaps in an empty one (`conftest.py`),
    so tests that only set the environment keep meaning what they meant before settings."""
    return PostgresStore()


def installation() -> Installation:
    from mendel_api.services.models import where_purposes

    codec = codec_from_env(os.environ)
    inst = Installation(
        CATALOGUE, _store(), os.environ, codec=Tolerant(codec) if codec else None
    )
    inst.reporters = {"privacy.where": lambda: where_purposes(inst)}
    return inst
```

Append to `tests/conftest.py`:

```python
class _MemoryStore:
    def __init__(self):
        self.rows = {}

    def values(self):
        return dict(self.rows)

    def put(self, key, value, by):
        self.rows[key] = value


@pytest.fixture(autouse=True)
def settings_in_memory(request, monkeypatch):
    """**Settings start empty and live in memory** unless a test is marked `real_settings`.

    `model_access()` reads the settings store since part 14.7.5.4. Most of this suite configures
    a model through the environment and has no database; an empty store keeps those tests
    meaning exactly what they meant. Yields the store so a test can choose a model.
    """
    if request.node.get_closest_marker("real_settings"):
        yield None
        return
    from mendel_api.services import installation

    store = _MemoryStore()
    monkeypatch.setattr(installation, "_store", lambda: store)
    yield store
```

Register the marker: in the root `pyproject.toml`'s `[tool.pytest.ini_options]` `markers` list (create the key if absent), add `"real_settings: read settings from the real Postgres store"`.

- [ ] **Step 2: Write the failing tests**

```python
"""Each call uses its purpose's model (spec §6)."""

import pytest
from comeni_ai import access as ai_access
from comeni_core.settings import catalogue

from mendel_api.services import authoring_ai, installation
from mendel_api.services.models import PURPOSES, access_for, where_purposes
from mendel_api.settings import model_access
from mendel_forge.workflow import InvocationPurpose


@pytest.fixture
def clean_env(monkeypatch):
    for name in (*ai_access.DEPRECATED, *ai_access.DEPRECATED.values()):
        monkeypatch.delenv(name, raising=False)
    for setting in (catalogue.DEFAULT_MODEL, *catalogue.PURPOSE_SETTINGS):
        monkeypatch.delenv(setting.env, raising=False)


def _choose(store, **purposes):
    store.rows["models.connections"] = [
        {"name": "Local", "server": "ollama", "endpoint": "http://ollama:11434", "key": None}
    ]
    for name, model in purposes.items():
        store.rows[f"models.{name}"] = {"connection": "Local", "model": model}


def test_every_call_purpose_maps_to_a_menu_purpose():
    builder = {("builder", p.value) for p in authoring_ai.Purpose}
    forge = {("forge", p.value) for p in InvocationPurpose}
    assert builder and forge, "an enum is empty — this test is measuring nothing"
    assert builder | forge == set(PURPOSES), "a call purpose has no model in Settings"


def test_a_purpose_uses_its_own_model(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/gemma3:12b", talk="ollama_chat/gemma3:4b")
    assert model_access("builder", "ask").model == "ollama_chat/gemma3:4b"
    assert model_access("builder", "ask").base_url == "http://ollama:11434"
    assert model_access("builder", "goal").model == "ollama_chat/gemma3:12b"


def test_a_purpose_without_its_own_model_uses_the_default(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/qwen2.5:7b")
    assert model_access("forge", "analysis").model == "ollama_chat/qwen2.5:7b"


def test_a_purpose_with_no_default_still_counts_as_configured(clean_env, settings_in_memory):
    _choose(settings_in_memory, talk="ollama_chat/gemma3:4b")
    assert model_access() is not None
    assert model_access("builder", "goal") is None


def test_the_env_still_configures_the_default(clean_env, monkeypatch):
    monkeypatch.setenv("COMENI_AI_MODEL", "ollama_chat/gemma3:12b")
    monkeypatch.setenv("COMENI_AI_BASE_URL", "http://ollama:11434")
    got = model_access("builder", "readback")
    assert (got.model, got.base_url) == ("ollama_chat/gemma3:12b", "http://ollama:11434")


def test_a_deprecated_name_alone_still_works(clean_env, monkeypatch):
    monkeypatch.setenv("MENDEL_MODEL", "ollama_chat/gemma3:12b")
    assert model_access().model == "ollama_chat/gemma3:12b"


def test_an_env_purpose_pin_uses_the_env_connection(clean_env, monkeypatch):
    monkeypatch.setenv("COMENI_AI_MODEL", "ollama_chat/gemma3:12b")
    monkeypatch.setenv("COMENI_AI_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("COMENI_AI_MODEL_TALK", "ollama_chat/gemma3:4b")
    got = model_access("builder", "chat")
    assert (got.model, got.base_url) == ("ollama_chat/gemma3:4b", "http://ollama:11434")


def test_a_purpose_naming_a_gone_connection_falls_back(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/qwen2.5:7b", talk="ollama_chat/gemma3:4b")
    settings_in_memory.rows["models.talk"] = {"connection": "Gone", "model": "x"}
    assert model_access("builder", "ask").model == "ollama_chat/qwen2.5:7b"


def test_the_builder_client_is_built_for_its_purpose(clean_env, settings_in_memory):
    from mendel_api.services import authoring_jobs

    _choose(settings_in_memory, default="ollama_chat/gemma3:12b", readback="ollama_chat/gemma3:4b")
    assert authoring_jobs._client(authoring_ai.Purpose.READBACK).access.model == "ollama_chat/gemma3:4b"


def test_where_each_purpose_goes(clean_env, settings_in_memory):
    _choose(settings_in_memory, default="ollama_chat/gemma3:12b")
    settings_in_memory.rows["models.connections"].append(
        {"name": "Anthropic", "server": "hosted", "endpoint": "", "key": None}
    )
    settings_in_memory.rows["models.tier4"] = {
        "connection": "Anthropic", "model": "anthropic/claude-sonnet-4-5",
    }
    rows = {r["purpose"]: r for r in where_purposes(installation.installation())}
    assert rows["Talking with you"]["goes"] == "stays on this machine or your network"
    assert rows["Choosing where the rules cannot"]["goes"] == "goes to anthropic"
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_models_per_purpose.py -q`
Expected: FAIL, `No module named 'mendel_api.services.models'`

- [ ] **Step 4: Write `services/models.py`**

```python
"""Which model answers each call (spec §6).

**Every call names its purpose**, and `PURPOSES` maps it to a setting in Settings → Models. The
fallback is the purpose's own model, then the default, then the environment as it was read
before settings existed — so an installation configured only by `.env`, including the
deprecated `MENDEL_*` names, behaves exactly as it did.

**Invariant 13:** a connection becomes a `ModelAccess` the same way whatever its server is. Only
`where_purposes`, a report for a person, reads the server kind.
"""

import os
from collections.abc import Mapping

from comeni_ai import ModelAccess
from comeni_ai.access import MODEL
from comeni_core.settings import FROM_ENV, Installation, Setting
from comeni_core.settings import catalogue as c

PURPOSES: dict[tuple[str, str], Setting] = {
    ("builder", "goal"): c.MODEL_WANT,
    ("builder", "family"): c.MODEL_WANT,
    ("builder", "chat"): c.MODEL_TALK,
    ("builder", "gap"): c.MODEL_TALK,
    ("builder", "ask"): c.MODEL_TALK,
    ("builder", "tier4"): c.MODEL_TIER4,
    ("builder", "readback"): c.MODEL_READBACK,
    ("forge", "analysis"): c.MODEL_FORGE,
    ("forge", "implementation"): c.MODEL_FORGE,
    ("forge", "repair"): c.MODEL_FORGE,
    ("forge", "chat"): c.MODEL_FORGE,
}


def _access(inst: Installation, choice: dict, env: Mapping[str, str]) -> ModelAccess | None:
    record = inst.record(c.CONNECTIONS, choice["connection"])
    if record is None:
        return None
    # `from_env` with the chosen model reads the timeout and temperature the same way the
    # environment lane always has; the connection then supplies where and with what key.
    base = ModelAccess.from_env({**env, MODEL: choice["model"]})
    assert base is not None
    if choice["connection"] == FROM_ENV:
        return base
    return base.model_copy(
        update={"api_key": record.get("key") or None, "base_url": record.get("endpoint") or None}
    )


def access_for(
    inst: Installation, env: Mapping[str, str], agent: str | None = None, purpose: str | None = None
) -> ModelAccess | None:
    if agent is None:
        order = [c.DEFAULT_MODEL, *c.PURPOSE_SETTINGS]
    else:
        order = [PURPOSES[(agent, str(purpose))], c.DEFAULT_MODEL] if purpose else [c.DEFAULT_MODEL]
    for setting in order:
        choice = inst.get(setting)
        if isinstance(choice, dict):
            found = _access(inst, choice, env)
            if found is not None:
                return found
    return ModelAccess.from_env(env)


def _goes(record: dict | None, model: str) -> str:
    if record is None:
        return "no model: nothing is sent"
    server = record.get("server")
    if server == "hosted" or (server is None and not record.get("endpoint")):
        return f"goes to {model.split('/', 1)[0]}"
    return "stays on this machine or your network"


def where_purposes(inst: Installation) -> list[dict]:
    rows = []
    default = inst.get(c.DEFAULT_MODEL)
    for setting in c.PURPOSE_SETTINGS:
        choice = inst.get(setting) or default
        record = inst.record(c.CONNECTIONS, choice["connection"]) if choice else None
        rows.append({
            "purpose": setting.label,
            "connection": choice["connection"] if choice else None,
            "goes": _goes(record, choice["model"] if choice else ""),
        })
    return rows
```

- [ ] **Step 5: `model_access` takes the purpose**

Replace `model_access` in `mendel_api/settings.py` (keep its docstring's three paragraphs and add one):

```python
def model_access(agent: str | None = None, purpose: str | None = None) -> "ModelAccess | None":
    """How to reach the model for one call, or `None` when none is configured.

    ... (the existing three paragraphs stay) ...

    **Per purpose since 14.7.5.4.** `agent` and `purpose` name the call (`"builder"`, `"ask"`)
    and Settings → Models says which model answers it; with neither, the question is *is any
    model configured*. `services/models.py` holds the map and the fallback order.
    """
    from mendel_api.services.installation import installation
    from mendel_api.services.models import access_for

    return access_for(installation(), os.environ, agent, purpose)
```

- [ ] **Step 6: Pass the purpose at every call site**

- `authoring_jobs.py`: `def _client(purpose: Purpose) -> Client | None:` with `access = model_access("builder", purpose)`; import `Purpose` from `authoring_ai`. Each call passes the purpose of the function it feeds — `choose_families` → `Purpose.FAMILY`; `understand` → `Purpose.GOAL`; `read_back` → `Purpose.READBACK`; `phrase_gap` → the purpose `phrase_gap` records (read it in `authoring_ai.py`; `Purpose.GAP` at the time of writing); `read_gap_reply` → the purpose it records (`Purpose.ASK` at the time of writing); `follow_up` → `Purpose.CHAT`; `start_building` → `Purpose.TIER4`.
- `authoring_ai._call`: `access = model_access("builder", purpose)`.
- `forge_jobs._client` and `_model_id`: `model_access("forge", InvocationPurpose.ANALYSIS)`. All forge purposes map to one setting, so the purpose named here only has to be a forge one.
- The *is anything configured* checks (`routes/authoring.py:550`, `services/authoring.py:1310`, `:1630`, `forge_jobs.py:925`, `routes/health.py:210`) stay `model_access()`. `test_forge_jobs.py`'s AST guard looks for that name in the `if`.

Run: `grep -n "_client()" packages/mendel-api/src/mendel_api/services/authoring_jobs.py`
Expected: nothing (every call now names its purpose).

- [ ] **Step 7: Run the tests, then the whole package**

Run: `uv run pytest packages/mendel-api/tests/test_models_per_purpose.py -q`
Expected: PASS, 11 passed

Run: `MENDEL_DATABASE_URL=$DB uv run pytest packages/mendel-api -q 2>&1 | tail -3`
Expected: PASS. A test that fails because it monkeypatched `authoring_jobs._client` with a zero-argument lambda gets `lambda *_: …`; record each as a ruling.

- [ ] **Step 8: Commit**

```bash
git add packages/mendel-api/ pyproject.toml
git commit -m "feat(settings): every AI call uses its purpose's model, .env unchanged (#214)"
```

---

### Task 5: Test and list models — one generic route for record actions

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/probe.py` (move `_model_answers` and `PROBE_SECONDS` from `routes/health.py`)
- Modify: `packages/mendel-api/src/mendel_api/routes/health.py` (import from `probe`)
- Create: `packages/mendel-api/src/mendel_api/services/settings_actions.py`
- Modify: `packages/mendel-api/src/mendel_api/routes/settings.py`
- Modify: `packages/mendel-api/tests/test_openapi.py`
- Test: `packages/mendel-api/tests/test_settings_actions.py`

**Interfaces:**
- Produces: `probe.answers(base_url: str) -> bool` (async); `probe.listed(endpoint: str, server: str | None) -> list[str]` (async, raises `ProbeFailed`); `ActionResult(ok: bool | None, says: str, values: list[str] = [])`; `ACTIONS: dict[tuple[str, str], Callable[[dict], Awaitable[ActionResult]]]`; `POST /api/settings/{key}/items/{name}/{action}` → `ActionResult` (operation `runSettingAction`; 404 for an unknown setting, record or action).

Model ids carry LiteLLM's prefix for the server: `ollama` → `ollama_chat/<id>` (the chat endpoint; issue 179), `openai_compatible` → `openai/<id>`, `hosted` → nothing listed (the person types `provider/model`).

- [ ] **Step 1: Write the failing tests**

```python
"""Record actions: test a connection, list its models (spec §6)."""

import httpx
import pytest
from fastapi.testclient import TestClient

from mendel_api.main import create_app
from mendel_api.services import probe


@pytest.fixture
def client(settings_in_memory):
    settings_in_memory.rows["models.connections"] = [
        {"name": "Local", "server": "ollama", "endpoint": "http://ollama:11434", "key": None},
        {"name": "Cloud", "server": "hosted", "endpoint": "", "key": None},
    ]
    return TestClient(create_app())


def test_test_reports_a_listening_endpoint(client, monkeypatch):
    async def listening(base_url):
        return base_url == "http://ollama:11434"

    monkeypatch.setattr(probe, "answers", listening)
    body = client.post("/api/settings/models.connections/items/Local/test").json()
    assert body["ok"] is True and "answer" in body["says"]


def test_a_hosted_provider_is_not_probed(client):
    body = client.post("/api/settings/models.connections/items/Cloud/test").json()
    assert body["ok"] is None and "not probed" in body["says"]


def test_models_are_listed_with_the_prefix_their_server_needs(client, monkeypatch):
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "qwen2.5:7b"}, {"id": "gemma3:4b"}]})

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    body = client.post("/api/settings/models.connections/items/Local/models").json()
    assert body["values"] == ["ollama_chat/gemma3:4b", "ollama_chat/qwen2.5:7b"]


def test_an_endpoint_that_hangs_answers_not_ok(client, monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(probe, "TRANSPORT", httpx.MockTransport(handler))
    body = client.post("/api/settings/models.connections/items/Local/models").json()
    assert body["ok"] is False and body["values"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/api/settings/models.nothing/items/Local/test",
        "/api/settings/models.connections/items/Nowhere/test",
        "/api/settings/models.connections/items/Local/explode",
    ],
)
def test_unknown_setting_record_or_action_is_404(client, path):
    assert client.post(path).status_code == 404
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/mendel-api/tests/test_settings_actions.py -q`
Expected: FAIL, `cannot import name 'probe'`

- [ ] **Step 3: Write `probe.py`** (move `_model_answers` and `PROBE_SECONDS` verbatim from `routes/health.py` as `answers`; then add)

```python
TRANSPORT: httpx.AsyncBaseTransport | None = None
"""A seam for tests: `httpx.MockTransport`. `None` is the real network."""

PREFIX = {"ollama": "ollama_chat/", "openai_compatible": "openai/"}
"""LiteLLM's prefix per server. `ollama_chat/`, not `ollama/`: issue 179."""


class ProbeFailed(Exception):
    pass


async def listed(endpoint: str, server: str | None) -> list[str]:
    """`GET <endpoint>/v1/models`. **No prompt is sent**: this asks what a server holds."""
    try:
        async with httpx.AsyncClient(timeout=PROBE_SECONDS, transport=TRANSPORT) as http:
            answer = await http.get(endpoint.rstrip("/") + "/v1/models")
            answer.raise_for_status()
            ids = [item["id"] for item in answer.json()["data"]]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as failed:
        raise ProbeFailed(type(failed).__name__) from None
    prefix = PREFIX.get(server or "", "")
    return sorted(prefix + i for i in ids)
```

In `routes/health.py`, delete the moved function and constant and `from mendel_api.services.probe import PROBE_SECONDS, answers`; replace `_model_answers(` with `answers(`. Run `uv run pytest packages/mendel-api/tests/test_ai_health.py packages/mendel-api/tests/test_health.py -q` → PASS (if a test monkeypatches `health._model_answers`, point it at `probe.answers` and record it).

- [ ] **Step 4: Write `settings_actions.py`**

```python
"""What a record can be asked to do (spec §6). One map, one generic route.

**Adding an action is one entry here** and its name in the setting's `actions`; the menu draws a
button for each name it is served.
"""

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from mendel_api.services import probe


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool | None
    """`None`: not asked, on purpose — a hosted provider is never probed."""
    says: str
    values: list[str] = []


async def _test(record: dict) -> ActionResult:
    endpoint = record.get("endpoint")
    if not endpoint:
        return ActionResult(
            ok=None, says="A hosted provider is not probed: asking costs a call."
        )
    if await probe.answers(endpoint):
        return ActionResult(ok=True, says=f"Something answers at {endpoint}.")
    return ActionResult(ok=False, says=f"Nothing answered at {endpoint} within a few seconds.")


async def _models(record: dict) -> ActionResult:
    endpoint = record.get("endpoint")
    if not endpoint:
        return ActionResult(ok=None, says="Type the model id, as provider/model.")
    try:
        values = await probe.listed(endpoint, record.get("server"))
    except probe.ProbeFailed as failed:
        return ActionResult(ok=False, says=f"Could not list models at {endpoint} ({failed}).")
    return ActionResult(ok=True, says=f"{len(values)} models at {endpoint}.", values=values)


ACTIONS: dict[tuple[str, str], Callable[[dict], Awaitable[ActionResult]]] = {
    ("models.connections", "test"): _test,
    ("models.connections", "models"): _models,
}
```

- [ ] **Step 5: The route** — append to `routes/settings.py`

```python
@router.post(
    "/{key}/items/{name}/{action}",
    operation_id="runSettingAction",
    summary="Ask one record of a setting to do something: test a connection, list its models",
    responses=REFUSES,
)
async def run_setting_action(
    key: str, name: str, action: str, inst: Annotated[Installation, Depends(installation)]
) -> ActionResult:
    setting = inst.catalogue.setting(key)
    if action not in setting.actions or (key, action) not in ACTIONS:
        raise KeyError(f"{key} has no action {action}")
    record = inst.record(setting, name)
    if record is None:
        raise KeyError(f"{key} has no record {name}")
    return await ACTIONS[(key, action)](record)
```

Import `ActionResult`, `ACTIONS` from `mendel_api.services.settings_actions`. Add to `test_openapi.py`'s dict: `("/api/settings/{key}/items/{name}/{action}", "post"): "runSettingAction",`.

- [ ] **Step 6: Run them to verify they pass**

Run: `uv run pytest packages/mendel-api/tests/test_settings_actions.py packages/mendel-api/tests/test_openapi.py -q`
Expected: PASS

- [ ] **Step 7: Regenerate the client and commit**

Run: `make client && cd frontend && npx tsc -b`
Expected: `schema.d.ts` gains `runSettingAction` and `ActionResult`; no type errors.

```bash
git add packages/mendel-api/ frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "feat(settings): test a connection and list its models — one route for record actions (#214)"
```

---

### Task 6: The frontend — connections, the model picker, and reports

**Files:**
- Create: `frontend/src/preferences/useAction.ts`
- Create: `frontend/src/preferences/Collection.tsx`
- Create: `frontend/src/preferences/ModelPicker.tsx`
- Create: `frontend/src/preferences/Report.tsx`
- Modify: `frontend/src/preferences/SettingRow.tsx` (`Control` gains three cases; a reason on an unlocked row reads *Needs attention*)
- Modify: `frontend/src/preferences/Help.tsx` (`heading` prop)
- Modify: `frontend/src/preferences/Preferences.tsx` (pass the whole menu to rows that need it)
- Test: `frontend/src/preferences/Collection.test.tsx`, `ModelPicker.test.tsx`, `Report.test.tsx`

**Interfaces:**
- Consumes: `Entry`, `Menu`, `useMenu` (part 3); `post` (`api/client`); `components["schemas"]["ActionResult"]`.
- Produces: `useAction(key, name, action)` (a mutation returning `ActionResult`); `Collection({ entry, onWrite })`; `ModelPicker({ entry, menu, onWrite })`; `Report({ value })`; `SettingRow` gains an optional `menu?: Menu` prop.

- [ ] **Step 1: Write the failing tests**

`Collection.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Collection } from "./Collection";
import type { Entry } from "./usePreferences";

const HELP = "Where models are reached, from this machine or a provider.";
const field = (key: string, kind: string, extra = {}) => ({
  key, label: key.split(".")[1], help: HELP, kind, default: kind === "secret" ? null : "",
  env: null, options: [], minimum: null, maximum: null, unavailable: null, where: "installation",
  fields: [], item_name: "name", from_env: null, actions: [], of: null, ...extra,
});
const ENTRY = {
  setting: {
    ...field("models.connections", "collection", { default: [] }),
    label: "Connections", actions: ["test", "models"],
    fields: [field("connection.name", "text"), field("connection.endpoint", "text"), field("connection.key", "secret")],
  },
  shown: {
    value: [
      { name: "From .env", endpoint: "http://ollama:11434", key: { set: false, last4: null }, locked: true },
      { name: "Cloud", endpoint: "", key: { set: true, last4: "1234" } },
    ],
    source: "installation", locked: false, reason: null, set: null, last4: null,
  },
} as unknown as Entry;

function draw(onWrite = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Collection entry={ENTRY} onWrite={onWrite} />
    </QueryClientProvider>,
  );
  return onWrite;
}

afterEach(() => vi.unstubAllGlobals());

describe("connections", () => {
  it("shows each record, the env one locked", () => {
    draw();
    expect(screen.getByText("From .env")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Remove/ })).toHaveLength(1);
    expect(screen.getByText(/ending 1234/)).toBeTruthy();
  });

  it("adds a record and saves the list without the env record and without retyping keys", async () => {
    const onWrite = draw();
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await userEvent.type(screen.getByLabelText("name", { selector: "#new-name" }), "Local");
    await userEvent.type(screen.getByLabelText("endpoint", { selector: "#new-endpoint" }), "http://o:11434");
    await userEvent.click(screen.getByRole("button", { name: "Save connections" }));
    expect(onWrite).toHaveBeenCalledWith([
      { name: "Cloud", endpoint: "", key: null },
      { name: "Local", endpoint: "http://o:11434", key: null },
    ]);
  });

  it("runs an action and shows what it said", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ ok: true, says: "Something answers at http://ollama:11434.", values: [] }),
    }));
    draw();
    await userEvent.click(screen.getAllByRole("button", { name: "test" })[0]);
    expect(await screen.findByText(/Something answers/)).toBeTruthy();
  });
});
```

`ModelPicker.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelPicker } from "./ModelPicker";
import type { Entry, Menu } from "./usePreferences";

const HELP = "Phrases the questions the build asks you and reads your replies.";
const MENU = {
  sections: [{ key: "models", title: "Models", order: 3, served_by: "mendel", entries: [{
    setting: { key: "models.connections", kind: "collection", label: "Connections", help: HELP },
    shown: { value: [{ name: "Local", server: "ollama", endpoint: "http://o:11434", key: { set: false, last4: null } }],
             source: "installation", locked: false, reason: null },
  }] }],
} as unknown as Menu;
const ENTRY = {
  setting: { key: "models.talk", label: "Talking with you", help: HELP, kind: "model", of: "models.connections", default: null },
  shown: { value: null, source: "default", locked: false, reason: null },
} as unknown as Entry;

afterEach(() => vi.unstubAllGlobals());

describe("the model picker", () => {
  it("offers the default and every listed model, and writes a choice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ ok: true, says: "2 models", values: ["ollama_chat/gemma3:4b", "ollama_chat/qwen2.5:7b"] }),
    }));
    const onWrite = vi.fn();
    render(<QueryClientProvider client={new QueryClient()}>
      <ModelPicker entry={ENTRY} menu={MENU} onWrite={onWrite} />
    </QueryClientProvider>);
    const select = screen.getByRole("combobox", { name: "Talking with you" });
    await waitFor(() => expect(screen.getByRole("option", { name: "Local · ollama_chat/gemma3:4b" })).toBeTruthy());
    expect(screen.getByRole("option", { name: "Same as the default" })).toBeTruthy();
    await userEvent.selectOptions(select, "Local · ollama_chat/gemma3:4b");
    expect(onWrite).toHaveBeenCalledWith({ connection: "Local", model: "ollama_chat/gemma3:4b" });
  });
});
```

`Report.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Report } from "./Report";

describe("a report", () => {
  it("draws a list of records as a table", () => {
    render(<Report value={[{ purpose: "Talking with you", goes: "stays on this machine or your network" }]} />);
    expect(screen.getByRole("columnheader", { name: "purpose" })).toBeTruthy();
    expect(screen.getByRole("cell", { name: "Talking with you" })).toBeTruthy();
  });

  it("draws anything else as text", () => {
    render(<Report value="0.1.0" />);
    expect(screen.getByText("0.1.0")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/preferences/Collection.test.tsx src/preferences/ModelPicker.test.tsx src/preferences/Report.test.tsx`
Expected: FAIL, cannot resolve the three modules

- [ ] **Step 3: Write `useAction.ts` and `Report.tsx`**

```ts
import { useMutation } from "@tanstack/react-query";

import { post } from "../api/client";
import type { components } from "../api/schema";

export type ActionResult = components["schemas"]["ActionResult"];

const at = (key: string, name: string, action: string) =>
  `/settings/${encodeURIComponent(key)}/items/${encodeURIComponent(name)}/${action}`;

export function useAction(key: string, name: string, action: string) {
  return useMutation({ mutationFn: () => post<ActionResult>(at(key, name, action), {}) });
}

export function listModels(key: string, name: string) {
  return post<ActionResult>(at(key, name, "models"), {});
}
```

```tsx
/** A value the server reports (spec §6, §7). A list of records is a table, with the records'
 *  own keys as headers; anything else is text. Knows no particular report. */
export function Report({ value }: { value: unknown }) {
  if (Array.isArray(value) && value.length && value.every((r) => r && typeof r === "object")) {
    const rows = value as Record<string, unknown>[];
    const columns = Object.keys(rows[0]);
    return (
      <table className="text-secondary border-collapse">
        <thead>
          <tr>{columns.map((c) => <th key={c} className="text-left text-ink-3 pr-4 font-normal">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>{columns.map((c) => <td key={c} className="pr-4 text-ink">{String(row[c] ?? "—")}</td>)}</tr>
          ))}
        </tbody>
      </table>
    );
  }
  return <span className="font-data text-secondary text-ink-2">{value == null ? "—" : String(value)}</span>;
}
```

- [ ] **Step 4: Write `Collection.tsx`**

```tsx
import { useState } from "react";

import { useAction } from "./useAction";
import type { Entry } from "./usePreferences";

/** A list of records — connections today (spec §6). **Generic**: the fields come from the
 * declaration and the buttons from its `actions`. A locked record (from .env) is shown and never
 * sent back. A secret field is sent as `null`, which keeps what is stored, unless retyped. */
type Record = { [field: string]: unknown; locked?: boolean };
type Field = { key: string; label: string; kind: string };

const nameOf = (field: Field) => field.key.split(".").pop() as string;

export function Collection({ entry, onWrite }: { entry: Entry; onWrite: (value: unknown) => void }) {
  const setting = entry.setting as unknown as { key: string; fields: Field[]; item_name: string; actions: string[] };
  const records = (entry.shown.value as Record[] | null) ?? [];
  const [added, setAdded] = useState<Record | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [typed, setTyped] = useState<{ [name: string]: { [field: string]: string } }>({});

  const kept = records.filter((r) => !r.locked && !removed.includes(String(r[setting.item_name])));
  const plain = (record: Record) =>
    Object.fromEntries(setting.fields.map((f) => {
      const name = nameOf(f);
      const retyped = typed[String(record[setting.item_name])]?.[name];
      if (f.kind === "secret") return [name, retyped ?? null];
      return [name, retyped ?? record[name] ?? ""];
    }));
  const save = () => onWrite([...kept.map(plain), ...(added ? [plain(added)] : [])]);

  return (
    <div className="flex flex-col gap-3">
      {records.filter((r) => !removed.includes(String(r[setting.item_name]))).map((record) => (
        <Card key={String(record[setting.item_name])} setting={setting} record={record}
              onRemove={() => setRemoved([...removed, String(record[setting.item_name])])}
              onType={(field, v) => setTyped({ ...typed, [String(record[setting.item_name])]: { ...typed[String(record[setting.item_name])], [field]: v } })} />
      ))}
      {added && (
        <div className="border border-line p-3 flex flex-col gap-2">
          {setting.fields.map((f) => (
            <label key={f.key} className="flex gap-2 items-center text-secondary text-ink-2">
              <span className="w-[90px]">{nameOf(f)}</span>
              <input id={`new-${nameOf(f)}`} aria-label={nameOf(f)}
                     type={f.kind === "secret" ? "password" : "text"}
                     onChange={(e) => setAdded({ ...added, [nameOf(f)]: e.target.value })}
                     className="border border-line bg-transparent px-2 py-1 text-ink w-[260px] max-w-full" />
            </label>
          ))}
        </div>
      )}
      <div className="flex gap-3">
        <button type="button" onClick={() => setAdded({})} disabled={added !== null}
                className="bg-transparent text-link cursor-pointer text-secondary">Add</button>
        <button type="button" onClick={save}
                className="bg-transparent text-link cursor-pointer text-secondary">Save connections</button>
      </div>
    </div>
  );
}

function Card({ setting, record, onRemove, onType }: {
  setting: { key: string; fields: Field[]; item_name: string; actions: string[] };
  record: Record; onRemove: () => void; onType: (field: string, value: string) => void;
}) {
  const name = String(record[setting.item_name]);
  return (
    <div className="border border-line p-3">
      <div className="flex items-baseline gap-2">
        <span className="text-body text-ink">{name}</span>
        {record.locked && <span aria-label="Locked" title="Pinned by .env">🔒</span>}
        <span className="ml-auto flex gap-3">
          {setting.actions.map((a) => <Action key={a} setting={setting.key} name={name} action={a} />)}
          {!record.locked && (
            <button type="button" aria-label={`Remove ${name}`} onClick={onRemove}
                    className="bg-transparent text-ink-3 hover:text-fault cursor-pointer text-secondary">Remove</button>
          )}
        </span>
      </div>
      {setting.fields.filter((f) => nameOf(f) !== setting.item_name).map((f) => {
        const value = record[nameOf(f)];
        if (f.kind === "secret") {
          const mask = value as { set: boolean; last4: string | null } | null;
          return (
            <div key={f.key} className="text-secondary text-ink-2 mt-1">
              {nameOf(f)}: {mask?.set ? `set, ending ${mask.last4}` : "not set"}
              {!record.locked && (
                <input aria-label={`${name} ${nameOf(f)}`} type="password" placeholder="replace"
                       onChange={(e) => onType(nameOf(f), e.target.value)}
                       className="ml-2 border border-line bg-transparent px-2 py-0.5 text-ink w-[180px]" />
              )}
            </div>
          );
        }
        return <div key={f.key} className="text-secondary text-ink-2 mt-1">{nameOf(f)}: {String(value ?? "") || "—"}</div>;
      })}
    </div>
  );
}

function Action({ setting, name, action }: { setting: string; name: string; action: string }) {
  const run = useAction(setting, name, action);
  return (
    <span className="text-secondary">
      <button type="button" onClick={() => run.mutate()} className="bg-transparent text-link cursor-pointer">{action}</button>
      {run.data && <span className={`ml-2 ${run.data.ok === false ? "text-fault" : "text-ink-2"}`}>{run.data.says}</span>}
    </span>
  );
}
```

- [ ] **Step 5: Write `ModelPicker.tsx`**

```tsx
import { useQueries } from "@tanstack/react-query";
import { useState } from "react";

import { listModels } from "./useAction";
import type { Entry, Menu } from "./usePreferences";

/** A model for one purpose (spec §6): *same as the default*, a model listed by any connection,
 * or *Other…*, a typed `provider/model` on a chosen connection — for a hosted provider, which
 * lists nothing. */
type Choice = { connection: string; model: string } | null;

export function ModelPicker({ entry, menu, onWrite }: { entry: Entry; menu: Menu; onWrite: (v: Choice) => void }) {
  const of = (entry.setting as unknown as { of: string }).of;
  const records = (menu.sections.flatMap((s) => s.entries).find((e) => e.setting.key === of)
    ?.shown.value as { name: string }[] | null) ?? [];
  const lists = useQueries({
    queries: records.map((r) => ({
      queryKey: ["models", of, r.name],
      queryFn: () => listModels(of, r.name),
      staleTime: 60_000,
    })),
  });
  const current = entry.shown.value as Choice;
  const [other, setOther] = useState<{ connection: string; model: string } | null>(null);
  const encode = (c: Choice) => (c ? `${c.connection}\u0000${c.model}` : "");
  const options = records.flatMap((r, i) =>
    (lists[i].data?.values ?? []).map((model) => ({ connection: r.name, model })));
  const known = current && options.some((o) => encode(o) === encode(current));

  return (
    <span className="flex flex-wrap items-center gap-2">
      <select
        aria-label={entry.setting.label}
        disabled={entry.shown.locked}
        value={other ? "\u0001" : encode(current)}
        onChange={(event) => {
          const v = event.target.value;
          if (v === "\u0001") return setOther({ connection: records[0]?.name ?? "", model: "" });
          setOther(null);
          onWrite(v ? { connection: v.split("\u0000")[0], model: v.split("\u0000")[1] } : null);
        }}
        className="border border-line bg-transparent px-2 py-1 text-secondary text-ink max-w-full"
      >
        <option value="">Same as the default</option>
        {current && !known && <option value={encode(current)}>{current.connection} · {current.model}</option>}
        {options.map((o) => <option key={encode(o)} value={encode(o)}>{o.connection} · {o.model}</option>)}
        <option value={"\u0001"}>Other…</option>
      </select>
      {other && (
        <>
          <select aria-label="Connection" value={other.connection}
                  onChange={(e) => setOther({ ...other, connection: e.target.value })}
                  className="border border-line bg-transparent px-2 py-1 text-secondary text-ink">
            {records.map((r) => <option key={r.name}>{r.name}</option>)}
          </select>
          <input aria-label="Model id" placeholder="provider/model" value={other.model}
                 onChange={(e) => setOther({ ...other, model: e.target.value })}
                 className="border border-line bg-transparent px-2 py-1 text-secondary text-ink w-[240px]" />
          <button type="button" disabled={!other.model.includes("/")}
                  onClick={() => { onWrite(other); setOther(null); }}
                  className="bg-transparent text-link cursor-pointer text-secondary">Use</button>
        </>
      )}
    </span>
  );
}
```

- [ ] **Step 6: Wire them into the row and the page**

In `SettingRow.tsx`'s `Control`, add before `default:`:

```tsx
    case "collection":
      return <Collection entry={entry} onWrite={onWrite} />;
    case "model":
      return menu ? <ModelPicker entry={entry} menu={menu} onWrite={onWrite} /> : null;
    case "readonly":
      return <Report value={value} />;
```

Thread an optional `menu?: Menu` through `Props`, `Row` and `Control`. In `Row`, pass `heading={shown.locked ? "Why it is greyed out" : "Needs attention"}` to `Help`; in `Help.tsx` add `heading = "Why it is greyed out"` to the props and render `<strong>{heading}:</strong>`. In `Preferences.tsx`, pass `menu={menu.data}` to each `SettingRow`.

- [ ] **Step 7: Run the frontend suite and the type check**

Run: `cd frontend && npx vitest run src/preferences && npx vitest run && npx tsc -b`
Expected: PASS; no type errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/preferences/
git commit -m "feat(settings): connections, the model picker and reports in the menu (#214)"
```

---

### Task 7: Walk it

- [ ] **Step 1: Set a settings key and bring the stack up**

Ask the operator before touching `.env`: it is theirs. With their OK they add `COMENI_SETTINGS_KEY=<generated>`. Then `make dev`, `make migrate`. The `ai-worker` is baked: rebuild it (`docker compose build ai-worker && docker compose up -d ai-worker`).

- [ ] **Step 2: Drive it**

In Settings → Models: the *From .env* connection is listed, locked, with the operator's model as the default. Add *Local Ollama* at `http://ollama:11434` (the compose hostname), press *test* (expect *Something answers*), then *models* (expect `ollama_chat/gemma3:4b`, `ollama_chat/qwen2.5:7b`, `ollama_chat/gemma3:12b`). Choose `gemma3:4b` for *Talking with you*. Privacy & data → *Where each purpose goes* says every purpose stays on this machine.

- [ ] **Step 3: Check a call used it**

Start a builder session and answer one question. Then read the last invocations (`docker compose exec postgres psql -U mendel -c "select purpose, model from ai_invocation order by started_at desc limit 5"`; check the column name in `models.py` first).
Expected: `ask` or `gap` rows with `ollama_chat/gemma3:4b`; `goal` or `family` with the default.

- [ ] **Step 4: Show the operator, and close**

Screenshots of Models and Privacy at 1280px and 390px. Findings become issues under #210 unless they block. Run the checks separately, comment on #214 with the commits, and close it.

---

## Execution record

(Filled in while executing.)
