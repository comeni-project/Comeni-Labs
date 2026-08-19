# Compose and prod — Plan 3A phase 7

**Status:** written 2026-08-19, against the code phases 0–6 landed.
**Implements:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §7 and §3's phase 7 —
*bring the whole thing up with one command* — and `worker.py`'s `cron_jobs: []`, whose docstring
says *"The nightly schedule lands with Compose"*.
**Follows:** `../../Cladewright/docker-compose.dev.yml` and `../../portfolio/docker-compose.prod.yml`,
read rather than remembered. Where this spec and those files disagree about a shape, they are
right and this drifted.

---

## 1. What phase 7 is for

Six phases built a tool that a developer runs by hand: `docker compose up postgres redis`, a
`uvicorn` in one terminal, an `arq` worker in another if they remember, `npm run dev` in a third.
Nothing starts the worker at all, so the drift check has never run on a schedule — `checked_at`
has been real and *"next nightly"* has been a lie since phase 4.

At the end, `make dev` brings the whole thing up and prints where it is, and
`docker-compose.prod.yml` runs the same services with the frontend built and served.

**What phase 7 is not:** not a deployment, not TLS, not auth, not a registry of images. It is the
last phase of 3A and it ends 3A; 3B is the landing page.

---

## 2. What exists, and what does not

Checked by reading it, 2026-08-19.

| Exists | Where |
|---|---|
| `docker-compose.yml` — **postgres and redis only**, healthchecked, named volume | repo root |
| `make dev` — `compose up -d postgres redis` then `npm run dev` **in the foreground** | `Makefile` |
| `make migrate` — `alembic upgrade head` on the host | `Makefile` |
| `check_sources`, an ARQ job that runs the whole registry check | `mendel_api/worker.py` |
| `WorkerSettings.cron_jobs: list = []` with a docstring naming this phase | `worker.py` |
| the Vite proxy, `/api` → `localhost:8000` | `frontend/vite.config.ts` |
| `.env` and `.env.local` ignored | `.gitignore` |

| Does **not** exist | Consequence |
|---|---|
| any `Dockerfile` | the API and worker cannot be images |
| any `.env.example` | every setting is a default in `settings.py` and undiscoverable |
| a dev compose carrying the api or the worker | §3.1 |
| a prod compose at all | §3.4 |
| a cron schedule | *"next nightly"* is still not true |

**Measured, because it decides how the image is built:** the API reads `registry/` (**224K**) and
`vendor/` (**788K**) at runtime — `settings.registry_root` and `settings.source_root`. This is not
a web app whose data lives in Postgres; roughly a megabyte of declared files is part of what it
serves.

---

## 3. Decisions

### 3.1 `docker-compose.dev.yml` carries db, redis, api and worker — and the frontend stays on the host

The existing `docker-compose.yml` is renamed. It holds infrastructure only, which is why the API
and the worker are started by hand today and the worker usually is not started at all.

Only the `Makefile` refers to the old filename, so the rename costs one line.

**The frontend is not in it**, matching both reference repos: an HMR dev server through a
container bind-mount is slower and flakier on Linux, and Vite on the host already proxies `/api`.
`make dev` brings compose up and starts Vite **in the background with a pidfile and a log**, then
prints the URLs — `make dev` today runs `npm run dev` in the foreground, so it never gets as far
as printing anything.

Shapes taken from `Cladewright/docker-compose.dev.yml`: healthchecks at `2s/2s/30`,
`depends_on: condition: service_healthy`, `container_name` overridable through `${…}`, a named
volume for pgdata, live code mounts, and migrations in the API's start command.

### 3.2 The image carries the registry and the vendored modules

`settings.registry_root` and `settings.source_root` are read on nearly every request: the queue,
the contracts list, the drift report and the source catalogue all walk them. A container without
them serves 500s.

They are **baked into the image** rather than mounted, because at 1MB they are cheap, and because
an image that cannot answer without a correctly-mounted host directory is an image that fails in
a new way on every host. Dev mounts them live anyway, as it mounts the code.

**`registry/` is a git submodule**, so a build context has its files only if it is checked out —
the same `git submodule update --init` that `make check` already refuses without. `.dockerignore`
excludes `.git`, `.venv`, `node_modules` and the frontend build.

### 3.3 Accepting a drift in a container needs a git checkout, and today it crashes

**Measured, and this is a defect rather than a packaging note:**

```
ops.accept(... registry_root=<a copy with no .git> ...)
  -> CalledProcessError: 'git branch --show-current' returned non-zero exit status 128
```

Phase 5 built a ladder of coded refusals for every way a checkout is not somewhere to commit —
detached HEAD, dirty tree, default branch — and **missed the case a container makes normal**: the
path is not a git repository at all. A baked-in registry is exactly that, so `POST /drift/accept`
would answer a 500 carrying a git traceback rather than a sentence.

