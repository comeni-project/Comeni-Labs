# Wiener: run management

**Date:** 2026-08-23
**Status:** Proposed. **Nothing in this document is built** — Wiener has zero lines of code.
**Constrained by:** [`execution-boundary.md`](execution-boundary.md), which decided what Mendel
hands over, and invariants 1, 2, 5, 6 and 13.
**Supersedes** every prior sentence about Wiener. Those were written at repository init, before
Mendel existed, and are treated here as having no authority.
**Written against a real capture**, not against memory:
[`tests/fixtures/weblog/failing-run.jsonl`](../../tests/fixtures/weblog/failing-run.jsonl) is
thirteen events from an actual Nextflow 25.10.4 run, and §4.3 lists the five things in it that
contradicted this document's first draft.

Nextflow schedules tasks. **Wiener manages runs**: it accepts one, launches it, watches it,
survives it failing at 3am on day two, remembers what happened, and tells somebody something
useful without costing a fortune in tokens to do it.

---

## 0. Why this document exists

[`execution-boundary.md`](execution-boundary.md) §8 says an MVP that runs pipelines contains the
first slice of Wiener, and names the failure mode: **building it inside `mendel-api` because that
is where the worker already is**, then discovering in six months that run state, credentials and
sample paths are entangled with the deterministic half.

This document is what that warning asks for — Wiener designed as its own thing, before a single
route is written in the wrong place.

**It also inverts a constraint.** Invariant 15 says *Mendel does not receive patient data*, and
that is structural: there is nowhere to put it. **Wiener is the opposite by definition.** It takes
a samplesheet, so it stands in the data. Every decision below is downstream of that one fact.

---

## 1. The decisions

| # | Question | Decision |
|---|---|---|
| 1 | How does Wiener learn what a run is doing? | **`nf-weblog`** — typed JSON per lifecycle transition. Never log parsing |
| 2 | What may Wiener's AI see? | **Everything, at MVP.** The redaction seam is a port from day one, so `guarded` and `sealed` slot in without a caller changing |
| 3 | Where does Wiener live? | **Its own packages in this repository**, with the import arrow held by a test |
| 4 | Is `wiener-core` pure? | **Yes** — invariant 1 extends to it |
| 5 | Where does model transport live? | **`ai-core`**, which is `mendel-ai` renamed to the thing it already is |
| 6 | Is the AI in the control loop? | **Beside it.** `decide()` is deterministic; the model explains and proposes |
| 7 | What wakes the model? | **A failure signature not seen before in this run**, plus a heartbeat |
| 8 | What does console *write* mode mean? | **A closed verb vocabulary.** Never a shell |
| 9 | How does a run get its artifact? | **Wiener owns its own store; the browser is the courier** |
| 10 | Where does the interface live? | **The existing SPA**, in `runs/`, importing nothing from `forge/` or `build/` |
| 11 | OpenTelemetry? | **Yes, full stack from slice W1** — and never as the system of record |
| 12 | Which backend? | **ClickHouse-based** (SigNoz family, Apache-2.0), reached over OTLP so it stays swappable |
| 13 | What does Wiener accept from Nextflow? | **A declared subset.** An *ingress* allowlist, mirroring the egress one — §4.4 |
| 14 | What does it look like? | **Depth** — the existing palette, layered. Four new tokens, **no new hue** — §9.5 |

---

## 2. Wiener's level is the run

[`execution-boundary.md`](execution-boundary.md) §2 separates three levels and that separation is
not repeated here. The short form:

> **task** — order, submit, retry, resume → **Nextflow**, mature.
> **run** — accept, launch, supervise, relaunch, remember → **Wiener**, this document.
> **fleet** — cost, drift, quotas → Wiener later, and §8 gives it a mechanism it did not have.

**Wiener must not re-implement the task level.** Ordering, task retry and `-resume` are a workflow
engine's job and a second one would be worse at all three.

---

## 3. The packages, and what is pure

```
comeni-core     PURE     Pipeline — the only type the two halves share
wiener-core     PURE     run and task types · fold · decide · brief · project · spans · ports
ai-core         impure   generate(shape), closed choice, the three model lanes
wiener-ai       impure   wiener-core's ports over ai-core
wiener-api      impure   ingest · launcher · WS · ARQ worker · Postgres · Redis · OTLP export
```

**Supervision splits into deciding and doing, and only the doing is impure.** That is the whole
argument for a pure core, and it is the same shape as `resolve()` returning a `DecisionRecord`
rather than editing a file:

| Pure, in `wiener-core` | |
|---|---|
| `fold(state, event) -> RunState` | a days-long run is a sequence of records; the state is a fold over them |
| `decide(RunState) -> list[Intent]` | retry, give up, escalate, notify — returns **typed intents**, never performs them |
| `brief(RunState) -> AiBrief \| None` | what the model is told, as a closed type. Token economy enforced here rather than hoped for |
| `project(RunState) -> ConsoleView \| BoardView` | what the console and the dashboard draw |
| `spans(RunState) -> list[Span]` | the OpenTelemetry mapping, §8 |
| `admit(payload) -> RunEvent` | the ingress allowlist, §4.4 |

Everything else — launching a subprocess, receiving a POST, writing Postgres, calling a model,
exporting OTLP — is `wiener-api`, and none of it decides anything.

### 3.1 `wiener-core` joins invariant 1

The static AST scan and the runtime audit hook cover it exactly as they cover the three Mendel
packages. **A fold over events has no legitimate need to open a socket**, which is what makes the
entry costless in the way `ctypes` was and `subprocess` never could be.

That extension pays for itself immediately and in a place nobody planned: **the OpenTelemetry SDK
is a network client**, so the purity guard makes it structurally impossible to put the exporter on
the wrong side of the line. The span *mapping* is pure and replayable; the *export* is not. Nobody
has to remember this.

It costs one deliberate edit to `CLAUDE.md`'s invariant 1 and one entry in
`tests/test_purity.py`'s `CLOSED_PACKAGES`, watched failing and recorded in the guard ledger
like every other guard. (This said `PURE_PACKAGES` until 2026-08-24; there is no such
constant, and the plan had it right — A181.)

### 3.2 `ai-core` is `mendel-ai` renamed

That package's own docstring already says *"this package holds no Mendel domain types … which is
what lets the tier-4 ambiguity resolver reuse it unchanged"*. Only the name was wrong.

Measured rather than assumed: **610 lines, never released, no tag, imported by five files, all in
`mendel-forge`.** So this is a rename, not a refactor. The `MA` codes move with it and
`diagnostics.yml`'s header still reads true, because it already says *the AI adapters*.

`mendel-ai` reappears as a name only when the tier-4 ambiguity resolver needs a package to hold a
`mendel_resolver.ports` implementation.

### 3.3 The arrows, held by a test

```
comeni-core  <──  wiener-core  <──  wiener-api  ──>  wiener-ai  ──>  ai-core
                                                                      ^
                                   mendel-forge ────────────────────-─┘
```

`test_no_pure_package_imports_an_impure_one` already exists and gains two rules:

- **Nothing under `mendel_*` may import `wiener_*`**, and nothing under `wiener_*` may import
  `mendel_*` — with the single exception of `comeni_core`, which is the shared artifact vocabulary
  and the reason that package keeps the platform name.
- `wiener_core` is added to `PURE_PACKAGES`.

**The exception is the interesting half.** `wiener-core` reads `Pipeline` because a run is a run
*of an artifact*, and that artifact type is `comeni-core`'s. Everything else about Mendel —
resolution, the registry, the forge — is invisible to Wiener, and a laboratory can run Wiener
against a pipeline Mendel never built.

---

## 4. Events

### 4.0 The recipe, so this section can be re-derived

