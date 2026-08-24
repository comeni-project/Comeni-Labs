# Wiener W1, phase 3 — the graph, the telemetry, and the boards

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes, and where a step was
> carried out differently, tick it anyway and record the deviation in the execution table.

**Goal:** a run you can look at rather than read — the pipeline's own graph coloured by what
happened, the numbers §9.3 names, and four across-runs boards in a telemetry backend.

**This finishes W1.** `docs/design/wiener.md` §18's W1 row ends on *"a real pipeline runs on real
data, you watch it finish, and its waterfall is already queryable"*. Phases 0–2 delivered the
first two clauses on 2026-08-24; this is the third.

**Longer than usual, on purpose, and with six checkpoints rather than three** — the operator's
instruction. Phases 0–2 were 12 tasks and 3 checkpoints; this is 13 tasks and 6, because three of
them end on *a thing you look at* and looking is what found nine defects in Plan 3E that 76 green
steps did not.

**Specs:** [`../../docs/design/wiener.md`](../../docs/design/wiener.md) §8, §8.1, §9 and §9.1.1,
and [`../specs/2026-08-24-telemetry-for-a-run.md`](../specs/2026-08-24-telemetry-for-a-run.md) for
every attribute name and enum mapping. **The research is done — do not re-derive it, and do not
invent a `wiener.*` name that the note does not list.**

## Global constraints

- **`wiener-core` and `dag-core` are PURE.** No network, no subprocess, no clock. The
  OpenTelemetry **SDK is a network client** and may not be imported by either — §3.1 says this
  guard is what makes putting the exporter on the wrong side structurally impossible, and phase
  3 is where that stops being theoretical.
- **`spans()` returns Wiener's own `Span` type, not the SDK's.** The pure half describes the
  telemetry; `wiener-api` translates and sends it.
- **The two halves share only `comeni-core` and `dag-core`** — `test_the_two_halves_share_only_comeni_core`.
  A new shared package is legal and needs no change to that guard; check rather than assume.
- **No new screens.** §9.4: the run page is two views of one `RunState`. The graph is the second
  view, already designed; the boards live in the backend.
- **`make check` is the gate.** Task 1 touches `mendel_compiler`, so it is the one task that
  needs **`make verify`** — `emit.py` is not touched but `layout.py` feeds the canvas and
  `CLAUDE.md`'s rule is about the directory.
- **Diagnostic codes:** Wiener's band is `MW0001`–`MW0099`; `MW0001` and `MW0002` are taken.
  Read `diagnostics.yml`'s real schema before writing an entry — **two plans in a row have
  guessed it wrong** (`emitted_by`, `concern`, `says`, `fires_on`, `refuses`, `fix`,
  `explanation`, and `extra="forbid"`).
- **Commit messages** end with the two trailer lines `CLAUDE.md` specifies.

## The pre-execution audit — A184–A190, 2026-08-24

Run against the code before a line was written, the way 18a's was. **Seven findings, one
critical, and the critical one is the same mistake Checkpoint 2 caught one layer down.**

| | What | Where | Fixed |
|---|---|---|---|
| A184 | **`RunState` carries none of the fifteen resource fields, so `spans()` cannot emit them** | `state.py`; plan Tasks 3, 4, 11 | Task 2a, added |
| A185 | `GET /api/pipeline/layout` does not exist | plan Task 1 | yes, below |
| A186 | The safety net exists already and is better than the one invented | plan Task 1 | yes, below |
| A187 | The `dag-core` allowlist omits `__future__` | plan Task 1 | yes, below |
| A188 | `Ports` is a type alias and the plan does not say which side it lands on | plan Task 1 | yes, below |
| A189 | 3C's canvas is reusable — confirmed, with the file names | plan Task 9 | yes, below |
| A190 | **`cicd.pipeline.name` is Required and the artifact has no name** | plan Task 3 | **open — needs a decision** |

### A184 — the fold drops what `admit()` was fixed to keep

```
Attempt  : n, status, exit, at_ms
TaskState: task_id, process, status, attempts, latest_exit, first_seen_ms, last_change_ms
```

**None of the fifteen `trace.enabled` fields survives the fold**, and neither do a task's
`start_ms` and `complete_ms`. Three tasks in this plan are built on the assumption that they do:

- §8 says *each attempt is its own span* with *start / end from `start_ms` / `complete_ms`* —
  `TaskState` has `first_seen_ms` and `last_change_ms`, which are **per task, not per attempt**,
  so a retried task's three spans would share one pair of timestamps.
- Task 4's six `wiener.*` attributes read `cpus`, `%cpu`, `memory`, `peak_rss`, `duration`,
  `realtime`, `read_bytes`, `write_bytes` — none of which `RunState` has.
- Task 11 aggregates "from `run_task`", whose `attempts` column is a JSON dump of `Attempt`.
  Same four fields. **The §9.3 panel cannot be built from the projection as it stands.**

