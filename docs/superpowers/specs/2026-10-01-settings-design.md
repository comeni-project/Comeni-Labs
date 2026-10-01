# Settings — design

**Issue:** #181 (step 14.7.5, under #126). Holds #117 (pacing) and #187 (which models fit).
**Decided** by the operator on 2026-10-01, in the brainstorm this spec records: general settings,
not only AI ones; per installation now, per person when sign-in arrives; layers with the
environment as a lock; a (?) on every setting that says what it is and why it is greyed out;
one declaration per setting; connections and a model per purpose, now.

Built in seven parts, 14.7.5.1–14.7.5.7 (§10). Each part gets its own plan.

## 1. What a person gets

A **settings menu**, behind a gear at the right of the top bar, at `/settings/<section>`. Every
setting shows its value, **where that value came from**, and a ⓘ that says what it is and, when the
setting is greyed out, why. Changing a setting takes effect on the next use, with no restart.
`.env` stays the operator's last word: a value pinned there is shown, greyed, and says so.

## 2. Per installation, per person later

Every setting is per installation. There are no accounts (`mendel_api/identity.py` is
attribution, not security), so a per-person value has nothing to attach to yet. The layering
(§3) leaves room for a person layer, and for a lab layer on the hosted service, without a rewrite.

## 3. Where a value comes from: layers, with the environment as a lock

Each setting looks its value up through layers. The strongest one that has a value wins:

| Layer | What it is | Built |
|---|---|---|
| default | the value in the declaration | now |
| installation | what someone chose in the menu, stored in Mendel's Postgres | now |
| lab | a lab's own choice, when one server hosts several | later |
| person | a person's own choice, after sign-in (#83) | later |
| **environment (lock)** | a value in `.env`; beats every layer and greys the field out | now |

Every resolved value carries its **source** (`default`, `installation`, `environment`) and
whether it is **locked**. This is the shape the registry already has: a stack of layers that
records which one supplied a value.

