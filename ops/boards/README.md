# Execution dashboards

These Grafana dashboards query the traces and metrics stored by the local ClickHouse exporter.
Their JSON definitions are committed so query and display changes can be reviewed.

| Dashboard | Questions answered | Data |
|---|---|---|
| [wrong-now.json](wrong-now.json) | How many runs are active, what failed, and how did completed runs end? | Active/error metrics and completed run spans. |
| [time.json](time.json) | Which processes take longest, and how much time is outside execution? | Attempt span durations and queue-wait attributes. |
| [capacity.json](capacity.json) | What CPU and memory were requested and used, and which steps perform I/O? | Resource and I/O attributes on attempt spans. |
| [breaks.json](breaks.json) | Which processes fail, with which exit codes, and which are retried? | Attempt results, exit codes and attempt numbers. |

## Provisioning and ownership

`make telemetry` starts Grafana with these files mounted at `/etc/grafana/boards`.
[Dashboard provisioning](../grafana/dashboards/wiener.yml) loads them into the Wiener folder;
[data-source provisioning](../grafana/datasources/clickhouse.yml) creates the
`wiener-clickhouse` data source. Manual import is unnecessary for the local stack.

Grafana permits UI edits, but those edits do not update the committed JSON. Export reviewed
changes back to this directory and reload the provisioned dashboards. These files use Grafana
format and ClickHouse SQL; another telemetry backend needs its own queries and views.

## Query contracts

Trace panels read `otel.otel_traces`; metric panels read `otel.otel_metrics_sum`. Queries use
CI/CD attributes, `process.exit.code` and the `wiener.task.*` attributes defined in
[the span builder](../../packages/wiener-core/src/wiener_core/spans.py). The
[exporter](../../packages/wiener-api/src/wiener_api/services/telemetry.py) defines active-run,
run-duration and error metrics.

Keep query names and units aligned with those sources. Review both when changing an attribute
or the exporter schema. The current resource attributes cover attempt/cache status, CPU,
requested and peak memory, I/O and inferred queue wait. They do not include a sample-name field.

Timing panels show median, p95 and maximum duration. Resource panels retain maxima, and queue
wait displays its maximum beside its mean. Run summaries also use average duration, while I/O
panels sum transferred bytes. Preserve these distinctions when editing aggregation: a mean
cannot describe the largest resource requirement.

Every panel has an empty-data message. Treat it as guidance for missing results, and check
export and backend health before interpreting it as evidence that no run failed or is active.

## Interpreting measurements

Attempt spans are exported after a run reaches a terminal state. Live execution does not yet
appear in the trace-based timing, capacity and failure panels. The active-run panel uses a
separate metric; see [telemetry setup](../telemetry/README.md) to enable export.

Queue wait is calculated as recorded duration minus execution time, when both are present.
Local execution may produce zero; this value does not independently identify scheduler wait.
Missing attributes are omitted by the exporter, but current SQL conversions can turn missing
values into zero. A displayed zero can therefore mean missing measurement data.

Requested resources reflect values reported by Nextflow after any configured resource limits.
Several processes can report the same memory ceiling on one machine. Peak memory, CPU and I/O
need execution trace data; the Wiener launcher enables tracing for its runs.
