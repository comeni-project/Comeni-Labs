# Plan 6 — what the run page still owes its artboard

**Written after** rebuilding `/runs/{id}` against `.design/RunView.dc.html` on 2026-09-01
(commit `b0bb5f4`). The bands landed; three things on that artboard did not, and each was left
out for a *stated* reason rather than forgotten. This plan is those three reasons, checked
against the code, and what it takes to close them.

**Read the artboard first**, and its annotations — they are the specification and they already
answer several questions this plan would otherwise re-litigate:

```bash
python3 -c "import json; [print(a['text']) for a in \
  json.load(open('.design/canvas.json'))['annotations'] if a['page']=='page-5']"
```

**The three are independent and are ordered by what they teach**, not by size. Phase 2 is the
smallest and can land alone; phase 3 is the one the artboard calls blocked and is not; phase 1
is a door this repository has deliberately kept shut and should be opened last, deliberately.

---

## What the research found, before any of it is planned

Four facts changed the shape of this plan. Each is written here rather than inside a task,
because each is the sort of thing a reader will otherwise assume the opposite of.

**1. Cancel is not a button — it is W4's whole door.** `docs/design/wiener.md` §11 defines a
**closed verb vocabulary**, and cancel is one of five: `cancel`, `relaunch`, `retry task N`,
`pause`, `apply`. Every one is a typed `Intent` that `requires: approval by a named human` and
carries an audit line — *who · when · why · prior phase · resulting run id*. §11 also says this
is *"the surface that deserves the hardest audit in Wiener"*, and that the vocabulary is what
makes the audit finite: **a reviewer checks a list of verbs, not a sanitiser.**

**2. The launcher cannot cancel anything, because it kept nothing to cancel.**
`launcher.py:110` is `subprocess.Popen(argv, cwd=cwd)` and line 179 is `_spawn(argv,
cwd=workdir)` — the handle is discarded on the same line it is created, and no `pid` column
exists on any model. This is not a small gap in phase 1; it is most of phase 1.

**3. The pipeline name is not missing. It is dropped at the courier.**
`mendel_api.models.PipelineDraft.name` is a `String(200)` that has existed since Plan 3E, and
`Pipeline` and `Goal` both have none. So the name a person typed in the builder exists, and
`GET /api/pipeline/drafts/{id}/bundle` → Wiener's upload is where it stops being carried. That
makes this a *courier* question, not a schema question — unless we want CLI-built artifacts to
have names too, which is the fork phase 2 has to take deliberately.

**4. The timeline's data already exists.** `page-5`'s own annotation lists it under **"BLOCKED,
FAKE, OR NOT YET PROJECTED"** — *"They are inside `run_task.attempts` but are not projected as
columns"* — and that is exactly right and no longer a blocker:
`wiener_core.state.Attempt` carries `start_ms` and `complete_ms`, and
`projection.py:142` writes every attempt into `run_task.attempts` as JSON. **Nothing needs to
be measured, admitted or migrated to draw the timeline.** What is missing is a query path and a
component. That is the same shape as the `tag` column added earlier today, and it should be
solved the same way.

---

## Phase 1 — cancel, and the door it opens

*The largest, and the one to do last. It is the first verb Wiener has ever had, and §11 says
the vocabulary is what makes the audit finite — so the machinery matters more than the verb.*

**Do not ship a bare `POST /runs/{id}/cancel`.** It would work, and it would pre-empt the design
that says every verb is a typed `Intent` with an approver and an audit row. The second verb
would then be built against the first one's shortcut. Cancel is the right verb to open with for
the reason §11 gives — *"the only one that needs no artifact"* — and that is an argument for
building the machinery under the cheapest verb, not for skipping it.

### 1.1 The launcher keeps what it spawned

- [ ] `RunProcess` — or a column on `run` — holding the **pid, the start time, and the host**.
      A pid alone is not an identity: pids are reused, and killing a recycled one kills
      somebody else's process. The start time is what makes the pair unique.