```bash
# a listener that appends every POST body to events.jsonl, then:
cat > nextflow.config <<'CFG'
weblog {
    enabled = true
    url = 'http://127.0.0.1:8099/events'
}
CFG
nextflow run main.nf
```

**The CLI flag is deprecated; the feature is not.** `-with-weblog` warns and points at
`weblog.enabled = true`. **It is already an official plugin — `nf-weblog`, auto-fetched** — which
is why no bespoke `nf-wiener` plugin is built (§15).

### 4.1 The vocabulary, as captured

Six event kinds from Nextflow, and only six — plus a seventh that Wiener writes itself:

| `event` | carries | when |
|---|---|---|
| `started` | `metadata` | once, at launch |
| `process_submitted` | `trace` | a task is handed to the executor |
| `process_started` | `trace` | it began running |
| `process_completed` | `trace` | it finished — **successfully or not** |
| `completed` | `metadata` | the run ended |
| `error` | **nothing** | the run failed |
| `heartbeat` | nothing | **not Nextflow's.** `wiener-api`'s timer, on an interval — §6.1. `admit()` refuses it from the network (A175) |

Every event carries `runId`, `runName`, `event` and `utcTime`.

### 4.2 What a `trace` holds

Captured from a failed task, every key:

```
task_id 3          process FAIL_ONCE      name FAIL_ONCE       status FAILED
exit 2             attempt 1              error_action TERMINATE
submit 1787517650045   start …054         complete …079        duration 34   realtime 25
cpus 1             memory None            disk None            time None     queue None
hash a8/fe0bf1     native_id 662621       container None       module []     tag None
script "test -f out_2.txt out_1.txt && exit 3"
workdir /tmp/…/work/a8/fe0bf109df3a073f91c63213ec26cf
```

**Everything the supervisor needs is here**: `process`, `status`, `exit`, `attempt`,
`error_action`, and three timestamps as epoch milliseconds — which is §6.1's *time enters as data*
satisfied by the payload itself rather than by a convention.

### 4.3 Five things the capture contradicted

Each of these was written differently in this document's first draft, and each was corrected by
thirteen lines of JSON.

1. **`error` carries nothing.** No trace, no message, no task — `{runId, runName, event, utcTime}`
   and that is all. **The diagnosis lives in the failed `process_completed`**, not in the event
   named after failure. A design that waits for `error` to learn what broke learns nothing.
2. **`completed` fired twice, with byte-identical payloads.** So **the fold must be idempotent**,
   and that is a property to test rather than a defensive `if`.
3. **`error` arrived *after* `completed`.** The terminal event is not last. Anything that closes a
   run on `completed` and stops listening will record a failed run as successful.
4. **The trace is not free of laboratory strings.** `script` holds the command *including file
   names*; `workdir` is a path; `name` and `tag` carry the sample tag in any real pipeline. **So
   "structured fields only" is not a privacy guarantee** — that framing was wrong, and §10.2 is
   written against this instead.
5. **`started.metadata` carries `parameters`** — which in a real run is where `--input
   samplesheet.csv` lands — plus `userName`, `homeDir`, `launchDir`, `workDir` and `configFiles`.
   **The very first event of every run is the most identifier-dense one**, and it arrives before
   any task exists.

6. **The resource metrics are opt-in, and Wiener must opt in.** A first capture showed
   `memory: None` and no CPU or I/O fields at all. With `trace.enabled = true` in the config the
   same payload gains **fifteen more**: `%cpu`, `%mem`, `rss`, `vmem`, `peak_rss`, `peak_vmem`,
   `rchar`, `wchar`, `read_bytes`, `write_bytes`, `syscr`, `syscw`, `vol_ctxt`, `inv_ctxt` and
   `cpu_model`. **Everything §9 draws depends on one line Wiener writes into `site.config`**, and
   without it the dashboard is empty for reasons nothing would explain.

One thing arrived free: `completed.metadata.workflow.stats` carries `succeededCount`,
`cachedCount`, `failedCount` and `ignoredCount`, and `errorReport` carries the readable failure
text. The dashboard's summary row is a field read, not a computation.

### 4.4 The ingress allowlist

Findings 4 and 5 are why `admit()` exists.

> **Mendel declares what may leave. Wiener declares what may enter.**

`wiener-core.admit(payload) -> RunEvent` converts a weblog body into Wiener's own closed types and
**drops every field nobody declared**. It is the exact mirror of `tests/test_egress.py`: an
allowlist rather than a blocklist, because a blocklist can only forbid what somebody named — which
is how `object`, `Path` and `Any` each arrived one audit apart on the egress side.

Three consequences:

- **Wiener stores what it declared**, so a Nextflow upgrade adding a field is inert until somebody
  adds it deliberately, in a diff.
- **The identifier-dense fields are named, in one place.** `script`, `workdir`, `name`, `tag`,
  `parameters`, `userName`, `homeDir`, `launchDir`, `configFiles`, `commandLine`, `errorMessage`
  and `errorReport` are marked as **lab strings** on the type. §10.2's redaction port filters *that
  marking*, not a guess about content.
- **An unknown `event` kind is refused rather than ignored**, with a diagnostic naming it. A
  silently dropped event is a run whose state is quietly wrong.

`test_admit_declares_every_field_it_keeps` and `test_a_lab_string_is_marked` hold it, and the
committed capture is what they run against.

---

## 5. The types

Declared here because a design document that names `RunState` without showing it is a document
that will disagree with the code within a week.

```python
# wiener_core/events.py

class EventKind(StrEnum):
    STARTED = "started"
    PROCESS_SUBMITTED = "process_submitted"
    PROCESS_STARTED = "process_started"
    PROCESS_COMPLETED = "process_completed"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"      # Wiener's own timer, never Nextflow's — A175


FROM_NEXTFLOW = frozenset(EventKind) - {EventKind.HEARTBEAT}
"""What an external party may author. Smaller than `EventKind` on purpose: `admit()` refuses a
heartbeat from the network, and `heartbeat()` is the only way one is constructed."""


class TaskTrace(BaseModel):
    """One task, as Nextflow reported it. Fields not listed here are dropped by admit().

    `LAB_STRING` below is **`wiener_core`'s own marker, not `comeni_core.spell.Mark`** — A182.
    Widening that enum drags in the egress accounting invariant 14 keeps, for a marking that
    never crosses a Mendel door.
    """

    task_id: int
    process: ProcessName
    name: Annotated[str, LAB_STRING]      # carries the sample tag
    status: TaskStatus                          # SUBMITTED RUNNING COMPLETED FAILED ABORTED CACHED
    exit: int | None
    attempt: int
    error_action: ErrorAction | None            # RETRY TERMINATE IGNORE FINISH None
    submit_ms: int | None
    start_ms: int | None
    complete_ms: int | None
    duration_ms: int | None
    realtime_ms: int | None
    cpus: int | None
    memory_bytes: int | None
    hash: str | None
    script: Annotated[str, LAB_STRING] | None
    workdir: Annotated[str, LAB_STRING] | None
    tag: Annotated[str, LAB_STRING] | None


class RunEvent(BaseModel):
    """What admit() produces. The only thing fold() ever sees."""

    kind: EventKind
    run_id: RunId
    at_ms: int
    trace: TaskTrace | None = None
    manifest: RunManifest | None = None         # only on started/completed
    seq: int                                    # assigned by ingest; §6.2
```

```python
# wiener_core/state.py

class RunPhase(StrEnum):
    QUEUED = "queued"        # accepted, not launched
    LAUNCHING = "launching"  # subprocess started, no `started` event yet
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOST = "lost"            # the head process died without a terminal event


class TaskState(BaseModel):
    task_id: int
    process: ProcessName
    status: TaskStatus
    attempts: tuple[Attempt, ...]    # one per try, in order — retries are history, not overwrites
    latest_exit: int | None
    first_seen_ms: int
    last_change_ms: int


class RunState(BaseModel):
    run_id: RunId
    phase: RunPhase
    tasks: Mapping[int, TaskState]
    signatures: tuple[FailureSignature, ...]   # deduplicated, in first-seen order
    counts: Counts                              # succeeded · failed · cached · running · submitted
    started_at_ms: int | None
    ended_at_ms: int | None
    last_seq: int                               # the fold's own idempotence key
    terminal_seen: frozenset[EventKind]         # {completed}, {error}, or both — §4.3 findings 2 and 3
```

