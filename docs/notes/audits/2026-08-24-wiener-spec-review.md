# The Wiener spec, read end to end — A175–A183

**2026-08-24.** Against [`docs/design/wiener.md`](../../design/wiener.md) (1049 lines) and
[`notes/plans/2026-08-23-wiener-w1-phases-0-2.md`](../plans/2026-08-23-wiener-w1-phases-0-2.md)
(12 tasks, 85 steps), **before Task 1**.

**Why it ran.** [`journal/2026-08-23-wiener-designed.md`](../journal/2026-08-23-wiener-designed.md)
says so itself, under *what a fresh reader gets wrong*: **"the spec was reviewed" — it was not.**
The operator answered seven design questions and read summaries; nobody had read the document end
to end. It names §12.1 and the tenancy guard as the two places most likely to be wrong, and both
are on this list.

**Method.** Read the spec in full, then check each claim it makes about existing code against the
code. Nothing here was found by reading the plan alone — every finding below is either a claim the
repository contradicts, or an internal disagreement between two sections that only shows up when
both are in the same head.

**What it did not do.** No line of Wiener exists, so nothing here was found by running it. That is
the same limitation the design audit named on 2026-08-14: *revert and watch* cannot be run against
a design. Findings A175, A176 and A177 are the ones most likely to have a sibling that only
execution finds.

---

## The findings

| | What | Where | Severity |
|---|---|---|---|
| A175 | The heartbeat has no `EventKind`, so `RunPhase.LOST` has no producer | spec §6.1 · §10.1 · §5; plan Task 2 | **critical** |
| A176 | The idempotence argument does not cover the duplicate it cites; `attempts` appends unconditionally | spec §5.1 · §6.3; plan Task 3 | **critical** |
| A177 | The tenancy guard checks a different sentence than §7.1 states, and three common query forms pass it untouched | spec §7.1; plan Task 5 step 6a | **critical** |
| A178 | `lab_id` has no authenticated source in phases 0–2 | spec §12.1 · §7.1 | major |
| A179 | Nothing produces the artifact the courier carries | spec §12; plan Task 8 | major |
| A180 | The branch claimed `make check` green while lint was red | journal 2026-08-23 | major |
| A181 | §3.1 names a constant that does not exist | spec §3.1 | minor |
| A182 | §5 marks lab strings with `Mark.LAB_STRING`; the plan does not, and is right | spec §5; plan Task 2 | minor |
| A183 | The failure signature carries `exit` twice | spec §10.1 | minor |

---

### A175 — the heartbeat has no `EventKind`, so `LOST` has no producer

**§6.1 is explicit**: *"The heartbeat is itself an **event** that `wiener-api` appends on a timer;
the fold sees `HEARTBEAT(at_ms=…)` exactly as it sees a task completing."* §10.1 depends on it —
it is what lets the chat panel answer *is this normal* rather than only *what broke* — and §17's
`LOST` decision (*absence of events, generous window*) has no other clock-free trigger, because
§6.1 forbids `wiener-core` from reading a clock at all.

**`EventKind` has exactly six members**, in spec §5 and again in plan Task 2, and §4.4 says an
unknown `event` kind is **refused with a diagnostic** rather than ignored. So as written:

- nothing can construct a heartbeat that `fold()` will accept;
- `RunPhase.LOST` (plan line 523) is a declared phase with no producer — the exact shape of
  [#69](https://github.com/comeni-project/Comeni-Labs/issues/69)'s `AiProvenance.available`, and of
  `OpenQuestion.suggested` before Plan 3D, both of which were consumers with no producer that
  nobody noticed until a screen needed them.

**It costs nothing to fix now and a type migration later**, because Task 2 is where `EventKind` and
`admit()` are frozen and Task 3 folds against them.

**The fix has a second half worth stating.** A heartbeat is **authored by Wiener, never by
Nextflow**, so `admit()` must refuse `HEARTBEAT` *from the network* while `fold()` accepts it from
the timer. Otherwise anything that reaches the ingest endpoint can forge liveness on a run — which
matters less than it sounds because §13.1 puts that endpoint on loopback behind a per-run secret,
and matters anyway because *"which events may an external party author"* is a distinction that
belongs in the allowlist rather than in a reviewer's memory. That is §4.4's own argument.

### A176 — the idempotence argument does not cover the duplicate it cites

> **It was worse than this finding first said, and the worse half was found while fixing it.**
> `attempts` is appended on **every trace event**, not once per attempt — and a task that runs
> once is described by *three* events, `process_submitted`, `process_started` and
> `process_completed`. So every ordinary task ended with three attempts and §9.1's *"a second
> ring means something retried"* would have drawn a retry ring on a run where nothing retried.
> The duplicate-delivery case below is the same bug reached from a rarer direction.
> `test_a_retry_is_history_rather_than_an_overwrite` asserted `len(attempts) >= 1`, which is
> true of three, so the plan's own test would have watched it happen and passed.
>
> **Measured, not argued.** Both folds were executed against
> `tests/fixtures/weblog/failing-run.jsonl` by extracting the plan's own code blocks — no
> Wiener package exists yet, so this is the only way to run it before Task 1:
>
> ```
> ORIGINAL fold, attempts per task: {1: 3, 2: 3, 3: 3}
> attempt numbers on task 1:        [1, 1, 1]
> the plan's own assertion len >= 1: True   <- passes
>
> CORRECTED fold, attempts per task: {1: 1, 2: 1, 3: 1}
> phase failed · counts succeeded=2 failed=1 · redelivery with a fresh seq: converges
> a heartbeat before `started`: queued · terminality regardless of order: failed
> ```
>
> Three tasks, none retried, each carrying three identical attempts. That is A14's shape in a
> plan rather than in a guard: a test that could only pass.


**§5.1 says:** *"Idempotent by construction, not by defence. `event.seq <= state.last_seq` returns
`state` unchanged, which makes finding 2 a one-line property rather than a special case for
`completed`."*

**It does not.** Finding 2 is that Nextflow sent `completed` **twice, with byte-identical
payloads** — two POSTs. §6.2 says `seq` is *assigned by `wiener-api` as bodies arrive*, so the
second copy gets a **higher** `seq` and the guard does not fire. What `seq <= last_seq` protects
against is re-delivery of an already-recorded event during replay, which is a different thing.

The capture's duplicate happens to be harmless: `terminal_seen` is a `frozenset`, so folding
`completed` twice is genuinely idempotent — **by the set, not by the seq**. The spec attributes the
property to the wrong mechanism, and the corpus property `replay(events) == replay(events + events)`
(§6.3) passes only because the appended copies carry their **original** `seq`.

**Where it bites is `process_completed`.** Plan Task 3, line 599:

```python
attempts = (*prior.attempts, attempt) if prior else (attempt,)
```

Nothing in the capture says Nextflow will not duplicate a task event the way it duplicated
`completed`. If it does, the task grows a **second attempt that never happened** — §5.1's *"retries
are history"* becomes *retries are invented*, the console draws a retry ring on a task that ran
once, and `counts` disagrees with `workflow.stats` (§4.3's free gift, which is a field read).

**Fix:** key attempts by `(task_id, attempt)` and treat a repeat as a replace rather than an
append; and add a corpus property that duplicates a `process_completed` **with a fresh `seq`** —
which is what arrival over HTTP actually looks like — rather than only re-appending the list.

### A177 — the tenancy guard checks a different sentence than the spec states

**§7.1 states a mechanism:** *"the guard is not 'remember the filter' — **every query goes through
a session scoped to one `lab_id`**, and a test asserts no query builder in `wiener-api` constructs
a `select()` on these tables without it."*

Those are two different controls, and the plan builds only the second. Task 5 step 6a greps the AST
for `select(...)` calls, and **three of the most likely ways to write a real query pass it
untouched**:

| form | why it slips through |
|---|---|
| `session.get(Run, run_id)` | not a `select()` call at all — and it is the obvious way to write `GET /api/runs/{id}` |
| `sa.select(Run)` | `node.func` is an `ast.Attribute`, and the check reads `node.func.id`, which is `""` |
| `select(Run.id)` | the argument is an `ast.Attribute`, and the `SCOPED` membership test reads `.id` on it |

Plus two weaknesses in the part that does fire: the window is `lineno … lineno+3`, so a `.where()`
on the fifth line is a false positive and **any** mention of `lab_id` in those four lines — a
comment, an adjacent statement — satisfies it; and `src = ast.get_source_segment(...)` is computed
and never used, which is the trace of a check that was replaced by a line-window and not
re-thought.

This is the guard the journal already flagged as *"easy to write so that it passes for the wrong
reason"*, and it does two things wrong at once: it passes **vacuously** at Task 5 (no queries yet,
which the plan honestly records), and it will keep passing at Task 6 for queries it cannot see.

**The structural options, cheapest first:**

1. **A repository module.** Every query lives in `wiener_api/repository.py`, whose functions all
   take `lab_id`. The guard becomes *no `select`, `session.get` or `session.query` appears outside
   that module* — a rule about **where**, which an AST scan checks reliably, rather than about the
   shape of an expression, which it does not.
2. **A SQLAlchemy `with_loader_criteria` on the session**, so the filter is applied by the session
   rather than by the author. This is literally §7.1's sentence.
3. **Postgres row-level security.** Strongest and the only one that survives a raw `text()` query;
   also the most operational cost, and it needs a per-request role.

Any of the three makes the guard non-vacuous **at Task 5**, before there is anything to leak.

### A178 — `lab_id` has no authenticated source in phases 0–2

§12.1 makes authentication a **W1 requirement** and the plan does not satisfy it; the journal names
that gap, and this finding is its consequence rather than a repeat of it. **A tenant column whose
value the client supplies is not a boundary.** Phases 0–2 have no authenticated principal, so
whatever fills `lab_id` comes from the request or from nowhere.

**Fix, and it is one line:** `lab_id` comes from `settings` — server-chosen, one laboratory per
deployment, exactly the restraint the plan already applies to `artifact_root` and that
`mendel_api.services.gates._directory` applies to paths. Nothing in phases 0–2 then teaches the
codebase that a client may name its own lab, which is the habit that would have to be un-taught
later.

### A179 — nothing produces the artifact the courier carries

**§12 is the boundary argument**: the browser copies the gated pipeline directory into Wiener's own
store, *"so `mendel-api` still never learns Wiener exists — which keeps `execution-boundary.md`
§9's rejection of a Mendel→Wiener API intact rather than quietly bending it."*

**`mendel-api` cannot serve that directory.** There is no `FileResponse`, no `StreamingResponse`
and no download route anywhere in the package — `keep` writes files under `MENDEL_DRAFT_ROOT` and
nothing reads them back out over HTTP. Plan Task 8 accordingly tests an upload with a fixture zip,
and Checkpoint 2's happy path is:

```bash
( cd /tmp/spine && zip -r /tmp/spine.zip . )
A=$(curl -sF bundle=@/tmp/spine.zip localhost:8001/api/artifacts | jq -r .artifact_id)
```

That is **fine for phases 0–2** — one operator, one laptop, and the plan says so. What is not fine
is that §18's W1 row promises *the user sees one button*, and the button needs a route on the
Mendel side that nobody has scheduled. Name it the way authentication is named, or add the route to
phase 3, but do not let it be discovered by whoever builds the button.

### A180 — the branch claimed `make check` green while lint was red

`docs/design/wiener-mockups/build.py` landed in `aa7bdfe` with **47 `E501`s**. The journal entry
three commits later (`62ba318`) reports *"`make check` green (1510)"*. It was not: `make check`
runs `lint` **first**, so the suite that produced 1510 could not have run in the same invocation.

Recorded here rather than absorbed, because it is A14's shape in a new place — **a claim of green
that nobody watched being made**. Fixed on 2026-08-24 by scoping `E501` off that one path in
`ruff.toml`; the code rules (`E`, `F`, `I`, `UP`, `B`, `SIM`) still apply to it.

### A181 — §3.1 names a constant that does not exist

*"one entry in `tests/test_purity.py`'s `PURE_PACKAGES`"*. There is no `PURE_PACKAGES`. The
constants are `CLOSED_PACKAGES`, `BANLIST_PACKAGES` and `IMPURE_PACKAGES`, and **the plan gets this
right** (Task 1 step: *add to `CLOSED_PACKAGES`*). A spec that names the wrong constant is how
plan 18a's *three criticals from one root* happened — a plan written against what the code
resembles.

### A182 — `Mark.LAB_STRING` in the spec, a local sentinel in the plan

Spec §5 writes `Annotated[str, Mark.LAB_STRING]`, which reads as `comeni_core.spell.marks.Mark`.
Plan Task 2 instead defines `LAB_STRING = "lab-string"` inside `wiener_core`. **The plan is right**:
widening `comeni-core`'s `Mark` pulls in `test_every_mark_carries_a_validator_or_is_listed_as_a_label`
and the egress accounting invariant 14 keeps, for a marking that never crosses a Mendel door. Make
the spec say so.

One caution on the plan's version: a **bare `str`** as `Annotated` metadata is a weak sentinel —
any other `Annotated[str, "lab-string"]` collides with it, and §10.2 leans on the marking hard
(*"an implementation that drops marked fields cannot miss one that was added later — adding a
marked field without handling it fails the totality test"*). A one-line sentinel class or a
`StrEnum` member costs nothing and cannot be spelled by accident.

### A183 — the failure signature carries `exit` twice

§10.1: a signature is `(process, exit, error_class)`, where `error_class` is *"derived from fields
the capture proves are present — `status`, `exit`, `error_action`"*. `exit` is already the second
element, and `status` is `FAILED` for everything that produces a signature at all, so
`error_class` carries `error_action` and nothing else. Either say the signature is
`(process, exit, error_action)`, or give `error_class` a definition that is not a function of the
tuple it sits in.

---

## What this review did not find

Stated because a review that reports only hits is a review nobody can calibrate.

- **The event model holds.** Six kinds, the trace's fields, the two terminal events and their
  ordering were all checked against `tests/fixtures/weblog/failing-run.jsonl`, and the document
  describes that file accurately. §4.3's five corrections are real and the capture supports each.
- **`layout.py` exists** and §9.1's claim that Wiener needs no second layout engine is true.
- **The `mendel-ai` → `ai-core` rename is as small as §3.2 says** — 1061 lines and five importers,
  all in `mendel-forge`.
- **The purity extension is sound.** `wiener-core` folding events has no legitimate socket, and the
  OTel-exporter argument for it is genuine rather than decorative.
- **The ingest endpoint's separation (§13.1) is the right shape**, and it names the Plan 3A phase 6
  defect it is avoiding.

---

## Disposition — all nine, closed into the plan and the spec on 2026-08-24

Closed **before Task 1**, which is the whole reason the review ran when it did: every one of
these was cheaper as a paragraph than as a migration.

| | Where it landed |
|---|---|
| A175 | Plan Task 2 — `EventKind.HEARTBEAT`, `FROM_NEXTFLOW`, `heartbeat()`, `MW0002`, and two tests. Spec §4.1 and §5 |
| A176 | Plan Task 3 — attempts keyed by `trace.attempt`, the corrected docstring, and two tests: one for the fresh-`seq` redelivery, one asserting a task that ran once carries **one** attempt. Spec §5.1 and §6.3 |
| A177 | Plan Task 5 — `repository.py`, and a guard about **where** a query lives rather than what it looks like. Spec §7.1 |
| A178 | Plan Task 5 — `settings.lab_id`, server-chosen, with the replacement path named. Spec §7.1 |
| A179 | Plan's closing section and spec §12 — named as a gap, with the Mendel-side route it needs |
| A180 | Fixed: `ruff.toml` scopes `E501` off the mockup builder. `make verify` green |
| A181 | Spec §3.1 — `CLOSED_PACKAGES` |
| A182 | Plan Task 2 — a sentinel class rather than a bare string. Spec §5 |
| A183 | Spec §10.1 — the signature is `(process, exit, error_action)` |

**A175 and A176 each grew a second half while being fixed**, and that is the part worth
carrying forward. A175's was that a `HEARTBEAT` in the stream makes `_phase` return `RUNNING`
for a run that never started, because the original read *any event seen* as *the run is going*;
it now reads `started_at_ms`. A176's is in the box above. Neither was visible from reading the
finding — both appeared on contact with the code the finding was about, which is the argument
for fixing a finding rather than filing it.
