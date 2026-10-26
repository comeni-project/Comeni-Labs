# wiener-core

`wiener-core` is the pure domain layer for recorded pipeline runs. It admits Nextflow events,
folds them into deterministic state, decides typed policy intents, and derives graph, timeline,
resource, overview, signal, and telemetry views. It performs no database, network, process, or
clock I/O; `wiener-api` owns those effects.

## How to use it

Use `events.admit()` at the trust boundary, then pass the resulting `RunEvent` values to
`state.replay()` or incrementally to `state.fold()`. Supply the folded state to the relevant
projection (`overview`, `series`, `timeline`, `graph`, or `spans`). Pass an explicit `now_ms` to
`policy.decide()` and let an outer adapter perform any returned intents.

For the application-level run workflow, see [Running a pipeline](../../docs/how-to/pipelines/run.md).

## Reference

| Module | Contract |
| --- | --- |
| `events` | Closed event types and admission of the allowed Nextflow payload fields. |
| `state` | Idempotent event fold, run/task/attempt state, and projection restoration. |
| `policy` | Pure policy decisions represented as typed intents. |
| `overview` | Per-process status and worst-case resource summaries. |
| `series` | Exact reservation/count curves and explicitly derived throughput curves. |
| `timeline` | Deterministic process lanes and bounded concurrency packing. |
| `graph` | Pipeline-to-DAG adapter and run-state colouring. |
| `spans` | Pure OpenTelemetry-shaped span descriptions; exporting belongs to `wiener-api`. |
| `signals` | Conservative signal names derived from exit codes, without causal guesses. |

## Design and boundaries

The same admitted event sequence must produce the same state, decisions, and projections.
Clocks are arguments, effects are returned as data, missing measurements remain absent rather
than becoming zero, and inferred curves are labelled separately from exact ones. See
[Package boundaries](../../docs/explanation/package-boundaries.md) and
[Repository invariants](../../docs/explanation/invariants.md) for the wider architecture.

## Verification

Run the package suite with:

```console
uv run pytest -q packages/wiener-core/tests
```

The tests include recorded Nextflow fixtures plus direct boundary cases for replay,
redelivery, terminal-event precedence, partial pipeline graphs, resource semantics, and pure
telemetry mapping.