### 5.1 The fold

```python
def fold(state: RunState, event: RunEvent) -> RunState: ...
def replay(events: Iterable[RunEvent]) -> RunState:  # fold, from EMPTY
```

**Idempotent in two ways, and A176 is about not confusing them.** `event.seq <= state.last_seq`
returns `state` unchanged — which covers **replay**, the same recorded event folded twice, and
nothing else: `seq` is assigned as bodies arrive (§6.2), so a *redelivery over the network* carries
a fresh one. What covers finding 2 is **convergence**: every field the fold writes is a function of
what has been seen rather than of how often. `terminal_seen` is a set, `counts` derives from
`tasks`, and an attempt is **keyed by `trace.attempt` rather than appended** — one try is described
by three events, so appending per event gave a task that never retried three attempts and a retry
ring in §9.1.

**Terminal is a set, not a flag.** Finding 3 — `error` after `completed` — means the run's outcome
is decided by *what has been seen*, not by *what arrived last*. `terminal_seen` accumulates, and
`phase` is a function of it: `{completed}` with `success=true` is `SUCCEEDED`; anything containing
`error`, or `completed` with `success=false`, is `FAILED`.

**Retries are history.** `TaskState.attempts` is a tuple, appended to. A task that failed twice and
then succeeded is a task whose state says so — which is what the console needs to draw, and what
§10.1's signature gate reads.

### 5.2 The decision

```python
class Intent(BaseModel):
    """Something Wiener wants done. Produced by decide(); performed by wiener-api."""

    kind: IntentKind          # RELAUNCH CANCEL ESCALATE NOTIFY GIVE_UP
    because: Reason           # a declared enum, never free text
    at_ms: int                # when it becomes due — §6.1
    needs_approval: bool

def decide(state: RunState, policy: Policy, now_ms: int) -> list[Intent]: ...
```

`Policy` is declared data: maximum relaunches, the backoff schedule, the give-up threshold, whether
`ESCALATE` is automatic. **`now_ms` is a parameter** — see §6.1.

### 5.3 What is deliberately not a type

**There is no `Run` object with methods.** A run is a `RunState` plus the events that produced it,
and everything that acts on it is a free function. That is what makes replay total: there is no
hidden field that only a constructor sets, and no ordering dependency between method calls.

---

## 6. Determinism, and how it is tested

> **Same event sequence in → same run state, same decisions, same AI brief.**

This is Wiener's version of invariant 10, and it is a test rather than an aspiration.

**A three-day run replays in milliseconds, with no cluster.** Every relaunch the supervisor chose
is reproducible and explainable after the fact — the operational analogue of what `pipeline.yml`
does for a pipeline. It is also why the model is not in the decision path (§10): a model inside
`decide()` makes replay approximate, and an approximate replay cannot answer *why did it give up at
04:12*.

### 6.1 Time enters as data, never as a clock

Backoff, give-up-after and the §10.1 heartbeat all need to know what time it is, and **reading a
clock inside `wiener-core` would break this section's claim in the first week** — the same run
would replay to different decisions depending on when you replayed it.

So the rule is narrow and absolute: **`wiener-core` never calls a clock.** Every temporal fact
arrives as a field (`at_ms`, `submit_ms`, `complete_ms` — all present in the capture) or as an
explicit `now_ms` parameter. The heartbeat is itself an **event** that `wiener-api` appends on a
timer; the fold sees `HEARTBEAT(at_ms=…)` exactly as it sees a task completing.

Same move `pipeline.yml` makes by carrying no timestamps, and it has a second payoff: **a test can
advance three days in a list literal.**

`test_wiener_core_never_reads_a_clock` scans for `datetime.now`, `time.time` and
`datetime.utcnow` in the package, and is watched failing.

### 6.2 `seq` is assigned at ingest, and why that is not cheating

The fold needs a total order and HTTP does not guarantee one. `wiener-api` assigns a monotonic
`seq` per run as bodies arrive, and *that* is the recorded order. Replay is therefore
**deterministic with respect to what Wiener received**, which is the honest claim — not
deterministic with respect to what Nextflow emitted, which nothing can promise over a network.

Stating the weaker true claim is the same discipline invariant 1 uses in saying *do not* rather
than *cannot*.

### 6.3 The test corpus

[`tests/fixtures/weblog/failing-run.jsonl`](../../tests/fixtures/weblog/failing-run.jsonl) is the
first entry: a real run, two tasks succeeding, one failing, `completed` twice and `error` after it.
It is the shape `tests/fixtures/rule-corpus/` has for rules — **the assertion that the format can
express what actually happens**, rather than what the designer imagined.

Three properties every corpus entry is held to:

- `replay(events) == replay(events + events)` — replay idempotence.
- **A duplicate carrying a *fresh* `seq` changes nothing** — which is what finding 2 actually
  looked like on the wire, and what the property above cannot see (A176).
- `replay(events).phase` is terminal iff a terminal event is present, regardless of order —
  finding 3.
- `decide(replay(events), policy, now)` is equal across two runs of the test — no clock, no set
  iteration order, no dict ordering leaking into a list.

**Guards are watched failing**, and the ones this design leans on hardest are §4.4's ingress
allowlist and §6.1's clock scan, because both are the kind that pass vacuously if written wrong.

---

## 7. Storage

Three stores, and confusing their jobs is how this design fails.

| | holds | lifetime | may be lost? |
|---|---|---|---|
| **Postgres** | runs, events, task state, intents, audit rows | forever | **no** — it is the record |
| **Redis Stream** | the live tail, per run | capped | yes — Postgres can rebuild it |
| **ClickHouse** (OTLP) | spans, logs, metrics | a retention policy | yes, by design — §8 |

### 7.1 The tables

```
run           id · lab_id · artifact_id · submitted_by · submitted_at · phase · policy_id
              executor · exit_code · ended_at · nextflow_run_id · nextflow_run_name
run_event     lab_id · run_id · seq · kind · at_ms · payload(jsonb, admitted) · received_at
run_task      lab_id · run_id · task_id · process · status · attempts(jsonb) · latest_exit · last_change_ms
run_intent    id · lab_id · run_id · kind · because · created_at · approved_by · approved_at · performed_at
run_artifact  id · lab_id · uploaded_by · uploaded_at · digest · pipeline_digest · size_bytes
run_message   id · lab_id · run_id · at_ms · author · trigger · body        <- W3
```

**`lab_id` is on every table from day one** (decided 2026-08-23), and until §12.1's
authentication exists it is **server-chosen — one deployment, one laboratory, named in
settings** (A178). A tenant column a request can set is not a boundary, and phases 0–2 have no
authenticated principal to derive one from. It is cheap now and a
migration touching every table later, and the alternative — one install per laboratory — was
rejected because the hosted offering would then need one deployment per customer. **The cost is
named rather than assumed: a filter you can forget is a leak**, and it is the class of bug that
stays invisible until it is a disclosure. So the guard is not "remember the filter" — **every query on
these tables lives in `wiener_api/repository.py` and takes a `lab_id`**, and the test is that no
query is built anywhere else. That is a rule about *where*, which an AST scan checks reliably;
the first draft asked for a `lab_id` near a `select()`, which `session.get(Run, id)`,
`sa.select(Run)` and `select(Run.id)` all walk past — A177.