- [ ] `_spawn` returns its `Popen` and the caller records it. Today the handle is discarded on
      the line it is made.
- [ ] **The host matters and this is why**: `docs/design/wiener.md` §12.1 records that the
      worker holds the host Docker socket. A cancel arriving at an API replica that did not
      spawn the run has no process to signal. Decide and write down whether cancel is
      *replica-local* (refuse when the host does not match) or goes through a queue. Refusing
      loudly is the correct MVP answer and must say so in the response.
- [ ] A guard: a launched run records a pid; a run whose recorded pid no longer names the same
      process is reported as **gone**, not as cancellable.

### 1.2 `Intent`, approval and audit — §11

- [ ] `IntentKind` and `Intent` in **`wiener-core`**, which already declares them in the design
      (§88: `decide(RunState) -> list[Intent]`, *"returns typed intents, never performs them"*).
      Check whether they exist in code before writing them; the design has carried them since
      W1 and the fold may already have the type.
- [ ] `run_intent` — the audit row. §11's five fields exactly: **who, when, why, prior phase,
      resulting run id**. `resulting run id` is null for cancel and non-null for relaunch, which
      is why the column exists now rather than when relaunch arrives.
- [ ] **`who` is authentication here, not attribution**, and that is a break with
      `mendel_api.models`'s `who` (which its own docstring calls attribution from
      `git config user.name`). §11 says *approval by a named human*. Until accounts exist,
      `WIENER_API_TOKEN` is the only boundary — so the honest MVP records the token's identity
      and the plan must not pretend otherwise. **`submitted_by` is hardcoded `"operator"`** and
      `page-5` already calls that out as decoration; do not add a second one.
- [ ] Cancel is refused on a terminal run, and the refusal names the phase.

### 1.3 The phase actually moves

- [ ] **Who writes `cancelled`?** The fold derives phase from events, and a cancel is not
      something Nextflow emits. Two options, and the plan must pick one in writing:
      **(a)** synthesise an admitted event so the record stays the source of truth and
      `state_of` replays a cancel exactly like anything else; **(b)** write the phase on the row
      and accept that the projection and the record now disagree.
      **(a) is correct** — §7.1 is *"`run_event` is the source of truth and everything else is a
      projection"*, and (b) makes a replayed run forget it was cancelled.
- [ ] Killing the head process leaves containers running. Nextflow traps `SIGTERM` and cleans
      up; `SIGKILL` does not. **Send `SIGTERM`, wait, and report what is still up** rather than
      claiming a clean stop.
- [ ] A guard driven against a real `-stub-run`: cancel mid-run, assert the phase becomes
      `cancelled` **and** that a replay of the events reaches the same phase.

### 1.4 The screen

- [ ] The Cancel control, in the header where the artboard draws it, on non-terminal runs only.
- [ ] **The three `read-only until W4` strings come down** — they are in `Run.tsx` and they will
      be false. Grep for the phrase; it appears three times.
- [ ] Confirmation before it fires. It is the first destructive control in Wiener.

### 1.5 Checkpoint

- [ ] A real run cancelled from the browser, its phase `cancelled`, an audit row naming who and
      why, and no orphaned containers — or a truthful line saying which ones survived.

---

## Phase 2 — the pipeline name, across the courier

*The smallest of the three, and it starts with a fork that decides how small.*

### 2.1 Pick where the name lives

- [x] **(a) On the upload request.** The browser is the courier (`docs/design/wiener.md` §12,
      A179) and it already holds the draft; it posts the name beside the bundle. `RunArtifact`
      gains a `name` column. **Small, no schema break — and a `mendel build` artifact uploaded
      by hand still has no name**, which is the hole.
