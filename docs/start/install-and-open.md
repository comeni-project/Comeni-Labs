---
title: Install and open the app
description: Bring up the alpha stack and open Comeni Labs in the browser.
---

# Install and open the app

You need `uv` and Docker. Clone with submodules, install the Python environment, and start the
local stack:

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
make dev
```

Open [http://localhost:5173](http://localhost:5173). That is the Vite development frontend, so
frontend changes appear without rebuilding the production bundle.

## Check it worked

You should see the Comeni home screen. On a fresh checkout, it may show the first-run prompt
with a link to build by hand. Existing local state may show recent pipeline drafts and runs
instead.

If startup fails early, check these first:

| Symptom | Likely cause | Fix |
|---|---|---|
| `registry/ holds no registry data` | the submodule was not checked out | run `git submodule update --init` |
| Docker container name conflict | another checkout owns the local names | stop the other stack or set compose name overrides |
| Browser cannot reach `:5173` | Vite did not start | inspect `.run/vite.log` or run `make dev-logs` |

## What starts

The local alpha stack brings up the app, the Mendel API that builds pipeline drafts, the Wiener
services that launch and observe runs, Postgres, Redis, and the local telemetry pieces. For
day-to-day use, the important addresses are:

| Address | Use |
|---|---|
| `http://localhost:5173/` | the app |
| `http://localhost:5173/build` | the pipeline builder |
| `http://localhost:5173/runs` | run history and live runs |
| `http://localhost:5173/forge/tools` | tool and registry maintenance |

## Alpha expectations

Comeni Labs is Alpha, pre-MVP. The broad loop is the thing to learn now: build, review, run,
watch. Some exact screens will change, especially the way inputs and samplesheets are supplied
before launch.

This page is intentionally operational: it tells you how to run the local alpha today. It is
not a deployment guide for a shared lab service.

When you are done:

```bash
make dev-down
```

For the container-by-container development view, see
[Local development stack](../handbook/the-stack.md).
