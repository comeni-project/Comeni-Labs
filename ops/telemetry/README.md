# Where the telemetry goes

**Wiener speaks OTLP and nothing else.** The backend is named in `docs/design/wiener.md` §8 and
depended on nowhere — it is a thing you point at, not a thing this repository composes.

Set one variable and Wiener exports; leave it unset and it does not:

```bash
WIENER_OTLP_ENDPOINT=http://localhost:4317
```

**Off by default**, which is `CLAUDE.md`'s standing rule for telemetry and §8's for this: spans
reaching a *hosted* vendor are an undeclared egress path, and worse than the model one because
telemetry is fire-and-forget.

## Running SigNoz

**It is not in `docker-compose.yml` on purpose.** SigNoz deprecated its bundled Compose files in
v0.130.0 and installs through **Foundry**, a CLI that renders and runs its own stack; it is not
designed to be embedded in somebody else's compose file. Vendoring the deprecated manifest to
keep one-file tidiness would mean running an unmaintained copy of somebody else's stack.

Development:

```bash
curl -fsSL https://signoz.io/foundry.sh | bash
foundryctl cast -f casting.yaml     # OTLP on 4317, UI on 8080
```

Production is Kubernetes, where SigNoz has a Helm chart and this question does not arise.

## The boards

`ops/boards/` holds them as JSON, so they are part of the repository rather than something
somebody clicked once. Import them into whichever backend is running — they read the CI/CD
attribute names, which are the conventions' rather than ours, so a board is not tied to a
vendor either.

## Anything else that speaks OTLP

Jaeger renders traces and stores no metrics; Grafana over ClickHouse renders both and wants its
schema hand-built. Either works — `spans()` and the five metrics know nothing about the far end.