**This is Checkpoint 2's finding one layer up.** `admit()` was dropping the fields and the
record lost them forever; now the record keeps them and *the fold* drops them, so everything
downstream of `RunState` is blind again. The difference is that this one is recoverable —
`run_event` has the payloads — but every projection built before the fix is wrong.

**Task 2a is added below**, before any span is written.

### A185 · A186 — the route and the net

`GET /api/pipeline/layout` does not exist. The build router carries `prefix="/pipeline"` and the
layout surface is `POST /api/pipeline/draw` (`drawPipeline`), which returns a `BuiltPipeline`.
**This is exactly the class of error 18a's audit found in every route path it checked**, one
plan later.

And the safety net was invented when a better one exists:
**`packages/mendel-compiler/tests/test_layout.py`, 270 lines**, including
`test_the_same_ir_lays_out_identically`, `test_nothing_overlaps`,
`test_every_coordinate_is_an_integer` and `test_a_producer_sits_above_its_consumer`. A move that
keeps those green has kept the canvas. The `/tmp` JSON diff is deleted from the plan.

### A187 · A188 — the allowlist and the alias

`layout.py` imports `__future__`, `collections`, `dataclasses` and `comeni_core`, and
`_outside_allowlist` has **no exemption for `__future__`** — the entry as written fails at Step
2. `Ports = Mapping[str, tuple[list[str], list[str]]]` is a type alias in `layout.py`; it
describes a *pipeline's* ports and belongs with the adapter, not with the arithmetic.

### A189 — the canvas is reusable, and here is where it lives

`frontend/src/build/`: `Canvas.tsx`, `useGraph.ts`, `geometry.ts`, `Graph.test.tsx`. Task 9's
assumption holds; the file names are recorded so the executor does not go looking.

### A190 — the one that needs a decision

**`cicd.pipeline.name` is Required on the resource, on the run span and on three of the five
metrics, and `Pipeline` has no name field.** Its fields are `version`, `goal`, `registry`, `ai`,
`steps`, `channels`, `decisions`, `emitted`, `gate`.

Every board groups by this. The candidates:

1. **The artifact digest.** Honest and stable, and **every rebuild is a new series** — so *"is
   the spine getting slower"* cannot be asked across a change.
2. **Derived from the goal** — `counts.matrix` from `goal.want`. Stable across rebuilds, low
   cardinality, and two different pipelines producing the same thing collide.
3. **A name the submitter supplies**, defaulting to (2). Answers both, and adds a field to a
   submit body the operator has already had to correct once.

**Not chosen here.** It changes what every board can ask, and the plan should not pick it.

## File structure

| File | Responsibility |
|---|---|
| `packages/dag-core/src/dag_core/graph.py` | `Node`, `Edge`, `Graph` — the neutral shape a layout takes |
| `packages/dag-core/src/dag_core/layout.py` | the arithmetic, moved from `mendel-compiler` unchanged |
| `packages/mendel-compiler/src/mendel_compiler/layout.py` | the `PipelineIR →` adapter, and a re-export |
| `packages/wiener-core/src/wiener_core/graph.py` | the `Pipeline →` adapter, and `coloured()` |
| `packages/wiener-core/src/wiener_core/spans.py` | `Span`, `SpanKind`, `spans(RunState, Pipeline) -> list[Span]` |
| `packages/wiener-api/src/wiener_api/services/telemetry.py` | the OTLP exporter and the five metrics |
| `packages/wiener-api/src/wiener_api/routes/runs.py` | `GET /api/runs/{id}/graph` |
| `frontend/src/runs/Graph.tsx` · `Stats.tsx` | the second view, and §9.3's numbers |
| `ops/boards/` | the four board definitions |

---

## Phase 3A — the layout, shared

### Task 1: `dag-core`, and the canvas that does not move

**Files:**
- Create: `packages/dag-core/pyproject.toml`, `src/dag_core/{__init__,graph,layout}.py`,
  `packages/dag-core/tests/test_layout_moved.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/layout.py`, root `pyproject.toml`,
  `tests/test_purity.py`, `CLAUDE.md`, `notes/audits/guard-ledger.md`

**Interfaces:**
- Consumes: `comeni_core.plan.ir` (in the adapter only).
- Produces: `dag_core.Graph`, `dag_core.layout.of(graph) -> Layout`, and
  `mendel_compiler.layout.of(ir, ports)` unchanged for its one caller.

**Read first:** §9.1.1. The lift does not reach on its own — `layout.of` takes a `PipelineIR`
and Wiener has a `Pipeline`, so the extraction is **the arithmetic moved plus one seam**.

- [x] **Step 1: Read the net that already exists — A186**

`packages/mendel-compiler/tests/test_layout.py` is 270 lines and holds the canvas by its
properties rather than by a blob: `test_the_same_ir_lays_out_identically`,
`test_nothing_overlaps`, `test_every_coordinate_is_an_integer`,
`test_a_producer_sits_above_its_consumer`, `test_a_straight_drop_is_two_points`. **A move that
keeps those green has kept the canvas**, and it does not need a `/tmp` file to say so.

Run it now and note the count, so "unchanged" has a number: `uv run pytest packages/mendel-compiler/tests/test_layout.py -q`