`MF0107` closes it: *the registry is not a git checkout*, with a fix naming the volume mount. It
belongs in the same band and the same function as the other three, and phase 5's own test file
gains the fourth case.

**And the check must ask git rather than stat `.git`** — measured, because the obvious shortcut is
wrong in exactly the case this diagnostic is for:

```
registry/.git  ->  gitdir: ../../../.git/worktrees/plan-3-slice-1/modules/registry
(registry / ".git").exists()  ->  True
git branch --show-current     ->  fatal: not a git repository: (null)
```

A submodule's `.git` is a **file** holding a relative pointer. Bind-mount that directory into a
container and the file is there while every git call fails, so `.exists()` answers yes to the one
question it was added to answer no to. `git rev-parse --git-dir` is the check.

**What it does not do is make accepting work in prod**, and the spec says so rather than
implying: an installation that wants drift resolution mounts a **clone** it can write to, with git
identity configured — not the submodule, whose pointer resolves to nothing outside the worktree.
That is a deployment decision, and the refusal is what makes it a legible one instead of a crash.

### 3.4 Prod serves the SPA with nginx, and that is forced by a guard rather than chosen

The obvious shortcut — `app.mount("/", StaticFiles(directory=...))` — **fails phase 6's guard**,
measured:

```
mounts after serving the SPA from FastAPI: ['']
test_the_served_surface_is_the_openapi_document: FAIL
```

That is the guard working, not a nuisance. Its rule is *the served surface is exactly the OpenAPI
document*, and a directory of static files is precisely a surface that is not in it. So the API
stays a JSON surface and nginx serves the built SPA and proxies `/api` — which is what
`portfolio/docker-compose.prod.yml` does, so the shape is the house one as well as the forced one.

**This is the first time a guard from one phase has decided a design question in another**, and it
is worth writing down: the argument for the rule was about generated clients, and it paid out
somewhere nobody was thinking about clients at all.

### 3.5 The nightly check runs `check_sources`, and the strip may then say *next nightly*

`WorkerSettings.cron_jobs` gains one entry: `check_sources` at 03:00. The job already exists and
already writes a `SourceCheck` row; what was missing was somewhere to run it.

**The health strip's copy changes with it, and not before.** Phase 4 shipped `checked_at` and
deliberately did not print *"next nightly"* because nothing scheduled anything. That sentence
becomes true in this phase, so it can be shown — and a `run_at_startup` is deliberately **not**
set, because a container restart is not a check-worthy event and a strip that says *checked 4
seconds ago* after every deploy is measuring deploys.

### 3.6 `.env.example` is committed, and it is the first place every setting is written down

`Settings` has six fields with defaults, and today the only way to learn they exist is to read the
class. The committed example is the discoverable surface: every variable, its default, and one
line on what it is for. `.env` stays ignored, as in both reference repos.

**`MENDEL_REGISTRY_ROOT` gets the loudest comment**, because phase 5 and phase 6 both turn on it:
point it at a checkout you can write to, or drift acceptance refuses with `MF0105` or `MF0107`.

### 3.7 A test reads the compose files

Not a smoke test — those need Docker, and `make check`'s lane has none. A parse-and-assert over
the YAML: every service healthchecked or depending on one that is, no service exposing a port it
does not need, the api and worker sharing one image, and **`registry/` and `vendor/` present in
the image or mounted**. It is cheap and it catches the class of error that otherwise appears only
on somebody's first `make dev`.

---

## 4. The surface

```
docker-compose.dev.yml     db · redis · api · worker      live mounts, migrations on start
docker-compose.prod.yml    the same four · frontend · nginx
Dockerfile                 one image, api and worker, `uv sync --frozen`
frontend/Dockerfile        node build → nginx static
nginx/default.conf         the SPA, and /api to the api
.dockerignore              .git .venv node_modules frontend/dist build/
.env.example               every setting, with the registry one flagged
```

| `make` | does |
|---|---|
| `dev` | compose up, Vite on the host with a pidfile, print the URLs |
| `dev-down` | Vite down, compose down |
| `dev-logs` | tail the api and worker |
| `prod` | `docker compose -f docker-compose.prod.yml up -d --build` |

---

## 5. What this does not settle

**No deployment, no TLS, no auth.** `docker-compose.prod.yml` is *the same thing, built* rather
than a production posture. Auth is still deferred (interface spec §9) and nothing here changes
that — an installation reachable from anywhere untrusted is not something this repository has yet
earned the right to describe.

**Accepting a drift in a container is refused rather than solved** — §3.3. The refusal is the
deliverable; a writable mounted checkout with git identity is a deployment choice.

**The image is not published anywhere.** `portfolio` pulls a tagged image from a registry; this
builds locally. Publishing is a release question and releases are per package
(`docs/guides/releasing.md`), which is a different thing from an application image.

**Nothing measures the image.** It is a `uv sync --frozen` over five workspace packages plus a
megabyte of declared data; whether that is 200MB or 900MB is unmeasured, and the first person to
care should measure rather than guess.
