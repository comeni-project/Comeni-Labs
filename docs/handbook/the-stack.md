# Running the platform

Everything the command line does, plus the parts it cannot: a visual pipeline builder, a live
run monitor, and a review queue for new tools. This brings it all up on your machine.

**You need Docker.** Everything else is fetched or built for you.

## Bring it up

```bash
make dev
```

That builds and starts eleven containers, then starts Vite on your machine so the frontend
hot-reloads while you edit it. When it finishes it prints where things are:

```
  Home (HMR):     http://localhost:5173/
  Home (built):   http://localhost/
  Queue:          http://localhost:5173/forge/queue
  API:            http://localhost:8000/docs
  Runs:           http://localhost:5173/runs
  Logs:           make dev-logs    ·    Vite: tail -f .run/vite.log
```

Use **`:5173`** while developing — that is Vite, and your frontend edits appear immediately.
**`http://localhost/`** is nginx serving the built bundle, which is what production looks like.

## What is actually running

| container | what it does |
|---|---|
| `api` | the Mendel API — resolves goals, stores drafts, serves the builder |
| `worker` | long jobs for the API, over Redis |
| `web` | nginx: the built SPA, and `/api` proxied to `api` |
| `postgres` · `redis` | the API's database and its queue |
| `wiener-api` | launches runs and answers questions about them |
| `wiener-ingest` · `wiener-worker` | receive Nextflow's events and fold them into run state |
| `wiener-postgres` | Wiener's own database, on its own migration chain |
| `otel-collector` · `clickhouse` · `grafana` | traces, and the across-runs boards on `:3001` |

Mendel and Wiener are **separate services that do not know about each other**. When you send a
pipeline from the builder to Wiener, your browser carries it. See
the execution boundary for why.

## Where to go in the app

| | |
|---|---|
| `/` | what needs you, and what your lab has been doing |
| `/build` | the pipeline builder — draw a graph, or see what the resolver would do |
| `/runs` · `/runs/:id` | runs, and one run in detail |
| `/forge/queue` · `/forge/tools` | the registry review queue and tool status board |

## Stopping, and starting clean

```bash
make dev-down      # stop the stack and Vite
make dev-logs      # tail the api and the worker
make migrate       # apply Mendel's database migrations
make wiener-migrate  # apply Wiener's — its own chain, its own database
```

## Two things to know before you rely on it

**The worker holds your Docker socket.** That is how a container starts Nextflow, which starts
more containers. It is root-equivalent on your machine. `WIENER_API_TOKEN` in `.env` is the only
thing in front of it, and the worker warns at startup if the socket is mounted without one.
Do not expose this stack to a network you do not control. `docs/design/wiener.md` §12.1 records
the trade-off, and running under Kubernetes removes it.

**The run directory is mounted at the same absolute path inside and outside the container.**
A path handed to the Docker daemon is resolved on the *host*, so a named volume breaks this
silently. `make dev` creates those directories owned by whoever ran it, because Docker would
otherwise create them as root and the first write would fail.

## Production

```bash
make prod        # the same stack with the unsafe parts removed
make prod-down
```

`docker-compose.prod.yml` is an overlay, not a second stack — it changes what `docker-compose.yml`
already declares.

## Next

- [Watching a run](running-the-stack.md) — send a pipeline to Wiener and read what happened
- [Driving Mendel](../tutorial.md) — the same loop on the command line