- [x] **Step 2: Create the package, pure and classified**

Manifest like `wiener-core`'s; `dependencies = ["comeni-core>=0.1.0"]`. Add to root
`dependencies` and `[tool.uv.sources]`, and to `CLOSED_PACKAGES` in `tests/test_purity.py`:

```python
    "dag-core": {
        "__future__", "collections", "collections.abc", "dataclasses", "typing",
        "comeni_core", "dag_core",
    },
```

**`__future__` is on that list because `layout.py` imports it and `_outside_allowlist` has no
exemption for it** — A187. It was missing from this plan's first draft and Step 2 would have
failed.

Watch `test_every_package_is_classified` fail first, then classify. Ledger row.

- [x] **Step 3: The neutral graph**

```python
# dag_core/graph.py
@dataclass(frozen=True)
class Node:
    id: str
    label: str
    inputs: tuple[str, ...]      # port names, in order — the layout needs the COUNT and the row
    outputs: tuple[str, ...]

@dataclass(frozen=True)
class Edge:
    from_node: str
    from_port: str
    to_node: str
    to_port: str

@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
```

**Nothing here knows what a pipeline is**, which is the point: two adapters, one arithmetic.

- [x] **Step 4: Move the arithmetic**

`_ranks`, `_order`, `_x_of`, `_height`, `_declared` and the constants (`NODE_W`, `COL_PITCH`,
`HEAD_H`, `PORT_ROW`, `MIN_H`, `RANK_GAP`, `CORNER`) move to `dag_core/layout.py` **unchanged
except for reading `Graph` instead of `PipelineIR`**. `Point`, `Placed`, `Wire` and `Layout`
move with them. **`Ports` does not** — A188: it is
`Mapping[str, tuple[list[str], list[str]]]`, it describes a *pipeline's* ports, and it belongs
with the adapter that knows what a pipeline is.

Resist improving anything while moving it. A move that changes no behaviour is provable; a move
that also tidies is not.

- [x] **Step 5: The `PipelineIR` adapter stays in `mendel-compiler`**

`mendel_compiler/layout.py` becomes the adapter plus a re-export, so
`from mendel_compiler import layout; layout.of(ir, ports)` still works for
`mendel_api.services.build`:

```python
def of(ir: PipelineIR, ports: Ports | None = None) -> Layout:
    return dag_core.layout.of(_graph_of(ir, ports))
```

- [x] **Step 6: Prove the canvas did not move**

`uv run pytest packages/mendel-compiler/tests/test_layout.py -q` — the same count as Step 1,
all passing. Then `cd frontend && npx vitest run` for 3C's own canvas tests
(`src/build/Graph.test.tsx`, `geometry.test.ts`).

- [x] **Step 7: `make verify`**, because `mendel_compiler` was touched. Expected PASS, and the
  emitted digests unchanged.

- [x] **Step 8: Commit**

```bash
git add packages/dag-core packages/mendel-compiler pyproject.toml tests/test_purity.py CLAUDE.md notes/audits/guard-ledger.md
git commit -m "feat(dag-core): one layout, two callers"
```

### Task 2: Wiener lays out its own artifact

**Files:**
- Create: `packages/wiener-core/src/wiener_core/graph.py`,
  `packages/wiener-core/tests/test_graph.py`
- Modify: `packages/wiener-core/pyproject.toml`, `tests/test_purity.py` (allowlist gains
  `dag_core`)

**Interfaces:**
- Consumes: `comeni_core.artifact.pipeline.Pipeline`, `dag_core`.
- Produces: `graph_of(pipeline) -> Graph`, `coloured(layout, state) -> RunGraph`.

- [x] **Step 1: Write the failing test**

```python
def test_the_artifact_lays_out_without_an_ir():
    """§9.1.1: Wiener has a `Pipeline`, not a `PipelineIR`, and may not reach for the resolver
    that turns one into the other. The adapter is the whole reason `dag-core` takes a neutral
    graph."""
    pipeline = Pipeline.model_validate(yaml.safe_load(SPINE_YML.read_text()))
    laid = dag_core.layout.of(graph_of(pipeline))
    assert len(laid.placed) == len(pipeline.steps)
    assert laid.wires, "a five-step spine has wires"


def test_the_colouring_says_what_the_run_did_and_nothing_else():
    """A node's fill is its aggregate; a ring means a retry. Neither invents a number."""
    run = coloured(laid, replay(_events()))
    star = next(n for n in run.nodes if n.process == "STAR_ALIGN")
    assert star.done == 1 and star.total == 1 and star.attempts == 1
```

- [x] **Step 2: Run and watch it fail** — `No module named 'wiener_core.graph'`.

- [x] **Step 3: Write the adapter and the colouring**

