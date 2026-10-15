# Before real users (14.7.8.3d Part H) — design

**Status: approved for planning (2026-10-12).**
Operator: “write the plan”. Decisions commented on
[276](https://github.com/comeni-project/Comeni-Labs/issues/276#issuecomment-6127927868).
Each choice below was made by the operator in the brainstorm of 2026-10-12.

Scope: [Part H](https://github.com/comeni-project/Comeni-Labs/issues/292), which is
[276](https://github.com/comeni-project/Comeni-Labs/issues/276) whole and the second half of
[273](https://github.com/comeni-project/Comeni-Labs/issues/273).
Code baseline: `59cbb0a8`, after Part G. Undo stays deferred under
[302](https://github.com/comeni-project/Comeni-Labs/issues/302).

## 1. What a laboratory gets

A laboratory running its own install can keep sessions and runs across upgrades without a row
being misread, can delete a draft or a run when it asks to, and knows how long everything else is
kept, because every limit is on the Settings page in plain words, with the last time anything
was cleared beside it.

Sample-derived files go first by default: a succeeded run's working files when it ends, a failed
run's after a week, a model's reply text and a sample excerpt's quote after a month. Everything a
person decided or wrote is kept until somebody deletes it.

A queued run survives a Redis crash: its parameters are on disk in its own directory, and the
worker relaunches it when it comes back.

## 2. Choices agreed with the operator

| Question | Choice |
|---|---|
| Whose policy is retention? | **The self-hosted laboratory's.** We ship safe defaults; the lab changes them in Settings. A hosted service later reuses the mechanism. |
| What can retention do? | **Delete by hand, and an age sweep.** A person deletes one draft or one run; per-category age limits are swept daily. |
| Default for a run's `work/` | **Deleted when a succeeded run ends; kept 7 days after a failed, cancelled or lost one.** |
| Defaults on the build side | **Model reply text and sample-excerpt quotes cleared after 30 days**; drafts, sessions, the person's words and gate output kept. Each has its own setting. |
| Visible where? | **On the Settings menu, every limit, Wiener's included** (operator: "make sure to appear on the setting menus so people can know it exists and not confusing"). |
| JSON shape versions | **A stamp per row and an eager upgrade at migrate time**; a stale stamp is refused on read. |
| JSON → JSONB | **Every column, now**, while databases are small. |
| A queued run's parameters | **`params.json` in the run's own directory, written at submit.** No table holds them (§7.1 of the retired Wiener design). |

## 3. Shape versions and JSONB

### 3.1 The registry of shapes

Each service declares `SHAPES` once (`mendel_api/shapes.py`, `wiener_api/shapes.py`; the two
services share no code, so it is written twice, as `_one_of` is):

```python
@dataclass(frozen=True)
class Shape:
    table: str
    column: str
    model: type[BaseModel] | TypeAdapter   # what a value of this column is
    version: int                           # the table's current shape_version
```

**Every JSON column is registered**, the plain lists too (`states`, `labels`, `terminal_seen`,
`pieces`), each with the model that types it. A column with no Pydantic model today gets a
`TypeAdapter` over what is actually written; the plan names each one against the code.

`run_event.payload` is Nextflow's, not ours: it is registered as `dict[str, object]`, version 1,
and the admission filter remains what shapes it.

### 3.2 The stamp

- **A `shape_version` integer on every table that has a registered column**, `NOT NULL`, one per
  table: it covers all of that table's JSON columns and bumps when any of them changes.
- **Set on write** by a SQLAlchemy `before_insert`/`before_update` listener from `SHAPES`, so no
  call site can forget it.
- **Checked on load** by a `load` listener: a row whose stamp is not the table's current version
  raises a coded diagnostic (new codes in `comeni_core/diagnostics.yml`, one per service:
  *this row was written in an older shape and was not migrated; run the migrations*). A row is
  refused, never misread.

### 3.3 Changing a shape

A shape change ships three things together:

1. the bumped `version` in `SHAPES`;
2. an upgrader, a plain function `upgrade_<table>_<n>_to_<n+1>(row: dict) -> dict` in
   `shapes_upgrade.py`, which reads and returns plain JSON, never the current model;
3. an Alembic migration that runs the upgrader over every row of the table and sets the stamp.

Old shapes never live in the database after `make migrate`, so readers carry only the current one.
A restored backup goes through the same migrations and is upgraded too.

### 3.4 JSONB

One migration per service converts every `JSON` column to `JSONB` and adds `shape_version`,
stamping existing rows 1. `models.py` declares `JSONB` (`sqlalchemy.dialects.postgresql`).
`json_array_length` in `wiener_api/repository.py` becomes `jsonb_array_length`.

**JSONB reorders keys and drops duplicate keys.** Anything that hashes or prints a reloaded value
without sorting would change. The round-trip guard (§3.5) covers it.

### 3.5 Guards, each watched failing

| Guard | Fails when |
|---|---|
| Golden JSON Schema per registered column (`tests/fixtures/shapes/<service>/<table>.<column>.json`) | a model changes and its version does not |
| Every JSON/JSONB column in the metadata is in `SHAPES` | a column is added without registering it |
| A stale stamp is refused with the diagnostic | the load listener is missing or lenient |
| Round trip: each column's representative value is stored, reloaded, compared equal, and any digest computed from it (draft graph, provenance, decision snapshot) is unchanged | JSONB's key order reaches a digest |
| An upgrade migration over a seeded old-shape row leaves it at the current stamp and valid | an upgrader is skipped |

## 4. A queued run's parameters

- **Submit writes `params.json` into `work_dir(run_id)`** before the `queued` row commits. If the
  write fails, nothing is committed and submit answers with a coded error: a row never exists
  without its parameters.
- **The job carries only `run_id`**: `launch_job(ctx, run_id)`. `launch` reads
  `params.json` from the run's directory; `_materialise_tables` still runs at launch and rewrites
  the file with materialised paths, as now.
- **Recovery:** the Wiener worker's startup re-enqueues every run still `queued`. #273's claim
  (`queued` → `launching` under a row lock) makes this safe: a claimed run is skipped, never
  launched twice. A Redis crash between submit and launch costs a delay, not the run.
- **No table holds parameters** (§7.1 of the retired `docs/design/wiener.md`). The citations in
  `worker.py` and `launcher.py` point at that file, which no longer exists; the rule gets a short
  entry in `docs/design/invariants.md` under invariant 15, and the citations point there.
- Deleting a run deletes `params.json` with its directory, so retention needs no category for it.

**Guards, each watched failing:** submit → flush Redis → start the worker → the run launches with
the submitted parameters; the enqueued job's arguments carry no parameter value; a submit whose
write fails leaves no `queued` row.

## 5. Retention

### 5.1 Deleting by hand

**A draft.** `DELETE /pipeline/drafts/{id}`, behind a confirmation on the draft's row in the
home list of pipelines (*Delete*), where drafts are listed and opened. One transaction removes the draft, its sessions, turns and proposals, its
gate runs, its decision rows (subjects, revisions, observations,
evidence access, phrasings, decision migration), and then its directory under `draft_root`. **Its model calls are kept and their reply text
cleared** (`response = NULL`, `response_cleared = 'deleted'`): `ai_invocation` has no foreign key
on purpose — *a deleted session must not take its audit rows with it* — so the record that a call
was made, its purpose, model and tokens, outlives the draft, and nothing it said does. A
draft forked from it keeps its own rows and its `forked_from` becomes null. A draft with a gate
running is refused with a code that says to wait or cancel. Wiener's copy of an artifact is not
touched: Wiener owns its store.

**A run.** `DELETE /api/runs/{id}`, behind a confirmation on the run page (*Delete run*). Only a
run in a terminal phase; a live one is refused with a code that says to cancel it first. It
removes the run's rows (`run`, `run_event`, `run_task`, `run_intent`), its whole directory
(`work/`, `results/`, `params.json`, `site.config`) and its Redis stream, all through
`wiener_api/repository.py`, which takes the `lab_id`. The artifact is deleted once no run
references it, which keeps the recorded rule *kept while any run references it*.

**Both confirmations say it is permanent, say what goes with it, and link to the Data retention
settings.** The routes are behind the same token as every other mutation.

### 5.2 The age sweep

A daily `retention_sweep` cron job on each service's arq worker, beside `check_sources` and
`heartbeat_job`. Each pass writes one `retention_sweep` row per category: when it ran, the
category, how many items it removed. It deletes by timestamps on the rows; nothing queries inside
JSON.

| Category | Setting key | Default | What the sweep does | Service |
|---|---|---|---|---|
| Working files, succeeded run | `retention.work_succeeded_days` | 0 | deletes `work/` once the run ended this many days ago; `results/` and the record stay | Wiener |
| Working files, failed / cancelled / lost run | `retention.work_failed_days` | 7 | the same | Wiener |
| Runs and results | `retention.runs_days` | kept | deletes the whole run, as §5.1 | Wiener |
| Model replies, including what a model quoted from a sample | `retention.model_replies_days` | 30 | clears `ai_invocation.response` of the builder's calls; the call's record and every decision stay | Mendel |
| Drafts and conversations | `retention.drafts_days` | kept | deletes a draft untouched this long, as §5.1 | Mendel |

**A sample's quotes live in one place: the model's reply.** Checked against the code
(2026-10-12): door 6's reply carries each quote (`CharacteriseReply`), which is stored whole in
`ai_invocation.response`; the reading kept on the proposal holds the type and states only, and
`pipeline_observation.evidence` holds counts (`records`, `rows`, `share`), never text. So the
operator's two 30-day categories are one setting, and its help says that replies to a sample
reading quote the sample. A guard holds that no quote reaches a turn, a proposal or an
observation. The forge's calls are about registry tools, never a sample, and are not swept.

*Drafts untouched* reads `pipeline_draft.updated_at`. *Kept* is `null`: kept until deleted by hand. `0` on working files means *when the run ends*.
The call panel shows a cleared reply as *Reply cleared after 30 days by this installation's
retention setting*, not as an empty string.

Removing working files leaves the run readable: its events, tasks, verdict and results are
untouched, and the run page says *Working files cleared* where it would link to them.

### 5.3 On the Settings page

**Two adjacent sections, *Data retention* (Mendel's) and *Data retention: runs* (Wiener's)**,
because a section is served by one service; both sit under *This installation*, after
*Privacy & data*, with a lede: *How long this
installation keeps what it stores. Anything not listed is kept until you delete it.* Each row
says its current limit in words (*Kept until deleted*, *Deleted when the run ends*, *Deleted
after 7 days*) and one line of help saying what is removed and what stays.

- **Mendel's rows** are `Setting.number` entries in `comeni_core/settings/catalogue.py`, stored as
  installation settings like every other.
- **Wiener's rows are editable on the same page**, not hidden in environment variables. Wiener
  keeps them in its own `retention_setting` table and serves `GET`/`PUT /api/settings/retention`;
  the browser reads both services, as it already does for the artifact copy. A `WIENER_RETENTION_*`
  environment variable pins a row, as `.env` pins every other setting (*a value in .env always
  wins*), and the row says so.
- **Under the section, the last sweep:** *Last cleared 12 Oct: 3 working folders, 41 replies*,
  read from both services' `retention_sweep`. *Not run yet* before the first pass.

**Per protection level.** These are level 0's defaults. No other level exists (#71); the
catalogue's defaults are where a later level overrides them, and nothing else changes.

### 5.4 Guards, each watched failing

- Deleting a draft leaves no row in any table that names its id (a test over every table with a
  `draft_id`, non-empty first) and no directory.
- Deleting a run leaves no row with its `run_id`, no directory, no stream; a live run is refused.
- The artifact goes with its last run and stays while another references it.
- The sweep clears exactly what is past its limit at the boundary (a day before and after), and
  writes its counts.
- A cleared reply and a cleared quote still leave the session readable and every decision intact.
- Every retention category appears in the Settings payload (a test over the categories, so a new
  one cannot be added without a row).

## 6. Order of work

1. Shape registry, stamp, listeners and diagnostics; JSONB migration; guards (§3).
2. Run parameters on disk, the slimmer job and startup recovery (§4).
3. Delete routes and their confirmations (§5.1).
4. The sweep and `retention_sweep` (§5.2).
5. The *Data retention* section, Wiener's settings route, the last sweep (§5.3).
6. A browser walk: delete a draft and a run, change a limit, see the sweep's line; then
   `make verify`, the image rebuilds, and the journal entry.

The retention and settings tables are created in step 4 and 5 already stamped and `JSONB`.

## 7. What this does not do

- No undo of a deletion (#302's undo is about decisions, and a deletion is permanent by design).
- No per-user ownership of what may be deleted: there is no authentication yet (§12.1 of the
  retired design); the API token is the boundary.
- No archive or export before deleting.
- No other protection level (#71).
- Redis keeps its present snapshot-only configuration; nothing durable depends on it any more.
