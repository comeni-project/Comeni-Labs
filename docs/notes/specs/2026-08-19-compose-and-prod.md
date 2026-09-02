# Compose and prod — Plan 3A phase 8

**Status:** written 2026-08-19, against the code phases 0–6 landed.
**Implements:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §7 and §3's phase 8 —
*bring the whole thing up with one command* — and `worker.py`'s `cron_jobs: []`, whose docstring
says *"The nightly schedule lands with Compose"*.
**Follows:** `../../Cladewright/docker-compose.dev.yml` and `../../portfolio/docker-compose.prod.yml`,
read rather than remembered. Where this spec and those files disagree about a shape, they are
right and this drifted.

---

## 1. What phase 8 is for

Six phases built a tool that a developer runs by hand: `docker compose up postgres redis`, a
`uvicorn` in one terminal, an `arq` worker in another if they remember, `npm run dev` in a third.
Nothing starts the worker at all, so the drift check has never run on a schedule — `checked_at`
has been real and *"next nightly"* has been a lie since phase 4.

At the end, `make dev` brings the whole thing up and prints where it is, and
`docker-compose.prod.yml` runs the same services with the frontend built and served.

**What phase 8 is not:** not a deployment, not TLS, not auth, not a registry of images. It is the
last phase of 3A and it ends 3A; 3B is the landing page.

**It was phase 7 until 2026-08-19**, when a performance audit inserted one ahead of it — see
[`2026-08-19-responsiveness.md`](2026-08-19-responsiveness.md). Compose inherits a fast app
instead of packaging a slow one, which is the right order.

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
| any service beyond db and redis in the compose file | §3.1 |
| a prod overlay | §3.1 |
| a registry a container can commit to | §3.2 |
| a cron schedule | *"next nightly"* is still not true |

**Measured, because it decides how the image is built:** the API reads `registry/` (**224K**) and
`vendor/` (**788K**) at runtime — `settings.registry_root` and `settings.source_root`. This is not
a web app whose data lives in Postgres; roughly a megabyte of declared files is part of what it
serves.

---

## 3. Decisions

### 3.1 One compose file defines the stack; prod is an overlay that changes safety and nothing else

**Dev and prod run the same services, and the difference is safety.** That is the operator's
instruction and it is also the only version that stays true: two independent compose files drift,
and the drift shows up as *"it works in dev"*.