**Why the environment locks rather than seeds.** A seed (Open WebUI's *PersistentConfig*) makes
the database win after the first boot, so an edited `.env` silently does nothing. A lock keeps
the deploy files the truth, which compose, Helm and GitOps need, and it is also the shape a
*policy* needs: the protection level is a value a lab sets and a person must not loosen.

**An empty string is not a value,** in the environment as in `comeni_ai.access`: `X=` exported
empty means unset.

**What a setting may never do: change the pipeline.** *Same goal in → same pipeline out.*
Anything that shapes what is built belongs in the goal or `pipeline.yml`. Settings change how the
build talks to a person (pacing), which model answers (already recorded per call in
`ai_invocation`), and where and how a run executes.

## 4. One declaration per setting

A setting is declared once, in Python, in a pure module `comeni_core/settings/`. Everything else
is generic:

```python
PACING = Setting.choice(
    key="building.pacing",
    label="Pacing",
    help="How the build walks you through its steps. ...",
    options=[("together", "Go through it together"),
             ("stop_where_needed", "Set it up, stop only where you need me"),
             ("ask", "Ask me every time")],
    default="ask",
    env="COMENI_BUILD_PACING",
)
```

- **Kinds**, each a factory: `choice`, `text`, `number`, `toggle`, `secret`, `model` (a model for
  one purpose, §6), `collection` (a list of records, used for connections, §6) and `readonly` (a
  value reported, never stored).
- **Sections** are declared the same way: key, title, order, settings. The menu draws itself
  from them.
- **One resolver** takes a declaration and returns `{value, source, locked, reason}`. The store
  it reads is a `Protocol`, so `comeni_core` never touches a database (invariant 1).
- **Code that uses a setting asks by its declaration**, `settings.get(PACING)`, never by a string
  key, so a typo fails a type check rather than a request.
- **Adding a setting is three steps:** declare it, add it to a section, read it where it is used.
  No endpoint, no component and no migration.

## 5. The ⓘ: what it is, and why it is greyed out

Next to every label, an **ⓘ that opens a small popover on click, tap or Enter**, and closes on
Escape. A hover-only tooltip is not used: touch screens have no hover and keyboard users cannot
reach it. The popover says:

1. **What it is:** one or two plain sentences, and what changes when it changes. From the
   declaration's `help`.
2. **Why it is greyed out**, only when it is. A greyed field also shows a small lock or *not built*
   mark beside the label. The reason is from a **closed list**:

| Reason | Says |
|---|---|
| `Pinned(env)` | pinned by `.env`, naming the variable; change it there and restart |
| `Designed(where)` | designed, not built; one line on where it is coming |
| `Needs(what)` | needs something first, e.g. *choose a connection first* |
| `ReadOnlyHere(why)` | reported here, set elsewhere, e.g. *Wiener reads this from its own `.env`* |

A greyed field without a reason cannot be declared. A new kind of reason is a change to this list.

## 6. Models: connections, and a model per purpose

**Connections** are a `collection` setting. Each has a name, a lane (self-hosted or hosted), an
endpoint, a key (a `secret`) and a **Test** button, e.g. *Local Ollama* at
`http://ollama:11434`, *Anthropic* with a key. No connection is the no-AI lane, as today.

**A model per purpose.** One dropdown per purpose, listing every model on every connection
(*Local Ollama · gemma3:4b*). Choosing a model chooses its connection. Each purpose may say
*same as default*. The menu's purposes group the calls by what they do for a person: the
**default**, **understanding what you want**, **talking with you** (phrasing a question, reading a
reply), **tier 4**, **read-back**, and **the forge**. Each call already records a `Purpose`
(`mendel_api/services/authoring_ai.py`) or an `InvocationPurpose` (`mendel_forge/workflow.py`);
the plan maps every member to exactly one menu purpose, and a test fails on an unmapped member.

**Model lists** come from `/v1/models` where the endpoint has one (Ollama and OpenAI-compatible
servers do). A hosted provider without it gets a text field checked for the `provider/model` form,
as `MA0007` already checks.

**`model_access()` becomes `model_access(purpose)`**, returning the `ModelAccess` for that
purpose's connection and model. The calls do not change otherwise.

**`.env` keeps working.** `COMENI_AI_MODEL`, `_BASE_URL` and `_API_KEY` appear as a connection
named *From `.env`*, locked, and its model is the default model. `COMENI_AI_MODEL_<PURPOSE>` pins
one purpose. So the operator's existing `.env` locks the default model only, and a purpose can
still be set in the menu.

**Where each purpose goes.** The Privacy & data section shows, for each purpose, whether it
stays on this machine or goes to a provider, computed from its connection. A connection adds no
new door: a hosted call leaves through the door its `AiPoint` already declares (invariant 14).

## 7. The menu, and what the MVP builds

| Section | Editable now | Shown read-only or greyed | Not yet |
|---|---|---|---|
| **Appearance** | theme (the toggle moves here; it stays in `localStorage`, per browser) | | density, reduced motion |
| **Building** | | **pacing**, `Designed`: arrives with the consultant build, 14.7.8. **Tier 4**: *always stops for you*, with *let a model answer* `Designed` | the family-step threshold (stays in `.env`) |
| **Models** | **connections** (lane, endpoint, key, Test), **a model per purpose** | temperature, request timeout, job timeout, context size, concurrency | caching |
| **Privacy & data** | | **protection level**: 0 selected, open, guarded and sealed `Designed` (#71); **where each purpose goes**; telemetry on or off | the list of doors |
| **Running** | | container runtime, *call a run lost after*, executor (local; k8s and awsbatch `Designed`), API token set or open | editing any of it |
| **Registry & sources** | | the registry and its layers; GitHub and Docker Hub tokens set or not | editing them |
| **System** | | versions; database, Redis and model health | |

**Pacing is declared greyed until something reads it.** No code asks the pacing question yet;
the consultant build (14.7.8) adds it. A setting a person can change that nothing reads would be a
false control. So 14.7.5 declares it `Designed`, and 14.7.8 lifts the mark and reads it: *ask*
asks as the spec for 14.7.8 describes, the other two skip the question. #117 closes then.

**Wiener reports its own.** Wiener is a separate service with its own `.env`. `wiener-api` serves
its own `GET /settings` from the same declarations and resolver, with the default and environment
layers only and no store; the menu shows both. Editing Running is not in this step.

## 8. Storage and the API

- **Table** `installation_setting` in Mendel's Postgres, by an Alembic migration: `key` (primary
  key), `value` (JSON), `updated_at`, `updated_by` (the git name, as `identity.py`). One row per
  setting, so two people saving different settings cannot overwrite each other. No history table.
- **Read on every use**, never cached, as `model_access()` reads the environment at call time.
  The AI worker shares the database, so a change applies to its next call.
- **`GET /settings`**: every section, each declaration with its `{value, source, locked,
  reason}`. **`PUT /settings/{key}`**: validated against its declaration. A locked setting answers
  409, an illegal value 422, each with a diagnostic in a new band **`MI0300–MI0399`, the API:
  settings**, declared in `diagnostics.yml` and emitted through `coded()`.
- **Secrets** are encrypted at rest with Fernet (`cryptography` is installed), keyed by a new
  `COMENI_SETTINGS_KEY` in `.env`. Without it a secret field is greyed with
  `Needs("COMENI_SETTINGS_KEY in .env, or set the key there directly")`. No response ever carries
  a secret: it reads back as `set` and its last four characters. The value is held in a type that
  prints as hidden, so a traceback or a log line cannot show it.
- **Frontend:** `/settings/<section>`, sections down the left on a wide screen and stacked on a
  phone. The menu's code is named `preferences/` so it does not collide with `build/Settings.tsx`,
  the card for a step's parameters. The words come from the API, as `useTiers` does.

## 9. Testing

- **`comeni-core`**: over every declaration, after asserting the list is non-empty: help present,
  a greyed setting has a reason from the closed list, the default is legal for its kind, keys and
  env names are unique, every setting is in exactly one section. The resolver, one case per layer
  path, including an empty env string as unset. A **golden file** of the served menu. A purpose
  naming a removed connection resolves with a `Needs` reason, not an exception.
- **`mendel-api`** (the throwaway Postgres on :5442): store round trip; two saves to different
  keys both land; `updated_by` recorded; `GET` sources; `PUT` 409 and 422 with their codes; **no
  response holds a secret's plaintext, and neither does its row**; `model_access(purpose)` picks
  each purpose's connection and falls back to the default; every `Purpose` and `InvocationPurpose`
  member maps to a menu purpose; a builder call records its purpose's model in `ai_invocation`,
  from recorded fixtures.
- **`wiener-api`**: Running read-only, locked where `WIENER_*` is set.
- **`tests/guards/`**: **a secret never leaves**, watched failing by a serializer made to leak it,
  the revert recorded in `tests/fixtures/guard-ledger.md`. Egress: a connection adds no door, and
  `FREE_TEXT_FIELDS` does not change.
- **`frontend/`**: the setting row per kind; a greyed row shows its mark and reason; the ⓘ opens
  on click and Enter and closes on Escape; **a menu served with a setting the frontend has never
  seen still renders it**; connections add, test and remove, and *From `.env`* cannot be removed.
- **The walk:** the stack up, screenshots at desktop and phone widths for the operator. There is
  no artboard; walk first, tune after.

## 10. The parts

| Part | What | Issue |
|---|---|---|
| **14.7.5.1** | declarations, sections, the closed reasons and the resolver (`comeni_core/settings/`), with the golden menu | new |
| **14.7.5.2** | the store, the migration, `GET`/`PUT /settings`, the `MI03xx` codes, secrets, the secret guard | new |
| **14.7.5.3** | the menu: the gear, `/settings/<section>`, the setting row, the ⓘ, Appearance | new |
| **14.7.5.4** | connections, a model per purpose, `model_access(purpose)`, model lists, *where each purpose goes* | new |
| **14.7.5.5** | Building: pacing declared `Designed` until 14.7.8, tier 4 | #117 |
| **14.7.5.6** | the read-only sections: Privacy & data, Running (`wiener-api`'s `GET /settings`), Registry & sources, System | new |
| **14.7.5.7** | which models fit the 8 GiB card, measured per purpose and set through the menu | #187 |

Each part ends walkable or tested on its own. 14.7.5.1 comes first; 14.7.5.2 and 14.7.5.3 need
it; 14.7.5.4 needs all three; 14.7.5.5 and 14.7.5.6 need 14.7.5.3; 14.7.5.7 needs 14.7.5.4.

## 11. Not in this step

Per-person and per-lab layers (sign-in, #83); editing Running or Registry; caching; the list of
doors; density and reduced motion; a settings history; an artboard.