**`run_message` is the fifth table and it has an argument** (decided 2026-08-23). A conversation
about a failure is part of that run's history: the person who diagnosed an OOM at 3am should not
have to remember what they asked. The briefs alone would not do — those are derived from
`RunState` and replay, but an ad-hoc question and its answer are neither. **It lands in W3, with
the chat panel**; until then the four-table guard stays at four, so adding it early fails a test
rather than arriving unnoticed.

**`run_event` is the source of truth and everything else is a projection.** `run_task` and
`run.phase` exist because a dashboard cannot fold three days of events on every page load; they are
a cache with a rebuild path, and `test_projection_matches_replay` asserts the cache agrees with the
fold over the same events.

**No table holds a samplesheet's contents.** The path is in the admitted `started` payload because
Nextflow put it there; nothing copies it out into a column, and nothing indexes it.

### 7.2 The Redis stream

```
key        wiener:run:<run_id>
write      XADD  key MAXLEN ~ 10000 * seq <n> kind <k> …
read       XREAD BLOCK  from the last id the browser saw
```

**Capped, because a days-long run must not grow without bound**, and lossy on purpose: a browser
that has been closed for a day does not scroll back through Redis, it asks Postgres for a page and
then subscribes from the current id. That handoff — *page from the record, then tail from the
stream* — is the only ordering subtlety in the console, and it is stated here so W2 does not
discover it.

`MAXLEN ~ 10000` is a starting number, not a measurement; §17 carries it as open.

---

## 8. OpenTelemetry: the lens, never the record

**A run is a trace.** Run is the root span; each task is a child span; **each attempt is its own
span**, because §5.1 keeps attempts as history and a retry that succeeded after two failures should
look like three spans, not one. The mapping is a pure function over `RunState`.

**The attribute names are OpenTelemetry's CI/CD conventions, not Wiener's** — researched
2026-08-24, [`notes/specs/2026-08-24-telemetry-for-a-run.md`](../../notes/specs/2026-08-24-telemetry-for-a-run.md),
which closes §17's last open question. A run is `cicd.pipeline.run.id` on a `SERVER` span, an
attempt is a `cicd.pipeline.task.run.*` child of kind `INTERNAL`, the exit code is
`process.exit.code`, and the five `cicd.pipeline.run.*` metrics are reused verbatim — including
`cicd.pipeline.run.active`, which is the fleet gauge §2 had no mechanism for.

**There is no batch-job convention and there has not been one since 2021**, so the six facts
that genuinely have no standard name stay `wiener.*`: the attempt index, and the four
asked-versus-got pairs plus queue wait. That list is short *because* the research happened —
the first draft of this section implied a namespace and the answer is six attributes.

The table below is the shape; the mapping tables, including how `RunPhase.LOST` becomes
`timeout` and why `CACHED` becomes `skip`, are in the note.

| span | from |
|---|---|
| name | `process` |
| start / end | `start_ms` / `complete_ms` — present in the capture |
| status | `OK` for `COMPLETED`/`CACHED`, `ERROR` otherwise |
| `wiener.run_id` · `wiener.task_id` · `wiener.attempt` | the trace |
| `wiener.exit` · `wiener.error_action` · `wiener.cached` | the trace |
| `wiener.process` · `wiener.executor` | the trace and the run |

**Nothing marked `LAB_STRING` becomes a span attribute.** `script`, `workdir`, `name` and
`tag` are exactly the fields a tracing backend would happily index and retain, and §4.3's finding 4
is why that has to be a rule rather than an oversight nobody made. The same marking that gates the
AI (§10.2) gates the exporter, and one test covers both.

### 8.1 The five boards

Across-runs views, and **they live in the backend rather than in the SPA** — which is what keeps
§9.4 true: the run page is two views of one `RunState` and gains no third. These only mean
anything once there is more than one run to compare, and the store that can compare them is
already in the compose stack.

| board | answers | built from |
|---|---|---|
| **Is anything wrong now** | active runs by state, failures today, runs gone `lost` | `cicd.pipeline.run.active`, `cicd.pipeline.run.errors` |
| **Where the time goes** | per-process duration and queue wait — p50, p95, max | task spans |
| **Where the capacity goes** | asked versus used per process, worst case kept | the six `wiener.*` attributes |
| **What breaks** | exit codes per process over time, retries, repeat signatures | `process.exit.code`, `wiener.task.attempt` |
| **This run** | the run page — built in phase 2, and the reason there are four boards here and not five |

**Keep the maximum, never the mean**: the maximum is what kills a run and the mean is what
hides it (§9.3).

**It buys four things Wiener would otherwise build**: a waterfall over a 400-task run, aggregation
across runs, a retention policy, and alerting. **And the fleet level gets a mechanism** — §2's third
level is OpenTelemetry *metrics*, which it had no answer for before.

**It is never the system of record.** Telemetry backends sample, drop and expire *by design*; that
is what makes them affordable, and it is exactly what run state cannot tolerate. A clinical audit
trail is measured in months where a tracing store defaults to days.

**The full stack ships in W1**, in the dev compose. The argument for paying that cost early is not
tidiness: **W2's dashboard is then designed against telemetry somebody has been reading for weeks**,
rather than in the abstract. Plan 3D exists because screens got designed while being built; this
pre-empts the same failure for free.

**Two cautions.** Spans reaching a *hosted* vendor is an undeclared egress path, and worse than the
model one because telemetry is fire-and-forget — so **self-hosted, and off by default**, matching
`CLAUDE.md`'s existing stance. And the dev stack grows by two containers.

**The backend is named but not depended on**, and on 2026-08-24 that sentence earned itself.
SigNoz (Apache-2.0, ClickHouse-backed, OpenTelemetry-native) is still the default, because one
store for traces, logs and metrics is one thing to operate — but **it is not in
`docker-compose.yml` and will not be**: SigNoz deprecated its bundled Compose files in v0.130.0
and installs through Foundry, a CLI that renders and runs its own stack rather than composing
into somebody else's.

So the backend is **something Wiener points at** — `WIENER_OTLP_ENDPOINT`, unset by default —
rather than something this repository brings up. `ops/telemetry/README.md` is how to run one;
production is Kubernetes, where the question does not arise at all. An operator running Jaeger
or Grafana over ClickHouse points Wiener there and nothing in `spans()` or the five metrics
knows the difference.

---

## 9. The two views, and what the numbers are

The centre of the run page is one region with **two views of the same state**: the **console**,
which is what happened in order, and the **graph**, which is where it is happening. Both are
`project(RunState)` (§3) — neither holds state the other lacks, and switching between them is a
render, not a fetch.

### 9.1 The graph is 3C's layout, coloured

**Nothing new is computed.** `mendel_compiler/layout.py` already lays a pipeline's DAG out in
Python — deterministically, so the canvas is as reproducible as the emitted `.nf` — and 3C ships
the pan, zoom and orthogonal routing that draws it. Wiener takes that layout and **colours it by
run state**:

| what you see | from |
|---|---|
| node fill | the process's aggregate: all done, some running, any failed |
| node ring | attempts — a second ring means something retried |
| node label | `9 / 12` from `RunState.counts` per process |
| edge activity | a downstream task is running on what an upstream produced |

**This is the same knowledge from a different route**, which is the argument 3C's own handoff
makes about the builder: the resolver searches for edges, the builder checks edges it is handed,
and Wiener animates edges that already exist. No new declaration, no second layout engine, and a
graph that cannot disagree with the pipeline because it *is* the pipeline's layout.

### 9.1.1 Where the layout comes from — decided 2026-08-24

**`layout.py` lives in `mendel-compiler`, and §3.3 forbids Wiener importing it.** That is not an
obstacle to route around; it is the arrow doing its job, and it was unguarded until the day this
was written — `test_the_two_halves_share_only_comeni_core` now refuses both directions, and both
were watched failing.