- [x] **(b) On `Pipeline`.** Every artifact carries its own name, including CLI builds and
      air-gapped ones, and `mendel emit` round-trips it. **`SCHEMA_VERSION` 6→7, which is a
      break for `comeni-core`** — `docs/guides/releasing.md` says a schema bump always is.
- [x] **Recommendation: (a) first, and only (a).** The name is a *label somebody chose in a
      builder*, and the artifact is the thing that must be byte-reproducible from a goal — a
      name is exactly the sort of free text that has no business changing a content digest.
      Note in `Pipeline`'s docstring that its absence is deliberate, so (b) is a decision
      somebody makes rather than a gap somebody fills.

### 2.2 Carry it

- [x] The bundle endpoint or the upload call sends the draft's `name`; `RunArtifact` stores it;
      `/runs` and `/runs/{id}` return it.
- [x] **A name is free text a person typed**, so it is displayed and never interpreted. It is
      not a lab string in the §8 sense — it names a pipeline shape, not a sample — but it is
      user-authored, so it must not reach a span attribute or a log line without the same care.
      Write that distinction down where the column is declared.
- [x] Absent is absent: an artifact uploaded without a name shows `run <id>`, which is what the
      page does today. **No name derived from a digest**, which would be a name nobody chose.

### Execution record — 2026-09-01

| step | what actually happened |
|---|---|
| 2.1 | **(a) as recommended, and the fork was not close.** Written up on the column itself rather than only here, so the next person meets the argument where the decision lives. |
| 2.2 | `artifact_names()` is a **separate statement**, not a widened `pipeline_digests()`. The latter filters `pipeline_digest IS NOT NULL` on purpose — a pre-2026-08-30 upload must show under *every run without a pipeline* — and folding names in would have made that filter silently swallow names too. Still one statement per page. |
| 2.2 | **The name is attached beside `RunState`, never folded into it.** A name came off the upload and is not in the events; a field on the pure type that no event can produce is how a projection stops being replayable from its record. A test asserts `name` is not in `RunState.model_fields`. |
| 2.2 | `upload()` gained an optional `fields` argument — multipart, not a query string, following the standing rule about what never goes in a URL. |
| 2.2 | **The browser already had the name and never sent it.** `usePipelineDraft` exposes `name` and its own header records that `PipelineDraft.name` has existed since 3E with nothing setting it. Four props of wiring, no new query. |
| — | The header keeps the **id beside the name** rather than replacing it: the id is what a person pastes into a message, and two runs of one pipeline share a name. Not in the plan; found while writing the guard. |

### 2.3 Checkpoint

- [x] A pipeline named in the builder, run through Wiener, and its name in the run header and
      the board — and a `mendel build` artifact uploaded by hand still reading `run <id>`
      without an error anywhere.

---

## Phase 3 — the timeline

*The band the artboard draws and the page does not have. **Its data is already in the
database**; treat any task here that talks about measuring or admitting as a mistake.*

### 3.1 A pure verb, beside the three that exist

- [x] `lanes(state, declared) -> Lanes` in **`wiener-core`**, the fourth of its shape after
      `overview()`, `spans()` and `series()` — and it inherits invariant 1 for free, which is
      the argument §3.1 already made for the others.
- [x] **A lane is a process, in the order the artifact declares it** — the annotation is
      explicit, and it is the same rule that gives `overview()` a row before the run reaches it:
      *"The chart's height is known before the first event."*
- [x] **Sub-rows are concurrency, greedily packed** — a finished row is reused. Above roughly
      40 concurrent the stack stops and the remainder becomes a **density band**. Never 5,000
      rows.
- [x] **Colour is status, never process.** The lane already carries identity. The annotation
      records that the first draft coloured by process and *"a finished STAR task was
      indistinguishable from a running one."*
- [x] **A retry is a separate bar in the same lane.** `Attempt` is per-attempt precisely so the
      try that asked for more memory is visible; collapsing them loses the only interesting
      thing.
