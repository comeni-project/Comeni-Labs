# Execution telemetry

Wiener exports execution traces and metrics over OTLP/gRPC when `WIENER_OTLP_ENDPOINT` is set.
The optional local backend receives them through an OpenTelemetry collector, stores them in
ClickHouse and displays them in Grafana. Wiener stores application run records in PostgreSQL.

## Start the local backend

From the repository root:

```bash
make telemetry
```

This starts `clickhouse`, `otel-collector` and `grafana` through the Compose `telemetry` profile.
Docker with Compose is required; startup may pull their images. Grafana automatically loads the
ClickHouse data source and the [committed dashboards](../boards/README.md).
The local profile enables anonymous Grafana access with the Admin role and uses the `otel`
ClickHouse account configured in Compose, the collector and Grafana provisioning.

| Endpoint | Default host address | Override |
|---|---|---|
| OTLP/gRPC collector | `http://localhost:4317` | `OTLP_HOST_PORT` |
| Grafana | `http://localhost:3001` | `GRAFANA_HOST_PORT` |

The collector also listens for OTLP/HTTP on port 4318 inside the Compose network. Compose
publishes only its gRPC port, and Wiener's exporter uses gRPC.

## Enable Wiener export

Export is disabled when the endpoint is empty. For a Wiener process running on the host,
set the variable in its environment before starting it:

```bash
export WIENER_OTLP_ENDPOINT=http://localhost:4317
```

Use the configured host port if `OTLP_HOST_PORT` was changed. For Wiener services in Compose,
the collector address is `http://otel-collector:4317`.

The current Compose files do not forward `WIENER_OTLP_ENDPOINT` to Wiener. Exporting it in the
host shell alone will not enable container export. Add it to the exporting services through a
local Compose override, for example:

```yaml
services:
  wiener-ingest:
    environment:
      WIENER_OTLP_ENDPOINT: http://otel-collector:4317
  wiener-api:
    environment:
      WIENER_OTLP_ENDPOINT: http://otel-collector:4317
  wiener-worker:
    environment:
      WIENER_OTLP_ENDPOINT: http://otel-collector:4317
```

The event receiver records normal execution transitions; API actions and worker recovery can
also record terminal transitions. Apply the override with the same Compose files used to start
those services, and recreate them to load the environment. Restart a host process after changing
its endpoint; settings and exporters are initialized in the process.

The current exporter uses an insecure gRPC connection and exposes no exporter authentication
settings. An alternative receiver must support that connection, or sit behind a compatible local
collector. This repository supplies the local ClickHouse/Grafana backend; other receivers need
separate deployment configuration and views. The dashboard JSON is specific to Grafana and
ClickHouse's OTLP tables.

## What arrives and when

Wiener updates the active-run metric when a run enters and leaves the running state. It exports
run and attempt spans after a terminal transition, using recorded timestamps. Each retry is a
separate attempt span. Duration and error metrics are recorded on completion.

Trace-based timing, capacity and failure panels therefore describe finished runs. Missing trace
measurements remain absent in span attributes. Export failures are logged; the telemetry store
is separate from the application record.

The [collector configuration](../otel/collector.yaml) batches traces and metrics, creates the
ClickHouse schema and sets a 720-hour retention TTL. It includes no sampling processor.
ClickHouse data persists in the `wiener-clickhouse` Docker volume.

## Check and stop the backend

Inspect service logs from the repository root:

```bash
docker compose --profile telemetry logs --tail=100 otel-collector clickhouse grafana
```

Check the exporting Wiener process's logs and environment as well. Empty Grafana panels can
mean no matching data, a disconnected exporter or a backend/query failure; their placeholder
messages alone do not establish which condition occurred.

To stop only the telemetry services while retaining their stored data:

```bash
docker compose --profile telemetry stop grafana otel-collector clickhouse
```

See the [operations index](../README.md) for configuration ownership and service mounts.