Three ways out were considered and the third is the decision.

- **The artifact carries its layout.** Emit coordinates into `pipeline.yml` or a sidecar at
  build time. Rejected: layout is a *rendering* concern with pixel units in it, and
  `pipeline.yml` is the record of decisions. A file that pins contracts by digest should not
  also pin where a box was drawn.
- **The browser fetches the layout from Mendel.** Legal — the browser already talks to both —
  but it makes the run graph unavailable to anything that is not a browser, and it makes
  Wiener's graph depend on a Mendel deployment being reachable, which contradicts §12.1's
  *"a laboratory can run Wiener against a pipeline Mendel never built"*.
- **Extract the layout into a package that is neither half.** ✅ **The operator's call:
  *"no point in building stuff if we can't reuse it."*** A DAG layout takes nodes and edges and
  returns positions; nothing about it is Mendel's. It becomes a third shared package beside
  `comeni-core` — working name **`dag-core`** — imported by `mendel-compiler` for the builder
  and by `wiener-core` for the run graph, with **one implementation and one set of golden
  tests**, so the two canvases cannot drift apart the way two layout engines would.

**The arrow guard already accommodates this and needed no change**, which is corroboration
rather than coincidence: it forbids `mendel_*` and `wiener_*` importing each other and says
nothing about a package that is neither, exactly as `comeni-core` relies on. A shared package is
the shape the rule was written to allow.

**It is pure**, and should join invariant 1 when it lands: laying out a graph has no more need
of a socket than folding events does.

**What phase 3 must decide before it starts**: whether the extraction is a *lift* — the same
functions, moved, with `mendel-compiler` re-exporting so 3C's callers do not change — or a
redesign of the layout API.

**Read against the code on 2026-08-24, a pure lift does not reach.** `layout.of(ir: PipelineIR,
ports)` takes a `PipelineIR`; it imports nothing but `comeni_core.plan.ir` and stdlib, and it
has exactly one caller (`mendel_api.services.build`), so the move itself is trivial. What is not
trivial is that **Wiener has no `PipelineIR`** — it has the artifact, and `pipeline.yml` is a
`Pipeline`: steps and channels, which are a DAG, but not that type. Deriving an IR from a
`Pipeline` would mean reaching for `mendel_resolver.materialise`, which §3.3 forbids.

So the extraction is a **lift plus one seam**: `dag-core` lays out a neutral graph — nodes,
edges, port counts — and each half supplies its own adapter, `PipelineIR →` on Mendel's side and
`Pipeline →` on Wiener's. The layout arithmetic, which is all of it, moves unchanged.

**The safety net is unchanged and is why this is still a lift**: the builder's canvas must come
out pixel-identical, which is a golden test that already exists, and the emitted `.nf` must be
byte-identical, which `make verify` already checks.

### 9.2 What an edge may honestly show

**The byte counters arrive on `process_completed`, not during a task** (§4.2). So Wiener knows how
much a task read and wrote *after it finishes*, and knows nothing about its throughput while it
runs.

Therefore:

- **A live edge means "this edge is active"** — the consumer is running on what the producer
  wrote. That is a fact the event stream supports, and animating it is honest.
- **A live edge must not carry a rate.** A pulse whose speed or thickness implies MB/s would be
  invented, and a number nobody can source is the thing this whole project exists to not do.
- **A finished edge may carry its real weight**, because then `write_bytes` and `read_bytes` are
  known. Weighting the graph *after the fact* is how you see that one join moved 40 GB.

**Motion may be decorative, provided it is not dishonest** — and that is a correction to
`dashboard.md`'s stricter line, made by the operator on 2026-08-23. An edge that moves because work
is flowing through it is carrying no number, and it does not have to: it is *true*, it is
legible at a glance, and a graph that never moves is a screenshot. What is forbidden is motion that
*implies* a quantity nothing measured.

The discipline that remains is selectivity. A graph where everything pulses says nothing; one where
only the working edges do is a status display. The product's only other animation is the front
door's single settle, and that restraint is what makes one moving edge readable.

### 9.3 The numbers

`trace.enabled` (§4.3 finding 6) makes four comparisons available, and they are comparisons rather
than readings — a bare `peak_rss` means nothing without what was asked for.

| | asked | got | why it matters |
|---|---|---|---|
| **memory** | `memory` | `peak_rss` | the OOM story, *before* the OOM. A process at 94% of its ceiling is the next exit 137. **`memory` is empty today** — see below |
| **cpu** | `cpus` | `%cpu` | over-allocation is the commonest waste in bioinformatics: 8 cores requested, 100% of one used |
| **time** | `duration` | `realtime` | the difference is **queue wait**. On a cluster that is the number that explains a slow run |
| **i/o** | — | `read_bytes` · `write_bytes` | which step actually moves the data |

**The `asked` half of the memory row does not exist yet, and it is Mendel's** (found 2026-08-24
by querying a real run's spans). The emitted `nextflow.config` carries `ext.args` and nothing
else — no `memory` or `cpus` directive on any process — so Nextflow reports `memory: null` and
the comparison has one side. `cpus` reads 1 because that is Nextflow's default rather than
anything the pipeline asked for.

That is not a telemetry gap to paper over: **a pipeline that requests nothing cannot be
over-provisioned or under-provisioned**, and the panel should say so rather than draw a bar
against zero. It becomes a real comparison when Mendel emits resource directives, which is a
resolver-and-emitter question — a `memory` for a step is a decision with a tier and a `why:`
like any other, and it is exactly the kind of decision §14's loop would later improve from
observed runs.

**Per process, not per task.** A 400-task run has 400 traces and nobody reads 400 rows; the
dashboard aggregates by process and keeps the outlier — *STAR_ALIGN: 12 tasks, peak 61 GB of 64
requested, worst 6m41s* — because the maximum is what kills a run and the mean is what hides it.

**These are also what §10.5's brief should carry**, and they cost nothing extra: the model
diagnosing exit 137 is much better placed knowing the task peaked at 31.8 GB of a 32 GB ceiling
than knowing only that it died.

### 9.4 Why this is not a second dashboard

Everything above is a **projection of `RunState`**, so it replays (§6) and it needs no store of its
own. The one thing it does need is that `admit()` (§4.4) keeps the fifteen trace fields — which is
a line in an allowlist and a test, rather than a subsystem.

### 9.5 The visual register: Depth

**Chosen 2026-08-23, from four directions put up as artboards** — Instrument (dark, dense),
Editorial (the serif leads), Depth (the existing palette, layered) and Signal (colour blocking, big
numerals). The three rejected ones are kept in [`wiener-mockups/`](wiener-mockups/) with the
argument for each, because a rejected option whose reasoning lives only in a chat log gets
re-proposed six months later.

**Depth adds no hue.** The first draft of it invented ten colours — gradient midpoints and tints —
which is precisely the drift `tokens.css` exists to stop. The version that shipped introduces
**four tokens, every one derived from `--shadow`, which already exists**:

```css
--e1    0 1px 1px var(--shadow)                                   /* a chip, a control */
--e2    0 1px 2px var(--shadow), 0 6px 16px -10px var(--shadow)   /* a card */
--e3    0 1px 2px var(--shadow), 0 14px 34px -18px var(--shadow)  /* the working panel */
--well  inset 0 1px 2px var(--shadow)                             /* a track, a groove */
```

**That is the argument for the direction, not a detail of it.** The verdict was that the product
looks *boring and stale*, and the two diagnoses were that the restraint is right and the execution
is thin, or that the restraint itself is wrong. Depth is the first hypothesis made testable — and
because it costs no palette, adopting it across the Builder and the Forge is four lines in
`tokens.css` rather than a redesign. If it does not fix *boring*, the answer was the second
diagnosis and the finding is cheap.