- [x] **No clock inside the fold.** `series()` already carries this rule and it is load-bearing
      here too: a running attempt has no `complete_ms`, and closing it at `now` inside a pure
      function breaks §6.1's *same events in, same decisions out*. The **renderer** extends an
      open bar to the right edge, exactly as the envelope does.

### 3.2 The query path

- [x] The windows are in `run_task.attempts` (JSON) and `/runs/{id}/tasks` pages at 100. So
      either **three derived columns** — the A191 move, and the one the `tag` column made
      earlier today — or a **dedicated endpoint** over the pure verb, the `/series` move.
- [x] **Recommendation: the endpoint.** A191's columns exist so a *table* can `ORDER BY`; the
      timeline needs every attempt of every task at once and orders by nothing. `/series` is
      the precedent and `page-5` names both options without choosing.
- [x] **A board is a query, not a fold in the request** — A191. Check what `/series` actually
      does before copying it: if it replays events per request, that is a cost this endpoint
      inherits and the plan should say so rather than discover it under a 5,000-task run.

### 3.3 The band

- [x] `Timeline.tsx`, between the panels and the envelope, sharing the envelope's x-axis —
      `curve.ts` already establishes that time is the comparison that matters and each series
      keeps its own y.
- [x] **Drill down in place**: clicking a lane filters the tasks table below it. The annotation
      is explicit — *"Never a second page for the same run"* — and the tasks band already takes
      a `process` filter, so this is wiring, not a new capability.
- [x] **A stepped, exact drawing and no interpolation**, for the reason `curve.ts` records: a
      scan already refuses a bezier, and a bar chart of windows must not grow a smoother.

### Execution record — 2026-09-01

| step | what actually happened |
|---|---|
| 3.1 | `lanes()` takes `(task_id, process, attempts)` rows, **not a `RunState`** — the shape `series()` established and for its reason. The first draft passed no `task_id` and every bar would have been unidentifiable, which kills 3.3's drill-down; caught while writing the packing. |
| 3.2 | **The endpoint, as recommended.** `task_windows()` is a wider query than `attempts_of()` rather than a replacement: the envelope reads only attempts and adding two columns would make it carry what it does not read. |
| 3.2 | `test_wiener_openapi.py` refused the new route until it was named in its literal list. That guard working. |
| 3.3 | Drill-down is a **callback**, not a filter the band applies: the timeline reports which lane was picked and the page decides. An empty lane is deliberately not clickable — filtering to nothing reads as *this process has no tasks* when the truth is *it has not started*. |
| — | **`make dev` runs the Python APIs from a baked image with no source mount and no `--reload`.** The endpoint 404'd in the browser while green in tests, and `docker compose up -d --build wiener-api` was the fix. Same class as the stale dev registry found this morning: the running stack not reflecting the source. Not fixed here — recorded, because it will cost the next person the same twenty minutes. |
| — | An SVG `<text>` has no `.click()` in jsdom. `fireEvent.click` instead. |

### 3.4 Checkpoint

- [x] A real multi-sample run — the fan-out fixture is two samples and `--gate test` produces
      more — with a lane per process, a bar per attempt, a retry visible as its own bar, and a
      click filtering the table beneath.
- [x] A run with one task and a run with none both draw something honest.

---

## What this plan does not do

**No `relaunch`, `retry`, `pause` or `apply`.** Phase 1 builds the machinery those need and
deliberately ships one verb over it. Adding a second in the same plan is how a vocabulary
becomes a pile.

**No sample axis.** Asked and answered on 2026-09-01: the artboards refuse it twice in writing,
and `launcher.py:120` refuses to hold a samplesheet in any table, so a sample lane cannot have
a height known before the first event. The `tag` filter shipped instead.

**No `submitted_by`.** `page-5` lists it as hardcoded `"operator"` — *"wire it or leave the
column out until accounts land. Do not ship a filter that filters nothing."* Phase 1.2 touches
the same nerve and must not quietly half-fix it.
