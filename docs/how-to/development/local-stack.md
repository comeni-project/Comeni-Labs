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

Install Docker with Compose 2.24.4 or newer, Python 3, Node.js and npm first.
Make reads `.env` through the Compose CLI, preserving dotenv quotes and interpolation;
exported environment values take precedence. This parsing needs the CLI but no running daemon.
Direct Python commands still need their configuration exported.

Startup creates `.env` from the example if absent, prepares writable runtime directories,
clones the registry into `.run/registry` and waits for Vite to become ready. Failures point to
`.run/vite.log`. Set `VITE_HOST_PORT`, `API_HOST_PORT` and `WEB_HOST_PORT` in `.env` when
running another checkout; Vite follows those backend ports and requires its own port to be free.

`make dev-refresh` fast-forwards a clean registry clone only when its history permits it.
Dirty, ahead or divergent clones retain their local changes and commits. Review and reconcile
such work in `.run/registry` explicitly before expecting upstream changes to appear.

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
stack to a network you do not control. Published development ports bind to `127.0.0.1`.
An empty `WIENER_API_TOKEN` disables local run-management authentication.

## Production overlay

```bash
make prod
make prod-down
```

`docker-compose.prod.yml` overlays the development compose file. Set a nonempty
`WIENER_API_TOKEN` before startup. Only the web port is published; application source comes
from the image while registry, drafts and workspace remain writable. See the
[operations guide](https://github.com/comeni-project/Comeni-Labs/blob/main/ops/README.md#application-deployment) for binding and image requirements.

See [Development services](../../reference/development-services.md) for service ownership
and [Configure a model](configure-model.md) for local or hosted model setup and troubleshooting.