Surfaces sit at three levels: `--paper` behind, `--surface` cards raised on `--e2`, every bar track
cut in with `--well`. Nothing else changed — the same six type roles, the same nine-step spacing
scale, and the same rule that certainty is drawn as stroke.

**One source of colour, and it is checkable.**
[`wiener-mockups/tokens.shared.css`](wiener-mockups/tokens.shared.css) is the only place a hex
literal appears; `build.py` generates every artboard from it, and **no hex literal appears in any
artboard outside that block** — verified by grep rather than asserted. That mirrors what
`frontend/src/tokens.css` gives the product, and it is why a colour change is one edit.

**What is not done:** the four tokens are not in `frontend/src/tokens.css`. That file's header
states `dashboard.md` §2 is authoritative and it mirrors it, so adopting them is a two-file change
touching every screen — deliberately deferred, and §17 carries it.


---

## 10. The AI

**`decide()` owns every action, deterministically.** Relaunch counts, backoff, give-up thresholds —
all from declared policy, all pure, all replayable. **The model explains and proposes.** A proposal
is a flagged suggestion a named human accepts, which is invariants 2 and 6 arriving in a new place
with the same shape.

### 10.1 What wakes it

A run that retries the same failure forty times must not cost forty model calls.

```
task 12  STAR_ALIGN  exit 137   ->  NEW signature      ->  one model call
task 12  STAR_ALIGN  exit 137   ->  seen this run      ->  zero tokens
task 12  STAR_ALIGN  exit 137   ->  seen this run      ->  zero tokens
task 31  SAMTOOLS…   exit 1     ->  NEW signature      ->  one model call
run completed                   ->  one closing brief

3-day run · 400 tasks · 41 failures  ->  3 model calls.
```

A **signature** is `(process, exit, error_action)` — all three present in the capture, and
**never message text**. (It was `(process, exit, error_class)` with `error_class` *derived from*
`status`, `exit` and `error_action`, which carried `exit` twice and, since `status` is `FAILED`
for anything that produces a signature at all, amounted to `error_action` under another name —
A183.) A
signature computed from prose would drift with Nextflow's wording, which is the same reason §4
refuses log parsing.

The gate is a pure function, so deduplication is deterministic rather than a cache hit, and
`signatures` living on `RunState` (§5) means **replay reproduces exactly which calls would have been
made** — the token cost of a run is a testable property, not an invoice surprise.

**A heartbeat** adds one cheap brief on an interval even when nothing failed, so the chat panel can
answer *is this normal* and not only *what broke*. It is an event (§6.1), so it replays too.

### 10.2 What it may see

**At MVP: everything**, including `errorReport` and the lab strings §4.3 found in the trace. That is
a deliberate choice and its consequence is written here rather than discovered: **Wiener's MVP is
research-use.** A laboratory handling patient data should not point it at a hosted provider until
§10.3 exists.

**Finding 4 corrected this section's first draft.** "Structured fields only" was offered as a
privacy guarantee and it is not one: `trace.script` holds file names, `trace.workdir` is a path,
`trace.name` and `trace.tag` carry the sample tag, and `started.metadata.parameters` carries the
samplesheet path in the very first event. **The dangerous fields are structured.**

So redaction is **a filter over declared markings**, not a scan of free text:

```python
class Redactor(Protocol):
    def brief(self, state: RunState) -> AiBrief: ...
```

`PassThrough` ships and passes everything. Because `LAB_STRING` is on the *type* (§5), an
implementation that drops marked fields is a few lines and cannot miss one that was added later —
adding a marked field without handling it fails the totality test rather than leaking quietly.

**Scrubbing is not the answer and never will be.** `clinical-data-protection.md` already rejects
it: Safe Harbor needs all eighteen identifier classes gone, and NLP de-identification leaves false
negatives *and fails silently*.

### 10.3 The seam that makes the other modes cheap

`PassThrough` is to `Redactor` what `NoFiller` is to `HoleFiller`: **declare the seam, ship the one
implementation you need, add the others without a caller changing.** The three protection profiles
are then three implementations —

| | `open` | `guarded` | `sealed` |
|---|---|---|---|
| lab strings in the brief | sent | shown, then sent on confirmation | dropped |
| provider | any lane | any lane | local model, or none |

— and Wiener becomes the first thing in the repository to implement a table that has been on paper
since [#71](https://github.com/comeni-project/Comeni-Labs/issues/71).

### 10.4 What a fix means

**Two classes, and confusing them is the failure:**

- **Run-level** — more memory, a different queue, resume. Touches `-c site.config` and Wiener's own
  launch, **never the artifact**. Wiener may apply these on a human's approval; at MVP it shows the
  exact change and a person clicks.
- **Pipeline-level** — a wrong parameter, the wrong tool. That is `pipeline.yml`, which is Mendel's.
  **Wiener never patches it**; it emits a proposal (§14). Same rule as invariant 5: repair patches
  the IR and re-emits, it never edits the generated text.

*"I cannot fix this"* is therefore a **typed outcome** — the model classified the failure as
pipeline-level or unknown — rather than a sentence it happened to produce.

### 10.5 The brief, shaped for the budget

```python
class AiBrief(BaseModel):
    why: BriefTrigger                    # NEW_SIGNATURE | HEARTBEAT | RUN_ENDED | ASKED
    run: RunSummary                      # phase, counts, elapsed — from RunState.counts
    signature: FailureSignature | None
    task: TaskBrief | None               # process, exit, attempts, resources, timings
    neighbours: tuple[TaskBrief, ...]    # what fed it, what else ran — bounded
    report: Annotated[str, LAB_STRING] | None   # errorReport, when the Redactor allows
```

Bounded by construction: `neighbours` has a declared maximum, and there is no field that can hold a
console tail. **The budget is a type, not a discipline.**

---

## 11. Acting: a closed verb vocabulary

The console is **read-only at MVP**. The door to write mode is left open, and what comes through it
is a fixed, typed set of run operations — **never a shell**.

```
> relaunch --resume --mem 64.GB
  Intent:    RELAUNCH(resume=true, overrides={memory: 64.GB})
  because:   OPERATOR_REQUEST
  requires:  approval by a named human
  audit:     who · when · why · prior phase · resulting run id
```

| verb | does | note |
|---|---|---|
| `cancel` | terminate the head process | the only one that needs no artifact |
| `relaunch` | launch again, optionally `-resume` | a **new run row**, linked to the old |
| `retry task N` | relaunch with `-resume`, targeting one failure | Nextflow does the resuming |
| `pause` | stop submitting new tasks | running tasks finish |
| `apply` | take a §10.4 run-level proposal into `site.config` | shows the diff first |

**There is no `retry this task in place`**, because task-level retry is Nextflow's (§2) and a second
implementation would be worse. `retry task N` is `relaunch --resume` with the intent recorded.

**The console displays text; the interactive part is a command palette over a vocabulary, not a
terminal.** There is no code path from that box to a shell, and adding one means adding a verb —
visibly, in a diff. **This is the surface that deserves the hardest audit in Wiener**, and the
vocabulary is what makes the audit finite: a reviewer checks a list of verbs, not a sanitiser.

---

## 12. Submission, and who may do it

**Wiener owns its own artifact store.** Submitting a run uploads the gated pipeline directory into
Wiener's storage; Wiener owns it from then on. **No shared volume, no shared environment variable,
no shared id.**

**A submission fills the artifact's declared holes, and the artifact is the schema** (decided
2026-08-24). This document said `samplesheet`, and a real run needs three values: the emitted
config carries `params { fasta = null; gtf = null; input = null }`, and Mendel emits all three
the same way because a `Goal` says *`have: genome.fasta`* — a type, not a file. So the rule is:
**Mendel emits every value it can justify and a placeholder for every value only the laboratory
can supply; Wiener fills the placeholders.** `declared_holes()` reads the nulls out of the
artifact, so an unknown key and a missing one are both refused at submit — for any pipeline,
including one Mendel never built. The values reach Nextflow through `-params-file`, which
carries a list where a spliced `--input` could not, and no table holds them (§7.1): they ride
to the launcher as a job argument, which is the right lifetime for run data.

