# Telemetry for a run — which conventions genuinely fit

**2026-08-24.** The research `docs/design/wiener.md` §17 asks for, before phase 3 writes its
first span. The operator's instruction was **"research them before inventing `wiener.*`
attributes"**, on the argument that mapping onto real conventions is what makes off-the-shelf
dashboards and alerting work — and that *conventions that half-fit are worse than clean custom
names*.

**The headline is that the premise was half right, and the half that is wrong is the more
useful half.**

- **There is no batch-job or workflow convention, and there has not been one for five and a
  half years.** [`opentelemetry-specification#1347`](https://github.com/open-telemetry/opentelemetry-specification/issues/1347)
  — *Semantic conventions for batch jobs* — was opened on **15 January 2021** and is still open,
  unassigned, with no milestone and no maintainer conclusion. The messaging conventions were
  used for batch work early on and are documented as a poor fit. **Waiting for this is waiting
  for nothing.**
- **The CI/CD conventions do exist, are Release Candidate, and fit a Nextflow run almost
  exactly.** A pipeline that runs named tasks, each of which succeeds or fails, on workers, is
  the same shape. That is the mapping to adopt.

---

## 1. What exists, exactly

Taken from the specification rather than from memory. Everything below is **Release Candidate**
unless marked otherwise, which matters: RC means the names are settled enough to build on and
not yet frozen.

### 1.1 Resource attributes — [`resource/cicd`](https://opentelemetry.io/docs/specs/semconv/resource/cicd/)

| attribute | requirement | what Wiener puts in it |
|---|---|---|
| `cicd.pipeline.name` | Required | the artifact's pipeline name |
| `cicd.pipeline.run.id` | Required | `run.id` — Wiener's own opaque id |
| `cicd.pipeline.run.url.full` | Recommended | `/runs/{id}` |
| `cicd.worker.id` · `cicd.worker.name` · `cicd.worker.url.full` | Required / Recommended | **not emitted in phase 3.** One local executor is one worker and saying so adds nothing; it becomes real in W5, where a node is a fact worth grouping by |

### 1.2 Spans — [`cicd/cicd-spans`](https://opentelemetry.io/docs/specs/semconv/cicd/cicd-spans/)

**The run** is a span of kind `SERVER`, named `{action} {pipeline}`, and `cicd.pipeline.action.name`
has exactly three legal values — `BUILD`, `RUN`, `SYNC` — of which **`RUN` is the honest one**.

| attribute | requirement |
|---|---|
| `cicd.pipeline.result` | Required |
| `cicd.pipeline.action.name` | Opt-In |
| `error.type` | Conditionally Required when the result is `failure` or `error` |

**Each task attempt** is a span of kind `INTERNAL`, a child of the run span:

| attribute | requirement |
|---|---|
| `cicd.pipeline.task.name` | Required |
| `cicd.pipeline.task.run.id` | Required |
| `cicd.pipeline.task.run.result` | Required |
| `cicd.pipeline.task.run.url.full` | Required |
| `error.type` | Conditionally Required as above |

The first three are to be set **at span creation**, so a sampler can see them. Wiener creates
spans after the fact, so this costs nothing — but it is the reason the mapping is a pure
function of `RunState` rather than something assembled as events arrive.

### 1.3 Metrics — [`cicd/cicd-metrics`](https://opentelemetry.io/docs/specs/semconv/cicd/cicd-metrics/)

| instrument | type | unit | required attributes |
|---|---|---|---|
| `cicd.pipeline.run.duration` | Histogram | `s` | `cicd.pipeline.name`, `cicd.pipeline.run.state` |
| `cicd.pipeline.run.active` | UpDownCounter | `{run}` | `cicd.pipeline.name`, `cicd.pipeline.run.state` |
| `cicd.pipeline.run.errors` | Counter | `{error}` | `cicd.pipeline.name`, `error.type` |
| `cicd.worker.count` | UpDownCounter | `{worker}` | `cicd.worker.state` |
| `cicd.system.errors` | Counter | `{error}` | `cicd.system.component`, `error.type` |

The VCS group (`vcs.change.*`, `vcs.ref.*`) is in the same document and is **not** Wiener's:
a pipeline run has no pull request.

### 1.4 The enums, and how Wiener's own vocabularies map onto them

This is the part worth getting right, because a wrong enum value is a dashboard that lies.

`cicd.pipeline.result` ∈ `success`, `failure`, `error`, `timeout`, `cancellation`, `skip`

| `RunPhase` | maps to | why |
|---|---|---|
| `SUCCEEDED` | `success` | |
| `FAILED` | `failure` | the pipeline ran and something in it failed |
| `CANCELLED` | `cancellation` | W4 |
| `LOST` | `timeout` | **the closest true value.** A run Wiener stopped hearing from did not fail — nothing said so — and it did not error, because Wiener did not break. It ran out of time to speak, which is what `timeout` means. Recorded here because the choice is arguable |
| a launcher that could not start | `error` | Wiener broke, not the pipeline. That distinction is the whole reason both values exist |

`cicd.pipeline.run.state` ∈ `pending`, `executing`, `finalizing` — `QUEUED` and `LAUNCHING` are
both `pending`, `RUNNING` is `executing`, and `finalizing` goes unused rather than being given a
meaning it does not have.

`cicd.pipeline.task.run.result` has the same six values as the pipeline result:

| `TaskStatus` | maps to |
|---|---|
| `COMPLETED` | `success` |
| `FAILED` | `failure` |
| `CACHED` | **`skip`** — the task did not run, which is exactly what `skip` says |
| `ABORTED` | `cancellation` |
| `SUBMITTED` · `RUNNING` | no span is closed yet; there is no result to report |

`cicd.pipeline.task.type` ∈ `build`, `deploy`, `test`. **None of those is what `STAR_ALIGN`
is**, so the attribute is omitted. It is Opt-In, so omitting it is legal, and inventing a
fourth value would be the "half-fitting convention" the operator warned against.

### 1.5 One convention Wiener may reuse, and one it must refuse

`process.exit.code` (RC) exists and is exactly Nextflow's `trace.exit` — reuse it rather than
inventing `wiener.task.exit`.

`process.command`, `process.command_line` and `process.command_args` also exist, and Wiener
**must not fill them**. `trace.script` is marked `LAB_STRING`, and §8's rule is that nothing
marked lab-string becomes a span attribute. **The convention offers a field the design forbids
filling**, which is worth writing down: adopting a convention is not the same as adopting every
field in it.

---

## 2. What has no convention at all, and therefore stays `wiener.*`

Searched and not found: **peak memory, and requested-versus-used anything.**
[`system/process-metrics`](https://opentelemetry.io/docs/specs/semconv/system/process-metrics/)
defines `process.memory.usage`, `process.cpu.utilization`, `process.disk.io` and eleven others,
all of them *current* readings sampled by an agent — and Wiener has no agent inside the task. It
has one post-hoc report per attempt, and the numbers it cares about are **comparisons**.

So these are custom, deliberately, with the names kept boring:

| `wiener.*` | from the trace | why there is no standard for it |
|---|---|---|
| `wiener.task.attempt` | `attempt` | retries are history (§5.1) and nothing standard carries an attempt index |
| `wiener.task.cpus_asked` / `wiener.task.cpu_used_pct` | `cpus` / `%cpu` | the *pair* is the point; no convention pairs a request with a use |
| `wiener.task.memory_asked_bytes` / `wiener.task.memory_peak_bytes` | `memory` / `peak_rss` | **there is no peak-memory convention anywhere.** This is the OOM story before the OOM |
| `wiener.task.queue_wait_ms` | `duration - realtime` | on a cluster this is the number that explains a slow run, and nothing standard expresses it |
| `wiener.task.read_bytes` / `wiener.task.write_bytes` | `read_bytes` / `write_bytes` | `process.disk.io` is a metric, not a span attribute, and this is a finished total |
| `wiener.task.cached` | `status == CACHED` | `skip` says it on the result; this makes it filterable without parsing a result |

**Six custom attributes, and every one of them is a fact no convention has a name for.** That
is the bar the operator set, and it is a much shorter list than the first draft of §8 implied.

---

## 3. What makes this possible at all: spans may be backdated

**`spans(RunState) -> list[Span]` only works if a span can be created with timestamps in the
past**, because Wiener maps a run *after* its tasks finished, and replays a three-day run in
milliseconds.

The OpenTelemetry API supports it explicitly: `start_span` takes a `start_time` and `Span.end`
takes an `end_time`, both integer **nanoseconds since the Unix epoch**, and the OTLP wire format
carries them as such. Nothing rejects a timestamp in the past.

Two consequences worth planning around:

- **Replay produces identical telemetry.** The same events fold to the same `RunState`, which
  maps to the same spans with the same timestamps. That is invariant 10's shape reaching the
  telemetry, and it means a backend can be rebuilt from the record after a retention window
  drops it — which is §8's *"the lens, never the system of record"* being literally true rather
  than aspirational.
- **A backend may reject or reorder very old data.** Ingestion windows are a real operational
  limit, and a replay of a month-old run is exactly the case that hits one. Phase 3 should
  discover the limit rather than assume it, and it does not affect live runs.

---

## 4. What this domain already tracks, and where Wiener differs

Seqera Platform — the commercial Nextflow control plane — surfaces CPU, memory, job duration
and I/O per process, **each shown both raw and as a percentage of what was requested**, and
feeds that history into *per-process resource recommendations* for the next run.

Two things follow.

**The asked-versus-got framing is the domain standard, not a Wiener invention.** §9.3 arrived at
it independently and it is what practitioners already read. Building anything else would be
building something people have to learn.

**Where Wiener differs is what it does with the history, and that difference is the product.**
A recommendation engine emits a number somebody either trusts or ignores. §14's loop turns the
same history into a **proposal into the forge queue** — a signature, a count, and the resource
ceilings involved — which a named human approves into a rule or a contract that is versioned,
cited and visible in a diff. Same input, and the output is reviewable rather than opaque. That
is W6, and this research is what tells us the input is worth keeping now.

---

### 4.1 The comparison is with the wrong product, and the operator said so

Everything above measures a **run**, which is what a run manager measures, and this document
spent a section benchmarking against one. **That is one part of Comeni Labs and not its
objective.** The claim the product is held to is *same goal in → same pipeline out, and nothing
was guessed silently* — Mendel decides and records why; Wiener is Lab Y, one half of a whole
that also has a Lab Z. A telemetry design scoped to *what Tower shows* would make Wiener a
worse Tower, which is a competition worth losing.

**The statistic nobody else can compute is outcome by provenance**, and the reason is
structural: no other platform records *why* a value is what it is, so no other platform can ask
whether the reasons were any good.

`pipeline.yml` is in the artifact Wiener owns, `Pipeline` is a `comeni-core` type, and
`comeni-core` is the one package both halves share (§3.3). So Wiener can read a run's decisions
**without touching Mendel at all** — which is what that shared package is for, and why it keeps
the platform name rather than the product's.

What that buys, in attributes on the task span, all of them declared data and low cardinality:

| attribute | from | the question it answers |
|---|---|---|
| `comeni.decision.tier` | `Why.tier`, `DecisionRecord.tier` | **do tier-3 decisions fail more often than tier-2 ones?** If a rule-matched choice breaks more than a documented default, the rule tables are wrong — and that is a claim about the engine, measured |
| `comeni.decision.source` | `Why.source` / `resolved_by` | resolver, rule, human, model — A130's question from the other direction: does a value a *model* chose behave like one a person chose? |
| `comeni.contract.id` | the step's pinned contract | which contract's steps fail, across every laboratory that runs it. That is the registry's own error rate |
| `comeni.registry.layer` | `Why.from_layer` | does an overlay's displacement make things better or worse than the base it replaced? |
| `comeni.override` | `human_override` / `model_override` | did overriding help? The one honest test of a flagged tier-4 answer |

**None of those is a run statistic.** They are statistics about *decisions*, keyed by the thing
that made them, and each one closes a loop the product already claims to care about and
currently cannot check.

**It is also the input §14 needs.** A failure signature recurring across runs becomes a forge
proposal; a failure signature recurring *on one contract, at one tier, from one layer* is a
proposal that says which rule to change. Same mechanism, and the difference between "STAR_ALIGN
fails sometimes" and "the rule that sets its memory is wrong above 3 Gb".

**This does not have to ship in phase 3, and saying so is the honest part.** Unlike the fifteen
trace fields — which are gone forever if `admit()` drops them — telemetry is **regenerable**:
spans are a pure function of `RunState` and the artifact, both of which are kept, and §3 says a
backdated span is legal. So decision labels can be added later and back-filled by replaying the
record. Phase 3 should carry them because they are nearly free once the artifact is open, not
because there is a cliff.

## 5. What to build, in order

**Phase 3 emits, and does not aggregate.** Every number below is derivable in the backend from
spans plus the five CI/CD metrics; a bespoke aggregation in Wiener would be a second
implementation of what ClickHouse is for.

1. **`spans(RunState) -> list[Span]`, pure, in `wiener-core`** — the run span, one child per
   attempt, the mapping tables above. Held by a golden test over the two committed captures, so
   the mapping is as reproducible as the emitted `.nf`.
2. **The exporter in `wiener-api`** — OTLP, self-hosted, off by default. Invariant 1 is what
   keeps the SDK out of `wiener-core`, and this is the payoff §3.1 predicted.
3. **The five CI/CD metrics**, verbatim. `cicd.pipeline.run.active` is §2's fleet level, which
   had no mechanism before.
4. **The four comparisons on the run page** (§9.3), read from the fields Checkpoint 2 rescued.
5. **`wiener.task.queue_wait_ms` as its own view** — it is the number that explains a slow run
   on a cluster and it is invisible until W5 has one, so build the view and expect it to read
   zero on `local`.

### 5.1 Dashboards, and what each answers

| dashboard | answers | built from |
|---|---|---|
| **Is anything wrong now** | active runs by state, failures in the last day, runs gone `lost` | `cicd.pipeline.run.active`, `cicd.pipeline.run.errors` |
| **This run** | the run page — built in phase 2 | the projection and the tail |
| **Where the time goes** | per-process duration and queue wait, p50/p95/max | task spans |
| **Where the capacity goes** | asked versus used, per process, worst case kept | the six `wiener.*` attributes |
| **What breaks** | exit codes per process over time, retries, repeat signatures | `process.exit.code`, `wiener.task.attempt` |

**Keep the maximum, not the mean** — §9.3 already says it and it is the single most important
display rule here: the maximum is what kills a run and the mean is what hides it.

### 5.2 The one thing to watch: cardinality

A 400-task run makes 400+ spans, and a task span carries a process name and an attempt index —
both low-cardinality and safe. What would *not* be safe is anything per-sample: `trace.name` and
`trace.tag` carry the sample tag, and §8 already forbids them as span attributes for privacy.
**That prohibition is doing double duty as a cardinality control**, and it is worth knowing both
reasons before somebody proposes an exception for one of them.

---

## 6. What this closes and what it leaves

**Closes** §17's last open question: the conventions to adopt are CI/CD, the mapping is §1.4, and
the custom set is the six in §2 rather than a `wiener.*` namespace invented wholesale.

**Leaves open**, and neither blocks phase 3:

- **`cicd.worker.*` in W5.** A worker is a node, and there is no node until something runs on a
  cluster. The attributes are already named; nothing has to be redesigned to start emitting them.
- **The backend.** §8 names SigNoz on the strength of one store for traces, logs and metrics.
  Wiener speaks OTLP, so this is a compose-file decision and not an architectural one — and the
  research above says nothing that changes it.

## Sources

- [CI/CD spans](https://opentelemetry.io/docs/specs/semconv/cicd/cicd-spans/) ·
  [CI/CD metrics](https://opentelemetry.io/docs/specs/semconv/cicd/cicd-metrics/) ·
  [CI/CD resource](https://opentelemetry.io/docs/specs/semconv/resource/cicd/) ·
  [CI/CD attribute registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/cicd/)
- [Process attribute registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/process/) ·
  [Process metrics](https://opentelemetry.io/docs/specs/semconv/system/process-metrics/)
- [`opentelemetry-specification#1347` — semantic conventions for batch jobs, open since 2021](https://github.com/open-telemetry/opentelemetry-specification/issues/1347)
- [Seqera Docs — understanding task resource metrics](https://docs.seqera.io/nextflow/tutorials/metrics) ·
  [Seqera Docs — run details](https://docs.seqera.io/platform-cloud/monitoring/run-details)
