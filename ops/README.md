# Operations configuration

These files configure the browser's reverse proxy and the optional local telemetry backend.
Service definitions and mounts live in [docker-compose.yml](../docker-compose.yml);
[docker-compose.prod.yml](../docker-compose.prod.yml) supplies production overrides.

| Configuration | Consumer | Responsibility |
|---|---|---|
| [postgres/](postgres/README.md) | Shared PostgreSQL server and migration tooling | Initialize isolated application roles/databases, verify cutover from legacy servers and document rollback. |
| [nginx/default.conf](nginx/default.conf) | Browser image, copied by [frontend/Dockerfile](../frontend/Dockerfile) | Serve the browser app and route API requests to Mendel and Wiener, including run WebSockets. |
| [otel/collector.yaml](otel/collector.yaml) | `otel-collector` | Receive OTLP traces and metrics, batch them and write them to ClickHouse. |
| [grafana/datasources/clickhouse.yml](grafana/datasources/clickhouse.yml) | Grafana provisioning | Configure the ClickHouse data source used by the dashboards. |
| [grafana/dashboards/wiener.yml](grafana/dashboards/wiener.yml) | Grafana provisioning | Load dashboard definitions from `/etc/grafana/boards`. |
| [boards/](boards/README.md) | Grafana, mounted from Compose | Define run status, timing, resource capacity and failure dashboards. |
| [telemetry/](telemetry/README.md) | Maintainers | Backend startup, explicit Wiener export setup, retention and troubleshooting. |

## Local telemetry

From the repository root, run `make telemetry` to start ClickHouse, the collector and Grafana.
Compose provisions the data source and dashboards from this directory. The default host
addresses are `http://localhost:4317` for OTLP and `http://localhost:3001` for Grafana;
`OTLP_HOST_PORT` and `GRAFANA_HOST_PORT` change the published ports.

Starting the backend does not enable Wiener export. Its `WIENER_OTLP_ENDPOINT` setting defaults
to empty, which constructs no exporter. Configure the endpoint in the exporting process's
environment. The current Compose definitions do not pass this variable to Wiener services.
A host process can reach the default collector at `http://localhost:4317`; a process on the
Compose network uses `http://otel-collector:4317`.

Wiener retains application run records in PostgreSQL. ClickHouse stores telemetry separately,
with a 30-day TTL configured in the collector. Changes to dashboard queries must agree with
the attributes emitted by [Wiener's telemetry adapter](../packages/wiener-api/src/wiener_api/services/telemetry.py).

## Configuration changes

Rebuild the browser image after changing nginx configuration; it is copied into the image.
Collector and Grafana configuration is mounted from the checkout. Restart the affected service
to load changes, and verify dashboards against recorded telemetry.

For application startup and service addresses, see the
[local stack guide](../docs/how-to/development/local-stack.md) and
[service reference](../docs/reference/development-services.md).

## Application deployment

Development ports bind to `127.0.0.1`, including optional wiki and telemetry services.
An empty `WIENER_API_TOKEN` disables run-management authentication only for local development.
Set a nonempty token before `make prod`; the production overlay refuses an empty value.
Production also requires `POSTGRES_ADMIN_PASSWORD`, `MENDEL_DB_PASSWORD` and
`WIENER_DB_PASSWORD`; the application passwords must use only letters, digits, `_` and `-`.
Configure the same token in the browser's execution settings.

`make prod` prepares the writable registry clone and runtime directories before building.
It retains registry, workspace and draft mounts while loading Python code from the image.
Only the web service publishes a production host port, including when optional profiles are
selected. `WEB_HOST_PORT` defaults to 80 and `WEB_BIND_ADDRESS` to `0.0.0.0` in production;
use `127.0.0.1` when an external reverse proxy handles public access. Provision TLS at that proxy.

Use Docker Compose 2.24.4 or newer for the overlay's volume replacement tags, and BuildKit
for dependency cache mounts. `DOCKER_UID` and `DOCKER_GID` select both the worker runtime
identity and the image's Nextflow cache owner. Rebuild after changing them.
Host artifacts under `var/wiener/`, runtime data, credentials and caches are excluded from
image build contexts; `.env` variants are also ignored by Git, apart from example files.

Before starting an existing installation with the shared database server, follow the
[PostgreSQL cutover guide](postgres/README.md). Make refuses startup when legacy Compose
volumes exist without a verified migration record for the current target volume.