It costs one thing, said plainly: a value filled at submit has no `why:`, because it is data
rather than a decision. If a reference genome ever becomes a resolvable decision — a curated
`GRCh38` with a citation — Mendel emits a value instead of `null`, the hole disappears, and the
map stops carrying that key with **no change to this API**.

```
Mendel side                    Wiener side
-----------                    -----------
build -> gate                  POST /api/runs
    │                            artifact_id + samplesheet + executor + policy
    └── browser fetches ───────► POST /api/artifacts   (pipeline.yml · main.nf · config · modules)
                                 -> Wiener's own store, Wiener's own id
```

**The browser does the copy, so `mendel-api` still never learns Wiener exists** — which keeps
`execution-boundary.md` §9's rejection of a Mendel→Wiener API intact rather than quietly bending it.
The user sees one button.

**The Mendel half of that copy does not exist yet — A179.** `mendel-api` has no route serving a
kept artifact: `keep` writes files under `MENDEL_DRAFT_ROOT` and nothing reads them back out over
HTTP. Until one is added, submission is an operator with a `zip` and a `curl`, which is what W1
phases 0–2 do. Whoever builds the button builds that route first.

This closes a gap that document names in §4: today the only thing that can name a gated artifact is
`settings.draft_root / draft_id`, both of them `mendel-api`'s private facts. **Sharing those between
the halves is the entanglement §8 warns about, arriving as an environment variable.**

### 12.1 Wiener executes what it is handed

**That is arbitrary code execution by design.** Running a pipeline is running code; every design has
this property and pretending otherwise would be the dangerous version. What follows from stating it:

- **Wiener's trust boundary is *who may submit*.** Authentication is a requirement of W1, not a
  later hardening pass — which is a genuine difference from `mendel-api`, where `who` is attribution
  and says so on three tables.
- **The artifact is content-addressed on upload** (`digest`), so *what ran* is answerable later, and
  a submission that claims to be a gated pipeline can be checked against `pipeline.yml`'s own
  recorded digests.
- **Write mode (§11) gates additionally on internal-network origin**, off by default. The verb
  vocabulary is what makes that gate meaningful: a shell behind an IP check is still a shell.

**Wiener becomes independently useful**, and that is a feature rather than a side effect — a
laboratory can run a pipeline Mendel never built, which is a far stronger position than a component
that only works downstream of us, and it is invariant 13's spirit applied one level out.

---

## 13. The API surface

```
POST   /api/artifacts              upload a gated pipeline directory -> {artifact_id, digest}
GET    /api/artifacts/{id}         what it is: pipeline digest, gate verdict, process count

POST   /api/runs                   {artifact_id, params, executor, policy_id} -> {run_id}
GET    /api/runs                   the board: phase, counts, elapsed — one row per run
GET    /api/runs/{id}              RunState, projected
GET    /api/runs/{id}/tasks        the task table, paged
GET    /api/runs/{id}/events       the record, paged — what the console reads before subscribing
WS     /api/runs/{id}/stream       the live tail, resuming from a stream id
POST   /api/runs/{id}/intents      a verb (§11) -> pending approval
POST   /api/intents/{id}/approve   a named human accepts it

POST   /events/{run_id}            nf-weblog's ingest. NOT under /api — §13.1
GET    /api/runs/{id}/brief        the latest AiBrief and what the model said
POST   /api/runs/{id}/ask          the chat panel
```

### 13.1 The ingest endpoint is not a public route

`POST /events/{run_id}` is written to by the head process, which Wiener launched, over loopback. It
is **bound separately from the public app** and carries a per-run secret in the URL that Wiener
generated at launch — so an ingest route is not something an unauthenticated client can post to just
because it exists.

That separation is written down because the alternative is the exact shape of the defect Plan 3A
phase 6 found: *the forge's mounted transport takes filesystem paths from an unauthenticated
request*. An ingest endpoint mounted on the public app for convenience is that defect, one release
later.

---

## 14. The feedback loop, and why it is not a database

The ask was that a failure be *"added to the database of issues so the compiler gets better"*. The
intent is right and the mechanism cannot be a database:
[`declared-data.md`](declared-data.md) decided declared data is files, and a fuzzy store that
influences resolution without passing the forge breaks invariant 2.

**There is already a route, and it is the one thing the project is missing.**

> Issue #38's closing note says the drafting question and the measuring question are the same one,
> and that a measurement has no `meta.yml` to be ground truth. **A real run failure is that ground
> truth.**

```
run fails  ->  signature  ->  recurs across runs  ->  a proposal into the FORGE queue
                                                              │
                                                       a human approves
                                                              │
                                                    a rule or contract in the registry
                                                              │
                                                 the next `mendel build` resolves better
```

**A signature can carry its decision.** `pipeline.yml` is in the artifact Wiener owns and
`Pipeline` is a `comeni-core` type, so a failure can name the tier, the rule and the contract
that produced the step — which turns a proposal from *"STAR_ALIGN fails sometimes"* into *"the
rule setting its memory is wrong above 3 Gb"*.

`STAR_ALIGN` exiting 137 across nine runs on genomes over 3 Gb is exactly the observed-data premise
a tier-3 rule encodes — and Mendel is named for deriving laws from observed data. **Wiener never
writes the registry.** It contributes evidence; the forge remains the only door, which is invariant
2 intact.

**What crosses is a signature and a count, never a run.** The proposal carries `(process, exit,
error_class, n_runs, the resource ceilings involved)` — no samplesheet, no path, no lab string. The
forge sits on the Mendel side of the boundary, so this is the one place Wiener data reaches Mendel,
and it is the narrowest possible shape.

This is slice **W6** and it is last on purpose: it needs many runs to have happened, and it inherits
the open design risk of
[`../../notes/specs/2026-08-13-the-rule-drafter.md`](../../notes/specs/2026-08-13-the-rule-drafter.md).

---

## 15. What was rejected

- **A bespoke `nf-wiener` Nextflow plugin.** `nf-weblog` already exists, is official and is
  maintained — it downloaded itself during the §4.0 capture. Writing one saves a loopback hop and
  costs a Groovy artifact to build, distribute and pin against every Nextflow version, plus Redis
  credentials inside the run process. It becomes right when Wiener needs a field Nextflow does not
  emit — a task correlated back to the `pipeline.yml` decision that produced it — and not before.
- **Parsing the console or `.nextflow.log`.** The least deterministic option, and the text is
  Nextflow's to change between versions. It was also the only option that would have needed the
  logging rework the brief anticipated — **so that scope disappeared rather than being descoped.**
- **Waiting for the `error` event to learn what failed.** §4.3 finding 1: it carries nothing.
- **Building Wiener inside `mendel-api`.** `execution-boundary.md` §8. The worker being there is the
  reason it is tempting and not a reason it is right.
- **A separate repository, now.** The hardest boundary and the wrong cost today: `comeni-core` is not
  published to an index, so it would mean cross-repo pinning to buy a guarantee a test already gives.
  Reconsider when Wiener needs its own release cadence.
- **A model in the control loop.** It would make replay approximate, and an approximate replay cannot
  answer *why did it give up at 04:12*. The typed `Intent` vocabulary exists from day one, so a
  bounded autonomous mode later is a policy swap rather than a rewrite.
- **"Structured fields only" as a privacy guarantee.** §4.3 finding 4 disproved it with a capture.
- **Scrubbing error text.** Rejected repository-wide, for reasons that have not changed.
- **OpenTelemetry as the system of record.** §8. Sampling and expiry are what make a tracing store
  affordable and are exactly what run state cannot tolerate.
