# Local development stack

<!--
Serves: all four steps.
-->

This page is for people running or developing the alpha stack locally. If you only want to use
the product, start with [Install and open the app](../install.md).

## Bring it up

```bash
make dev
```

When it finishes, use:

| Address | Use |
|---|---|
| `http://localhost:5173/` | app with Vite hot reload |
| `http://localhost/` | nginx serving the built frontend |
| `http://localhost:8000/docs` | Mendel API docs |
| `http://localhost:5173/runs` | runs board |
| `http://localhost:5173/forge/queue` | registry review queue |
| `http://localhost:8010/` | this wiki, with live reload |

Use `:5173` while developing the frontend.

## Useful commands

```bash
make dev-logs
make migrate
make wiener-migrate
make dev-down
```

## Safety

The local development worker uses the Docker socket so it can launch Nextflow, which launches
containers. Treat that as root-equivalent access to your machine. Do not expose the development
stack to a network you do not control.

## Production overlay

```bash
make prod
make prod-down
```

`docker-compose.prod.yml` overlays the development compose file. It is not a separate product
architecture.

See [Development services](../../reference/development-services.md) for service ownership
and [Configure a model](configure-model.md) for local or hosted model setup and troubleshooting.