`graph_of` reads `pipeline.steps` and `pipeline.channels`. `coloured` joins `RunState.tasks` by
process name onto the placed nodes and adds, per node: `done / total`, `failed`, `running`,
`attempts` (max over that process's tasks), and the phase colour token. **It computes no
duration and no rate** — §9.2.

- [x] **Step 4: `make check` and commit**

### Task 2a: The fold keeps what the record keeps — A184

**Files:**
- Modify: `packages/wiener-core/src/wiener_core/state.py`,
  `packages/wiener-core/tests/test_fold.py`,
  `packages/wiener-api/src/wiener_api/services/projection.py` (the `attempts` dump)

**Interfaces:** `Attempt` gains the per-attempt facts.

**Why this exists:** the audit above. Everything from Task 3 onward reads `RunState`, and
`RunState` currently has none of the fifteen fields Checkpoint 2 rescued into the record.

- [x] **Step 1: Write the failing test**

```python
def test_an_attempt_carries_what_the_trace_reported():
    """A184. `admit()` keeps the fifteen fields and the fold was dropping them, so everything
    downstream of RunState — spans, the §9.3 panel, run_task's attempts column — was blind to
    them. The record could be replayed to recover; a projection could not."""
    state = replay(_resourced_events())
    attempt = next(iter(state.tasks.values())).attempts[0]
    assert attempt.peak_rss_bytes and attempt.pct_cpu
    assert attempt.start_ms and attempt.complete_ms, (
        "a per-attempt span needs its own start and end — first_seen_ms and last_change_ms are "
        "per TASK, so a retried task's three spans would share one pair of timestamps"
    )


def test_a_trace_less_run_leaves_them_absent_rather_than_zero():
    """`failing-run.jsonl` was captured without `trace.enabled`. A zero would read as "this
    task used no memory", which is a lie about a real number."""
    attempt = next(iter(replay(_events()).tasks.values())).attempts[0]
    assert attempt.peak_rss_bytes is None
```

- [x] **Step 2: Run and watch both fail.**
- [x] **Step 3: Add the fields to `Attempt`** — `start_ms`, `complete_ms`, `duration_ms`,
  `realtime_ms`, and the resource fields from `TaskTrace`, all `| None`. Copy them in `fold`
  where the `Attempt` is built. **The keying stays `by_n`** (A176), so a redelivered body still
  replaces rather than appends.
- [x] **Step 4: Check the convergence property still holds** — `test_a_redelivered_event_does_not_invent_an_attempt` is
  what caught the `last_activity_ms` rewind, and it is the guard that will catch this one too if
  the copy is done wrong.
- [x] **Step 5: `projection.append`'s `attempts` dump carries them**, so `run_task` is a
  projection of the whole attempt rather than a quarter of it. Task 11 depends on this.
- [x] **Step 6: `make check` and commit.**

## ✋ CHECKPOINT 1 — the canvas did not move, and Wiener can draw

- [ ] `diff /tmp/layout-before.json /tmp/layout-after.json` — **empty**, pasted into the report.
- [ ] `make verify` green.
- [ ] **Report**: that the builder's canvas is unchanged, that `wiener-core` now lays out an
  artifact with no Mendel import, that an attempt now carries its own resources and timestamps
  (A184), and that nothing is on screen yet.

---

## Phase 3B — spans, pure

### Task 3: `Span`, and the CI/CD mapping

**Files:**
- Create: `packages/wiener-core/src/wiener_core/spans.py`,
  `packages/wiener-core/tests/test_spans.py`

**Interfaces:**
- Produces: `SpanKind`, `Span`, `spans(state: RunState, pipeline: Pipeline | None) -> list[Span]`.

**Read first:** the research note §1.2 and §1.4. Every attribute name and every enum value is
there. **Do not invent one.**

- [x] **Step 1: Write the failing tests, against both committed captures**

```python
def test_a_run_is_one_server_span_with_a_child_per_attempt():
    made = spans(replay(_events()), pipeline=None)
    run_span = made[0]
    assert run_span.kind is SpanKind.SERVER
    assert run_span.attributes["cicd.pipeline.run.id"] == "r1"
    assert all(s.parent is run_span.span_id for s in made[1:])
    assert all(s.kind is SpanKind.INTERNAL for s in made[1:])


def test_the_enum_mapping_is_the_note_s_table():
    """§1.4. A wrong value here is a dashboard that lies, and the two arguable ones are
    `LOST -> timeout` and `CACHED -> skip`."""
    assert result_of(RunPhase.FAILED) == "failure"
    assert result_of(RunPhase.LOST) == "timeout"
    assert task_result_of(TaskStatus.CACHED) == "skip"


def test_a_failed_span_carries_error_type():
    """Conditionally Required when the result is `failure` or `error`."""


def test_no_lab_string_becomes_an_attribute():
    """§8, and it covers the exporter and §10.2's redactor with one test. `trace.script`,
    `workdir`, `name` and `tag` are exactly the fields a backend would happily index."""
    for span in spans(replay(_events()), pipeline=None):
        for value in span.attributes.values():
            assert "/tmp" not in str(value) and "test -f" not in str(value)


def test_the_timestamps_are_the_events_own():
    """Research §3: spans are backdated, in nanoseconds, so replay produces identical
    telemetry and a three-day run maps in milliseconds."""


def test_spans_are_a_golden_file():
    """The mapping is as reproducible as the emitted `.nf` — same events in, same spans out."""
```

- [x] **Step 2: Run and watch them fail.**
- [x] **Step 3: Write `spans.py`.** `Span` carries `name`, `kind`, `span_id`, `parent`,
  `start_ns`, `end_ns`, `attributes: dict[str, str | int | float | bool]`. Ids are derived from
  `(run_id, task_id, attempt)` **deterministically** — a random id makes the golden file
  impossible and replay non-identical.
- [x] **Step 4: Golden file**, committed, over `failing-run.jsonl` and `resourced-run.jsonl`.
- [x] **Step 5: `make check` and commit.**

### Task 4: The six that have no convention

**Files:** modify `spans.py`, `tests/test_spans.py`

- [x] **Step 1: Write the failing test** — every one of the six from the note §2 present on a
  task span, with the exact names: `wiener.task.attempt`, `wiener.task.cpus_asked`,
  `wiener.task.cpu_used_pct`, `wiener.task.memory_asked_bytes`, `wiener.task.memory_peak_bytes`,
  `wiener.task.queue_wait_ms`, `wiener.task.read_bytes`, `wiener.task.write_bytes`,
  `wiener.task.cached`.
- [x] **Step 2: A test that the numbers are the trace's** — `queue_wait_ms` is
  `duration_ms - realtime_ms` and nothing else; `process.exit.code` is reused rather than
  renamed.
- [x] **Step 3: A test that a trace-less run degrades honestly** — `failing-run.jsonl` was
  captured without `trace.enabled`, so those attributes are **absent, not zero**. A zero would
  read as "this task used no memory".
- [x] **Step 4: `make check` and commit.**

## ✋ CHECKPOINT 2 — the mapping, before anything is sent

- [ ] Print the spans for the resourced capture and read them: `uv run python -c "…"`.
- [x] **Report**: the run span's attributes, one task span's attributes, and confirmation that
  no lab string appears in either. **Nothing has been exported and no container has been added.**

---

## Phase 3C — the export

### Task 5: The collector and the store, in compose

**Files:** modify `docker-compose.yml`, `docker-compose.prod.yml`, `tests/test_compose.py`,
`Makefile`

- [x] **Step 1: Add `otel-collector` and `clickhouse`** (or the SigNoz bundle §8 names) with
  healthchecks. **`test_the_stack_is_seven_services` will fail** — that is the guard working,
  and the same one that caught the Wiener services in phase 1. Update it, and check the prod
  overlay closes any port the base publishes: `test_prod_publishes_the_web_port_and_nothing_else`
  derives its list, so it needs nothing, but read it and confirm.
- [x] **Step 2: `docker compose config -q`** and bring the two up.
- [x] **Step 3: `make check` and commit.**

### Task 6: The exporter, and the five metrics

**Files:**
- Create: `packages/wiener-api/src/wiener_api/services/telemetry.py`,
  `packages/wiener-api/tests/test_telemetry.py`
- Modify: `packages/wiener-api/pyproject.toml`, `settings.py`, `services/projection.py`

**Interfaces:**
- Produces: `export(state, pipeline)`, `record_metrics(state)`, `settings.otlp_endpoint`.

- [x] **Step 1: Write the failing tests** — the SDK is stood in for; nothing in a test opens a
  socket. Assert that a terminal run exports one run span plus one per attempt, that a
  non-terminal run exports nothing (a span that has not ended cannot be sent), and that
  `settings.otlp_endpoint` empty means **no exporter is constructed at all** — off by default.
- [x] **Step 2: The five CI/CD metrics**, verbatim from the note §1.3:
  `cicd.pipeline.run.duration`, `cicd.pipeline.run.active`, `cicd.pipeline.run.errors`, and
  `cicd.system.errors`. `cicd.worker.count` waits for W5 — **write down that it is deliberately
  absent** rather than leaving a reader to wonder.
- [x] **Step 3: Wire it into the run's end**, in `projection.append`, after the flush and beside
  the stream publish — same reasoning: a span for an event Postgres has not accepted is telemetry
  that disagrees with the record.
- [x] **Step 4: A purity check you must run by hand**:
  `uv run pytest tests/test_purity.py -q` after adding `opentelemetry-sdk` to `wiener-api`.
  **Then deliberately import it in `wiener_core/spans.py` and watch the guard refuse it** —
  §3.1 predicted this exact payoff and it should be witnessed, not assumed. Ledger row.
- [x] **Step 5: `make check` and commit.**

## ✋ CHECKPOINT 3 — a real run's waterfall

- [ ] Submit the spine through the browser or `curl`, let it finish.
- [x] **Open the backend and find the trace.** One run span, five children, the timings matching
  the console.
- [x] **Report**: a screenshot or the trace id and its spans, how long after the run ended the
  trace appeared, and **whether any attribute in the backend contains a path or a sample name**
  — that is §8's rule checked where it matters rather than in a unit test.

---

## Phase 3D — the boards

### Task 7: Four boards, in the repo

**Files:** create `ops/boards/*.json` (or the backend's own format), `ops/boards/README.md`

- [x] **Step 1: Build them in the UI first, then export.** A board written by hand against a
  query language nobody has run is a board that renders empty.
- [x] **Step 2: The four** — §8.1's table: *is anything wrong now*, *where the time goes*,
  *where the capacity goes*, *what breaks*. **Keep the maximum, not the mean.**
- [x] **Step 3: `README.md` says how to import them**, in three lines, and says which one is
  useless until W5 (queue wait reads zero on `local`).
- [x] **Step 4: Commit.**

## ✋ CHECKPOINT 4 — the boards answer their questions

- [ ] With **at least three runs** in the store, one of them failed, open each board.
- [ ] **Report**: for each, the question it answers and whether it does — and specifically
  whether *where the capacity goes* shows the STAR_ALIGN peak against what was asked. If a board
  needs a number nothing emits, that is a finding for phase 3B, not a reason to fake it.

---

## Phase 3E — the graph view

### Task 8: The layout over HTTP

**Files:** modify `routes/runs.py`, `repository.py`, `tests/test_runs_routes.py`

- [x] **Step 1: Write the failing test** — `GET /api/runs/{id}/graph` returns placed nodes,
  wires and the per-node run state; 404 for an unknown run; and **the response contains no lab
  string**, for the same reason a span may not.
- [x] **Step 2: Implement**, reading the artifact's `pipeline.yml` from Wiener's own store.
- [x] **Step 3: `make client`** — both schemas regenerate.
- [x] **Step 4: `make check` and commit.**

### Task 9: The second view

**Files:** create `frontend/src/runs/Graph.tsx`, `Graph.test.tsx`; modify `Run.tsx`

**Read first:** `docs/design/wiener-mockups/Graph.dc.html`. **Do not invent the screen.**

- [x] **Step 1: Write the failing tests** — the toggle switches without a fetch (both views are
  the same state), a node shows `done / total`, a retried node draws a second ring, and a failed
  node uses `--undecided`.
- [x] **Step 2: Build it**, reusing 3C's pan/zoom and orthogonal routing rather than a second
  implementation — `frontend/src/build/`: `Canvas.tsx`, `useGraph.ts`, `geometry.ts` (A189,
  confirmed to exist rather than assumed). If that code is not reusable as it stands, **stop and say so** — a second
  canvas is exactly what `dag-core` exists to prevent.
- [x] **Step 3: Enable the `Graph` segment** in `Run.tsx`, which has been drawn disabled since
  phase 2, and delete the `aria-disabled`.
- [x] **Step 4: `npx vitest run && npx tsc -b`, `make check`, commit.**

### Task 10: An edge that is honest

**Files:** modify `Graph.tsx`, `Graph.test.tsx`

- [x] **Step 1: A live edge means active** — the consumer is running on what the producer wrote.
  Animate it.
- [x] **Step 2: A test that no rate is drawn.** §9.2: a pulse whose speed implies MB/s is a
  number nobody measured. The test asserts the animation's duration is a constant and not a
  function of any datum — **this is the guard for the rule that a graph may move but may not
  lie**.
- [x] **Step 3: A finished edge may carry its real weight**, from `read_bytes`/`write_bytes`,
  because then it is known.
- [x] **Step 4: Commit.**

## ✋ CHECKPOINT 5 — you watch a run as a graph

- [ ] Submit a run and **watch the graph while it executes**. Nodes fill, one edge moves, the
  counts climb.
- [ ] Switch to the console and back — **no fetch**, no flicker.
- [ ] **Report**: what twenty minutes of watching turns up. 3E's lesson stands.

---

## Phase 3F — the numbers on the run page

### Task 11: §9.3's four comparisons

**Files:** create `frontend/src/runs/Stats.tsx`, `Stats.test.tsx`; modify `Run.tsx`,
`routes/runs.py`

- [ ] **Step 1: Write the failing test** — per process, not per task: *STAR_ALIGN: 12 tasks,
  peak 61 GB of 64 requested, worst 6m41s*. **The outlier is kept and the mean is not shown.**
- [ ] **Step 2: A test for the absent case** — a run captured without `trace.enabled` must say
  *"resource metrics were not recorded for this run"* rather than rendering zeros. §4.3 finding
  6 is that the fields are opt-in, and a zero here is a lie about a real number.
- [ ] **Step 3: Implement**, aggregating in the API from `run_task`.
- [ ] **Step 4: `make check`, frontend tests, commit.**

### Task 12: The `More` panel

**Files:** modify `Run.tsx`, `Stats.tsx`

**Read first:** `wiener-mockups/Main.dc.html` — the header has a `More` control and the panel is
designed. Build what is drawn.

- [ ] **Step 1: Implement the expandable panel.**
- [ ] **Step 2: Commit.**

### Task 13: The journal, the plan's own record, and `CLAUDE.md`

- [ ] **Step 1: `notes/journal/2026-08-__-wiener-phase-3.md`** — what happened, what is next,
  what a fresh reader gets wrong.
- [ ] **Step 2: Fill the execution record** below with every deviation.
- [ ] **Step 3: Update `CLAUDE.md`'s Current state** — W1 complete, and what W2 is for.
- [ ] **Step 4: `make verify`, `make residue`**, and commit.

## ✋ CHECKPOINT 6 — W1 is done

- [ ] **`make verify`** green, and **`make residue`** — report the number and how many guards
  phase 3 added.
- [ ] **Walk the whole thing as a user**: build a pipeline in the Builder, gate it, submit it to
  Wiener, watch the graph, read the stats, open a board.
- [ ] **Report**: whether §18's W1 sentence is true — *a real pipeline runs on real data, you
  watch it finish, and its waterfall is already queryable* — and what is still wrong.

---

## Execution record

| Task | Deviation from the plan | Why |
|---|---|---|
| 1 | `_declared` and the `ports` parameter stayed in `mendel-compiler` rather than moving; `dag_core.of(graph)` takes no ports at all | A188 said `Ports` belongs with the adapter, and following that through means the *question* does too: a node carries its own ports and whoever built the graph decided whether they are the declared ones or the wired ones. `dag-core`'s allowlist has no `comeni_core`, which is the check that the split is real |
| 1 | `Placed.tier` and `Wire.type_id` keep their names in the shared package | Renaming them to something neutral would change the JSON the canvas already reads, and "the canvas did not move" is this task's whole safety net. Both mean something on each side — Mendel puts the resolution tier there, Wiener puts the tier the step's decision was settled at |
| 1 | One line changed in `test_layout.py` | `_port_x` moved with the arithmetic, so the import moved. **No assertion changed**, and the count is 13 before and 13 after |
| 2 | A third capture was committed: `tests/fixtures/weblog/spine-run.events.jsonl` | The colouring cannot be tested against the two existing fixtures — one is a two-task failure and the other a toy `GREET` pipeline, and **neither shares a process name with the spine**. This is a real run of this exact artifact, seventeen events, exported from Postgres |
| 2a | The fold **merges** attempts rather than replacing them | Found by writing the test the plan asked for and then asking what else could rewind. Only `process_completed` carries the resources, so a redelivered `process_started` erased them — **and the loss is invisible**, because an absent field is also what a run without `trace.enabled` looks like. Reproduced, then fixed: a field a later event reports wins, a field it leaves empty keeps what was known, and a status never rewinds out of a terminal one |
| 9 | 3C's `Canvas`, `useView` and `geometry` are reused; **`Node` is not** | `Node` is an editor node — selection, dragging, wire-drag, settings, verdicts — and a run node shows different facts. Reusing it would mean passing a dozen no-op props and a `Step`. The *layout* is shared, which is what `dag-core` exists for; the renderer differs because the two views say different things about the same shape |
| 9 | **Entry channels are not drawn**, and the mockup draws them | `Graph.dc.html` shows `fastq.reads` and `genome.fasta` as chips feeding the first nodes. A run graph is *coloured by what happened*, and a channel never runs — it has no tasks, no state and nothing to colour. The builder shows inputs because you are assembling; this shows what executed. Recorded rather than silently dropped |
| 9 | The view lives in the URL — `?view=graph` | A link to a failing graph is the thing somebody pastes into a message. It also makes "switching is a render, not a fetch" testable |
| 10 | The rate guard was watched failing | Making the pulse faster for more bytes — the tempting version — gives `expected '2s' to be '0.9s'`. §9.2 says a pulse whose speed implies MB/s is a number nobody measured, and that is now a test rather than a paragraph |
| 7 | The boards were authored as JSON and **each query verified against real data** rather than built in a UI and exported | The plan says build them in Grafana first, and this session cannot click. So every panel's SQL was run against ClickHouse before it went in a board, and then all eleven were re-run through the provisioned boards: **10 of 11 returned rows, and the eleventh was empty for a reason** |
| 7 | The Grafana mount was wrong and nothing was provisioned | `ops/grafana` was mounted onto `provisioning/datasources`, so the dashboard provider was never read — the log says *"starting to provision dashboards / finished"* with nothing between, and the search returns nothing. The whole `provisioning` tree is mounted now |
| 7 | **`errorStrategy` was missing, so `* task.attempt` was decoration** | Found by the one empty panel: nothing in any run had ever reached attempt 2, because the emitted config has no retry. A task killed for memory would ask for the same amount again, forever. nf-core pairs the two and so does this now — same citation, and it is what makes the OOM-retry story real |
| 7 | Every panel gained a `noValue` sentence | **Silence and breakage look identical**, and a reader cannot tell which they are seeing. *"Nothing has needed a second try"* is good news; *"No queue wait recorded — it reads zero on the local executor"* is an explanation rather than a gap |
| CP3 | **A run was two traces, and only ClickHouse could see it** | The SDK invents a random trace id for a span with no parent context, so the run span landed in a trace of its own while the five task spans shared the derived one — and their `ParentSpanId` pointed at a span that did not exist. One lone `RUN` and five orphans, which is the shape of failure that looks like it works. **Every unit test stubbed `_emit`**, so they asserted what Wiener intends rather than what the SDK produces. A `_DerivedIds` generator fixes it; the guard that catches it runs the real provider into an in-memory exporter |
| CP3 | The first version of that guard was **vacuous** and I caught it by reverting | It built its own `TracerProvider` with `_ids` attached, so removing the generator from the real one changed nothing and it still passed. `build_provider()` exists so the test constructs the subject rather than a copy of it — and reverting now gives `a run must be ONE trace: assert 2 == 1` |
| 5 | **No containers were added.** The telemetry backend is pointed at, not composed | **SigNoz deprecated its bundled Compose files in v0.130.0** and installs through Foundry — a CLI that renders and runs its own stack rather than composing into somebody else's. Vendoring the deprecated manifest would mean running an unmaintained copy of another project's stack to preserve one-file tidiness. §8 already said the backend is *named but not depended on*, and the operator's steer was that production is Kubernetes anyway, so this is that sentence being used rather than bent. `ops/telemetry/README.md` is how to run one; `WIENER_OTLP_ENDPOINT` is the whole integration |
| 5 | ClickHouse, the collector and Grafana **are** in compose, behind a `telemetry` profile | Backed out once and restored on the operator's decision: SigNoz is more locked-in, and its Compose is deprecated anyway. A profile is the third option between "three containers on every `make dev`" and "a second compose file that drifts" — `make telemetry` brings them up, and two guards hold it: the default stack is still seven services, and nothing in it depends on something that does not start |
| 5 | **The Dockerfile did not know about `dag-core`** and every image build was broken | Introduced in Task 1 and invisible to `make check`, which never builds an image. Found by `make telemetry` pulling the api build in: `Distribution not found at: file:///app/packages/dag-core`. The three new packages are copied now |
| 6 | `_id_of` lives in `wiener-api`, not in the pure core | The purity guard refused `hashlib` in `wiener-core` earlier, and refused the SDK here. So the pure half names a span `<run>.<task>.<attempt>` — legible in a golden file — and this side turns that into the eight bytes the wire wants. **A cost of the split, recorded rather than hidden** |
| CP2 | **The record did not survive being read back**, and the checkpoint is what found it | `run_event.payload` is written with `model_dump()`, which uses FIELD names, and `TaskTrace` validated by ALIAS only — so reading the record back turned every aliased field into `None`, and `extra="ignore"` swallowed the evidence. §7.1's *"run_event is the source of truth and everything else is a projection"* was false for nine fields of fifteen. **It hid because `cpus`, `read_bytes` and `write_bytes` have no alias**: a span carried three of the nine and looked merely sparse rather than broken. Found by printing the spans and asking why one number was missing — which is what a checkpoint is for. `populate_by_name=True`, and a test that round-trips a real event |
| 3 | **A190 was decided rather than deferred a third time**: `cicd.pipeline.name` is derived from `goal.want` — `counts.matrix` for the spine | It blocks the mapping and the operator said keep going. Derived beats the digest because every board groups by this and a digest starts a new series on every rebuild, which makes *"is the spine getting slower"* unanswerable across exactly the change you want to measure. The cost is that two pipelines producing the same thing collide, and the fix for that — a submitter-supplied name **defaulting to this** — is an added field rather than a changed one, so nothing here has to move |
| 3 | `_span_id` is a readable composite, not a hash | The purity guard refused `hashlib` in `wiener-core` and was right to: OpenTelemetry ids are eight bytes on the wire, and meeting a wire format is the exporter's job. The pure half says *which* span |
| 4 | A structural test was added: `test_the_fold_is_where_the_lab_strings_stop` | **Found by trying to break the string-sniffing one.** Sabotaging `spans()` to emit `process.command_line` failed with *`TaskState` has no attribute `script`* — the marked fields live on `TaskTrace` and the fold keeps `process` rather than `name`, so nothing a span can reach is a lab string. §8's rule is enforced by construction, and this test is what keeps it that way when somebody adds `script` to `TaskState` for the console |
| 2a | `projection.append`'s attempts dump needed no change | It is `a.model_dump(mode="json")`, so the new fields ride along. Checked rather than assumed |

---

## What this plan does not do

- **No auth, no multi-tenancy, no hosting.** It is a docker compose. Scope after the MVP —
  the operator's instruction, 2026-08-24, and `lab_id` stays server-chosen until there is a
  principal to derive it from.
- **No AI.** W3, and the right-hand column stays absent rather than stubbed.
- **No verbs.** W4 — the console still says `read-only until W4`.
- **`cicd.worker.*` and queue wait stay empty**, because there is no cluster until W5. Build the
  view; expect zero.
- **The ingest app is still unserved in compose** — a carried gap from phase 1, named in that
  plan's record. Phase 3 adds two containers and would be a natural place to fix it, but it is a
  topology decision (§13.1's loopback claim depends on the ingest app sharing a container with
  whatever spawns Nextflow) and it is the operator's to make.