```
docker-compose.yml        the definition — db, redis, api, worker, web (nginx)
docker-compose.prod.yml   an OVERLAY: restart policies, no code mounts, no --reload,
                          no published database or redis ports
make dev   ->  docker compose up -d
make prod  ->  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Everything a curator can do in prod, they can do in dev. What the overlay removes is a live code
mount, an auto-reloader, and a Postgres port open on the host — three things that are *unsafe*,
not three capabilities.

**The nginx service is in the base, so dev serves the prod path too.** The first draft of this
spec put nginx only in prod and left dev on the Vite proxy, which meant the routing dev exercised
was not the routing prod ran. That is precisely the class of difference this decision exists to
delete.

**Vite on the host is additional, not a replacement.** `make dev` also starts it, so HMR is there
on `:5173` while `:80` serves the same built SPA prod serves. Dev has strictly more; it never has
less. Both reference repos keep the dev server off the container for the same reason — HMR through
a bind-mount is slower and flakier on Linux — and neither of them had a second serving path to
compare against, which is why this spec adds one rather than copying.

### 3.2 Dev gets a writable registry clone, so accepting a drift works there too

The first draft of this spec had dev mount the submodule, discover that drift acceptance then
refuses, and **write that up as an honest finding**. It is an honest finding about a broken dev
environment. Dev must be able to do what prod does.

**Measured, and it is why the submodule cannot be the answer:**

```
registry/.git  ->  gitdir: ../../../.git/worktrees/plan-3-slice-1/modules/registry
(registry / ".git").exists()  ->  True
git branch --show-current     ->  fatal: not a git repository: (null)
```

A submodule's `.git` is a *file* holding a relative pointer out of the worktree. Bind-mount that
directory anywhere else and the file is present while every git call fails.

**So `make dev` clones it**, once, into a gitignored `.run/registry`, and compose mounts that.
Verified end to end:

```
git clone registry .run/registry     ->  branch: main
POST /drift/accept                   ->  forge/drift c90cbf5
git log -1  ->  forge: nf-core/fastqc@0.12.1 container -> …hdfd78af_0
```

A clone is what a laboratory actually has — the submodule is a pin for *this repository's tests*,
not the thing an installation writes to. Prod mounts a clone for the same reason, so this is one
shape rather than two.

`make dev` refreshes it (`git -C .run/registry fetch && git reset --hard origin/HEAD` when clean)
so registry edits reach dev without a manual step, and leaves it alone when it is dirty — a
`forge/drift` branch you have not merged is work, not staleness.

### 3.3 The image is multi-stage with a dependency layer, and the numbers are measured

| | |
|---|---|
| cold build | **53s** |
| **after a source edit** | **8.3s** |
| image | **693MB** before §3.4 |

The dependency layer copies the workspace's *shape* — the root `pyproject.toml`, `uv.lock`, and
each member's `pyproject.toml` with its `README.md` and `LICENSE` — and runs
`uv sync --frozen --no-install-project --no-dev`. Source arrives afterwards, so editing a module
re-runs the last two layers and nothing else. That is the 53 → 8.3 second difference.

**`README.md` and `LICENSE` are build inputs, not documentation.** The root and five of the six
members declare `readme =` and `license-files =`, so a dependency layer without them fails in
`uv sync`. Found by building it.

**BuildKit cache mounts are not available on this machine and the Dockerfile must not need them.**
Measured: `docker buildx` is not installed, and `DOCKER_BUILDKIT=1` answers *"BuildKit is enabled
but the buildx component is missing or broken"*. A `--mount=type=cache` Dockerfile does not build
here at all, which is the worst possible way to optimise. Layer ordering and a multi-stage build
work on the classic builder and are what this uses. **Installing `docker-buildx` would allow uv's
cache to persist across a cold build too** — worth doing, and not something a spec should assume
of somebody's machine.

The runtime stage is `python:3.12-slim-bookworm` plus `git` — needed because accepting a drift is
a commit — and copies the built `.venv` rather than the toolchain.

### 3.4 `mendel-ai` becomes an optional extra, because the served API cannot reach it

**Measured inside the image**, and this is the single largest thing in it:

```
litellm      110M
openai        19M
tokenizers    11M
hf_xet        12M            152M of a 285M virtualenv
```

Invariant 3 confines runtime AI to three points and **none of them is built**. `mendel-ai` exists
for `forge fill --model`, which is a CLI opt-in — CLAUDE.md says so in as many words: *"the
forge's model path is opt-in through `forge fill --model`, so its default is the no-AI lane"*.

It is nonetheless a hard dependency of `mendel-forge`, imported at the top of `ops.py`,
`filler.py` and `cli/__init__.py`. So the served image ships a model client, its HTTP stack and a
tokenizer library for a code path it cannot execute.

**It becomes `mendel-forge[model]`**, with those three imports moved inside the functions that use
them, and the image syncs `--package mendel-api` rather than the root project. Dev and CI install
the extra and lose nothing.

**This is a packaging change that makes a documented claim structurally true**, which is the same
move as `--no-ai` not being a flag: the no-AI lane stops being a default anybody could quietly
change and becomes what is installed.

### 3.5 Accepting a drift on a directory that is not a checkout refuses instead of crashing

`MF0107`, and the check is `git rev-parse --git-dir` rather than `(registry / ".git").exists()` —
§3.2 measured why the shortcut is wrong exactly where it matters.

**It is still worth building even though §3.2 means dev no longer hits it.** A prod installation
that mounts the wrong path, or forgets the mount entirely and gets the image's baked copy, lands
here — and a coded sentence naming the fix beats `CalledProcessError: exit 128`.

### 3.6 The nightly check runs `check_sources`, and the strip may then say *next nightly*

`WorkerSettings.cron_jobs` gains one entry at 03:00. The job exists and writes a `SourceCheck`
row; what was missing was somewhere to run it.

**Not `run_at_startup`** — a container restart is not a check-worthy event, and a strip reading
*checked 4 seconds ago* after every deploy is measuring deploys. Phase 4 deliberately withheld
*next nightly* because nothing scheduled anything; that becomes true here, so it can be shown.

### 3.7 `.env.example` is committed

Six settings with defaults, discoverable only by reading a class today. `MENDEL_REGISTRY_ROOT`
gets the loud comment: point it at a checkout you can write to, or drift acceptance refuses.

### 3.8 A test reads the compose files

Not a smoke test — `make check`'s lane has no Docker. A parse-and-assert: the overlay names only
services the base defines, every service is healthchecked or waits for one that is, the api and
the worker share one image, **the registry and the vendored modules reach the api**, and prod
mounts no code. The fourth is the one worth having: it is the failure that 500s every screen and
is invisible until somebody runs the image.

---

## 4. The surface

```
docker-compose.yml         db · redis · api · worker · web
docker-compose.prod.yml    overlay — restart, no mounts, no published infra ports
Dockerfile                 multi-stage; deps layer, then source
frontend/Dockerfile        node build -> nginx
nginx/default.conf         the SPA, and /api to the api
.dockerignore              .git .venv node_modules dist build .run
.env.example               every setting, with the registry one flagged
```

| `make` | does |
|---|---|
| `dev` | clone-or-refresh `.run/registry`, compose up, Vite on the host, print the URLs |
| `dev-down` | Vite down, compose down |
| `dev-logs` | tail the api and the worker |
| `prod` | the same stack with the prod overlay |

---

## 5. What this does not settle

**No deployment, no TLS, no auth.** The prod overlay is *the same stack with the unsafe parts
removed* rather than a production posture. Auth is still deferred (interface spec §9) and nothing here changes
that — an installation reachable from anywhere untrusted is not something this repository has yet
earned the right to describe.

**Accepting a drift needs a clone, in dev and in prod alike** — §3.2 and §3.5. Dev gets one from
`make dev`; a prod installation mounts one. What is *not* settled is git identity in prod: the
commit is authored as `<by>@forge.local`, which is fine for a local branch and is not a signed
commit by a named human. The federation spec's curated tier asks for the latter and this is not
it.

**The image is not published anywhere.** `portfolio` pulls a tagged image from a registry; this
builds locally. Publishing is a release question and releases are per package
(`docs/guides/releasing.md`), which is a different thing from an application image.

**The image is measured and not yet small.** 693MB before §3.4's extra, of which 206MB is the
base plus `git` and 285MB is the virtualenv. §3.4 removes a measured 152MB. What remains large
after that is `sqlalchemy` (23M), `uvloop` (16M) and `psycopg` (11M), all of which are used —
so the next real reduction is a smaller base, not a smaller dependency set, and nobody needs it
yet.

**Installing `docker-buildx` would improve the cold build**, and this machine does not have it —
§3.3. Cache mounts would let uv's download cache survive a `--no-cache` build; layer ordering
already covers the case that matters, which is editing source.