- **A real shell in the console.** §11. A box that reaches a process is one bug from reaching a
  shell; a vocabulary is auditable and a sanitiser is not.
- **Task-level retry implemented by Wiener.** §2 and §11 — Nextflow's `errorStrategy` and `-resume`
  already do it, and Mendel can already emit both.
- **A samplesheet anywhere in Mendel.** Invariant 15, unchanged and unweakened: this document puts
  the samplesheet in Wiener, which is where it was always going to live.
- **Mounting the ingest endpoint on the public app.** §13.1.

---

## 16. Costs, stated

- **Wiener stands in patient data**, and its MVP AI sees everything. Until §10.3's other two
  implementations exist, it is research-use, and saying so is part of shipping it.
- **Authentication is in W1**, not deferred. §12.1 is why: `who` is a permission here, where in
  `mendel-api` it is attribution.
- **The dev stack grows by two containers** and one more database to operate.
- **An artifact is copied** rather than shared. A boundary that costs nothing is usually not a
  boundary.
- **A model still costs something.** Three calls for a three-day run is cheap, not free, and the
  heartbeat is a standing charge chosen deliberately over silence.
- **Two of the six slices depend on infrastructure nobody has.** W5 needs a cluster and an AWS
  account, and proving the AWS row costs money.
- **`mendel-ai` is renamed.** Cheap today — five importers, no release — and it will never be cheaper.
- **Invariant 1 is edited**, which is a deliberate act and the first time that list has grown.

---

## 17. What is open

**Seven questions were put to the operator on 2026-08-23 and answered.** They are kept here with
their answers rather than deleted, because an open question that closes silently reads afterwards
as one nobody asked.

| | decided |
|---|---|
| **Multi-tenancy** | **A `lab_id` column from day one** — §7.1. Cheap now, a migration touching every table later. The cost is named: a filter you can forget is a leak |
| **`LOST` detection** | **Absence of events, generous window.** Purely a function of the stream, so it replays and needs no new signal. **Blunt on purpose**: a six-hour STAR align emits nothing while running and looks identical to a dead head process, so the window must exceed the slowest single task |
| **Artifact retention** | **Kept while any run references it** — and runs are forever, so artifacts are too. Disk grows; a spine is a few MB and the day that stops being true, deduplicating by digest is already possible because artifacts are content-addressed |
| **Executor choice** | **`Literal["local"]` until W5.** An enum accepting `awsbatch` before anything has run there is a lie the API tells its own generated client, which would offer it in a dropdown |
| **`MAXLEN ~ 10000`** | **Ship the guess and measure it at Checkpoint 3.** Losing the tail is survivable — Postgres is the record and the browser re-pages — so the number becomes a measurement rather than staying a guess |
| **The chat's history** | **A fifth table, `run_message`, argued for in §7.1.** It lands in W3; until then the four-table guard stays at four, so adding it early fails a test |

| **The run graph's layout** | **A third shared package, `dag-core`** — §9.1.1, decided 2026-08-24. `layout.py` is `mendel-compiler`'s and §3.3 forbids Wiener importing it; extracting it is the only answer that keeps one implementation. The arrow guard needed no change to allow it, which is what a rule written for the right reason looks like |

**Still genuinely open, and it is one:**

- ~~**The OTLP semantic conventions.**~~ **Closed 2026-08-24** —
  [`notes/specs/2026-08-24-telemetry-for-a-run.md`](../../notes/specs/2026-08-24-telemetry-for-a-run.md).
  The premise was half wrong in a useful way: **there is no batch or job convention**, and
  `opentelemetry-specification#1347` has been open since January 2021 with no maintainer
  conclusion, so waiting for one is waiting for nothing. What does exist is the **CI/CD** group
  — Release Candidate, and a pipeline that runs named tasks which succeed or fail on workers is
  the same shape as a Nextflow run. Adopted: `cicd.pipeline.*` for the run, `cicd.pipeline.task.run.*`
  for each attempt, `process.exit.code` for the exit, and the five CI/CD metrics verbatim. Six
  facts have no standard name and stay `wiener.*`. One convention is deliberately refused:
  `process.command_line` exists and `trace.script` is a lab string, so the field stays empty —
  adopting a convention is not adopting every field in it.

- **The product's visual register — an operator verdict, 2026-08-23.** *"The website until now is
  very boring and stale, even the graphs are not very visually appealing — but for an MVP it is
  reasonable."* Recorded rather than absorbed, because the last verdict of this shape (*the forge
  is really unintuitive and unusable*) became Plan 3D, and it only became a plan because somebody
  wrote it down. **Half-answered**: four directions went up as artboards and **Depth was chosen**
  (§9.5) — a bet that the restraint is right and the execution was thin. What stays open is whether
  it *works*, which only a week of looking at a real screen settles, and that the four tokens are
  **not yet in `frontend/src/tokens.css`**, so nothing outside the mockups has changed. Adopting
  them is four lines plus a `dashboard.md` §2 edit.

**And one that is not a question but a gap**, named so it is not discovered: §12.1 makes
authentication a W1 requirement, and the phases 0–2 plan does not satisfy it. `submitted_by` is
attribution. Phases 0–2 are for one operator on a laptop; the first deployment anybody else can
reach needs the check first.

---

## 18. Six slices

Each produces working software and gets its own plan, written against the code the previous one
lands. Writing all six now would be writing five against code that does not exist, which is what
killed Plan 2 and the original Plan 3.

| | What | Ends on |
|---|---|---|
| **W1** | `wiener-core` (types, `admit`, `fold`, `decide`, `project`, `spans`) · `wiener-api` (auth, artifacts, submit, launcher, ingest, Postgres, Redis) · OTel SDK, collector and ClickHouse in compose · a plain run list and a streaming console · local executor · no AI | **a real pipeline runs on real data, you watch it finish, and its waterfall is already queryable** |
| **W2** | The console and dashboard properly: WS with a reconnect offset, the page-then-tail handoff, the expandable top panel, the task table, attempts visible — designed against telemetry read since W1 | you can read a 400-task run without reading text |
| **W3** | `ai-core` rename · `wiener-ai` · the signature gate and heartbeat · the chat panel · the `Redactor` port | a three-day run cost three model calls and explained its own failure |
| **W4** | The verb vocabulary: cancel, relaunch, retry, pause, apply — typed `Intent`s, approval, audit, the internal-network gate | a failed run is recovered from the browser, with no terminal |
| **W5** | `k8s` and `awsbatch` proven for real · `site.config` · credentials · who may choose an executor | `execution-boundary.md` §7's *the profile resolves* becomes *it runs* |
| **W6** | Failure signatures accumulating across runs; recurring ones become forge proposals | a run failure produced a reviewed registry change |

**W1–W4 is the MVP.** The ordering argument: W1 first because nothing else has anything to watch; W3
after W2 because the AI brief and the dashboard are the same projection; W4 after W3 because *attempt
to fix* needs a proposal to act on; W6 last because it needs runs to have happened.

### 18.1 What you cannot do at the end of W1

Stated because every 3A phase states it, and the one that did not is the one that shipped a frontend
with zero event handlers.

- **You cannot cancel a run.** No verbs until W4; closing the tab does nothing to the pipeline.
- **You cannot understand a failure without reading text.** The console shows what happened; nothing
  summarises it until W2 and nothing explains it until W3.
- **You cannot run anywhere but local.** The profiles exist (`execution-boundary.md` §7) and nobody
  has proven them; W5.
- **You cannot see a run from another machine's Wiener.** One deployment, one store.
- **There is no chat panel**, and the right-hand column is empty on purpose rather than stubbed.

**W1's ending condition is a pipeline that ran** — not a shell that compiles, and not a screen that
renders a fixture.
