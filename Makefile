.PHONY: help registry-present names-free check verify slow guards residue links test lint fmt types docs docs-status static stub profile forge clean \
	dev dev-down dev-logs dev-refresh prod prod-down client migrate wiki wiki-tools wiki-serve

# The containers run as the host user so bind-mounted files stay yours: git refuses a
# repository owned by another uid, and root-owned drafts in ./workspace are undeletable.
export DOCKER_UID := $(shell id -u)
export DOCKER_GID := $(shell id -g)

DC       := docker compose
RUN_DIR  := .run
PIDFILE  := $(RUN_DIR)/vite.pid
LOGFILE  := $(RUN_DIR)/vite.log
DEVREG   := $(RUN_DIR)/registry
# npm writes this file on every install, so it is the honest mtime for "what is installed".
NODEDEPS := frontend/node_modules/.package-lock.json

registry-present:  ## refuse early if the registry submodule was not checked out
	@if [ -z "$$(ls -A registry 2>/dev/null)" ]; then \
	  echo "registry/ holds no registry data — it is a git submodule and was not checked out."; \
	  echo; \
	  echo "    git submodule update --init"; \
	  echo; \
	  echo "'git clone --recurse-submodules' avoids this. See .github/CONTRIBUTING.md."; \
	  exit 1; \
	fi
# Here as well as in `layers.load()` because a contributor's first command is `make check`,
# not a pytest invocation — and thirty-three failures about missing contracts is not a
# diagnosis. Same sentence in both places on purpose.
#
# **Empty, not "has no contracts/".** It tested `-d registry/contracts` until
# comeni-registry#1 arranged the layer by tool, at which point the directory it was looking for
# stopped existing and this refused a perfectly good checkout. A layer is files that say what
# they are, so the only thing left to check is whether there are any.

help:           ## show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t20

check: registry-present lint test types docs docs-status links  ## everything CI runs on a pull request (~1 min, no Docker)

verify:         ## check + slow + guards — needs Docker, ~2 min. See CLAUDE.md
	@$(MAKE) --no-print-directory -j1 check
	@$(MAKE) --no-print-directory slow
	@$(MAKE) --no-print-directory guards
# Sequential sub-makes rather than prerequisites: `verify: check slow guards` would let
# -j interleave them, and cheapest-first only means something if it is actually ordered.
# `-j1` on check is not a preference — MAKEFLAGS carries -j12 here and has hidden a lint
# failure before.

slow:           ## the counts-matrix tests: --gate test on real data (Docker, ~45s warm)
	uv run pytest -m slow -v

guards:         ## purity, egress and construction — the tests that hold the invariants
	uv run pytest tests/guards/test_purity.py tests/guards/test_purity_runtime.py \
	  tests/guards/test_egress.py tests/guards/test_construction.py -v

residue:        ## how much of A14 is left, counted per guard (A69). --list for the names
	@uv run python tools/guard_residue.py $(ARGS)

test:           ## run the test suite
	uv run pytest -v

lint:           ## ruff, line length 100
	uv run ruff check .

fmt:            ## format in place
	uv run ruff format .

types:          ## fail if the generated measurement stub is stale
	uv run python tools/generate_types.py --check

forge-rework:   ## everything the deferred forge rework has to revisit
	@grep -rn FORGE-REWORK packages/ frontend/src/ docs/notes/ 2>/dev/null \
	  | grep -v Binary || echo "nothing marked"

links:          ## every relative markdown link in docs/, .github/, .design/ and the root
	uv run python tools/check_links.py

docs:           ## fail if docs/reference/ disagrees with the code
	uv run python tools/generate_diagnostics_doc.py --check
	uv run python tools/check_reference.py --check

docs-status:    ## what on the wiki is vision and what is real — derived, not asserted
	uv run python tools/docs_status.py --check

wiki-tools:     ## render the tool catalogue from the registry into docs/tools/
	uv run mendel docs --registry registry/ --out docs/tools/
	uv run python tools/generate_tools_catalogue.py

# wiki-tools is not optional here: mkdocs.yml's nav names tools/catalogue.md, which only
# exists once wiki-tools has generated it — a bare `mkdocs build`/`serve` aborts under --strict.
wiki: wiki-tools  ## build the wiki to site/ — local, no hosting
	uv run --group docs mkdocs build --strict

wiki-serve: wiki-tools  ## serve the wiki at http://localhost:8000 with live reload
	uv run --group docs mkdocs serve

static:         ## conformance + lint + preview — everything checkable without Docker
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate lint
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate preview

stub:           ## build the RNA-seq spine and run the stub gate (needs Docker + Nextflow)
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub

profile:        ## emit a pipeline that measures the input data
	uv run mendel profile --have fastq.reads --out profile-build/

clean:          ## remove build outputs
	rm -rf build/ profile-build/ dist/ .pytest_cache/ .ruff_cache/

forge:          ## draft one nf-core module into a scratch workspace and show it
	@rm -rf .forge-demo
	uv run forge draft nf-core:samtools/sort --name sort --version 1.21.0 \
	  --workspace .forge-demo
	@echo
	uv run forge verify sort --workspace .forge-demo || true
# The whole loop in one command, for somebody meeting the forge for the first time. It ends
# on `verify` refusing, which is the point: a fresh draft has holes, and MF0004 is the design
# working rather than failing. `|| true` because that refusal exits 1 and this target is a
# demonstration, not a gate.

client:  ## regenerate both TypeScript clients from the APIs' own schemas
	uv run python -c "import json; from mendel_api.main import create_app; print(json.dumps(create_app().openapi()))" > frontend/openapi.json
	cd frontend && npx openapi-typescript openapi.json -o src/api/schema.d.ts
	uv run python -c "import json; from wiener_api.main import create_app; print(json.dumps(create_app().openapi()))" > frontend/openapi.wiener.json
	cd frontend && npx openapi-typescript openapi.wiener.json -o src/wiener/api/schema.d.ts

migrate:  ## apply database migrations
	cd packages/mendel-api && uv run alembic upgrade head

telemetry:  ## bring up the OTLP backend — ClickHouse, the collector and Grafana on :3001
	docker compose --profile telemetry up -d clickhouse otel-collector grafana
	@echo "OTLP on localhost:4317 · boards on http://localhost:3001"
	@echo "point Wiener at it:  export WIENER_OTLP_ENDPOINT=http://localhost:4317"

wiener-migrate:  ## apply Wiener's migrations — its own chain, its own database
	cd packages/wiener-api && uv run alembic upgrade head

dev: names-free $(DEVREG) dev-refresh $(NODEDEPS)  ## the whole stack, plus Vite on the host for HMR
	@test -f .env || cp .env.example .env
	@# **Made here, owned by whoever ran make.** Docker creates a missing bind-mount source
	@# ROOT-owned, and the containers run as the host user — so the first write dies on
	@# `PermissionError`. Same trap CLAUDE.md records for ./workspace, and the same fix.
	@#
	@# **The Wiener pair was covered and the Mendel pair was not**, while the sentence above
	@# named ./workspace as the precedent. Measured 2026-08-29: `.run/drafts` and `workspace`
	@# came up `root root`, and pressing *Keep* in the builder answered 500 with
	@# `PermissionError: /app/drafts/<id>` — the one control the whole loop hangs on.
	@mkdir -p .run/wiener/artifacts .run/wiener/work .run/drafts workspace
	$(DC) up -d --build
	@mkdir -p $(RUN_DIR)
	@if [ -f $(PIDFILE) ] && kill -0 `cat $(PIDFILE)` 2>/dev/null; then \
		echo "Vite already running (pid `cat $(PIDFILE)`)"; \
	else \
		setsid sh -c 'cd frontend && exec npm run dev' > $(LOGFILE) 2>&1 & \
		echo $$! > $(PIDFILE); sleep 1; \
	fi
	@echo ""
	@echo "  Home (HMR):     http://localhost:5173/"
	@echo "  Home (built):   http://localhost/"
	@echo "  Queue:          http://localhost:5173/forge/queue"
	@echo "  API:            http://localhost:8000/docs"
	@echo "  Runs:           http://localhost:5173/runs"
	@echo "  Logs:           make dev-logs    ·    Vite: tail -f $(LOGFILE)"

# **Install what the frontend now depends on, before Vite serves it.**
#
# `make dev` ran `npm run dev` against whatever `node_modules` happened to hold. Pull a commit
# that adds a dependency and the HMR server starts fine and fails in the browser — while
# `http://localhost/` stays green, because the `web` image runs `npm ci` in its own build. Two
# addresses, one of them silently a version behind. Measured after a 152-commit pull:
# `@tanstack/react-virtual` was in `package.json`, absent from `node_modules`, and `tsc -b`
# was the only thing that said so.
$(NODEDEPS): frontend/package-lock.json
	@echo "frontend dependencies changed — installing"
	cd frontend && npm install

# **Refuse early when another checkout already owns our container names.**
#
# The names are fixed (`mendel-api`, `wiener-db`, ...) so `docker exec mendel-db psql` works
# without looking anything up. The cost is that two checkouts collide, and the collision
# surfaces as a daemon error naming ONE container, mid-way through `up`, after some volumes
# have already been created:
#
#     Error response from daemon: Conflict. The container name "/mendel-redis" is already in
#     use by container "a5ba6fa6ed10..."
#
# `.env.example` has commented `*_CONTAINER_NAME` overrides "so two checkouts can run side by
# side", but `make dev` copies that file with them still commented — so the default experience
# is the conflict, and the message says nothing about the fix. This lists every colliding name
# at once and names both ways out.
#
# ═══ AND THE FIX IT NAMED DID NOT WORK ════════════════════════════════════════════════════
#
# Found 2026-08-31 by taking the advice in the message. Two reasons, and both are the same
# mistake: the check was written from the *sentence* rather than from `docker-compose.yml`.
#
#   → **It read the shell, not `.env`.** `make` does not load `.env`; compose does. So the
#     overrides the message tells you to write were invisible to the check that printed the
#     message, and following its advice changed nothing at all.
#   → **Five of the nine names were hardcoded.** `mendel-db`, `mendel-redis`, `wiener-db`,
#     `wiener-ingest` and `wiener-worker` had no override here, though `docker-compose.yml`
#     makes every one of them a `$${..._CONTAINER_NAME:-default}`. So even exporting the
#     variables first would still have collided on five names.
#
# The list is read from compose itself now — `config --format json` resolves `.env`, the
# defaults and the overrides the same way `up` will — so there is one answer to *what will
# this stack call its containers* rather than a copy here that goes stale on the next service.
names-free:
	@names="$$(docker compose config --format json 2>/dev/null \
	  | python3 -c 'import json,sys; print(" ".join(s.get("container_name","") for s in json.load(sys.stdin)["services"].values() if s.get("container_name")))' \
	  2>/dev/null)"; \
	if [ -z "$$names" ]; then \
	  echo "could not read the container names from compose; skipping the collision check"; \
	  exit 0; \
	fi; \
	mine="$${COMPOSE_PROJECT_NAME:-$$(basename "$$PWD" | tr '[:upper:]' '[:lower:]')}"; \
	clash=""; \
	for n in $$names; do \
	  owner="$$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' $$n 2>/dev/null || true)"; \
	  if [ -n "$$owner" ] && [ "$$owner" != "$$mine" ]; then clash="$$clash  $$n (owned by '$$owner')\n"; fi; \
	done; \
	if [ -n "$$clash" ]; then \
	  printf 'another checkout already owns these container names:\n\n'; \
	  printf "$$clash"; \
	  printf '\ncompose would fail part-way through `up`, one name at a time. Either:\n\n'; \
	  printf '    docker rm $$(docker ps -aq --filter label=com.docker.compose.project=<owner>)\n\n'; \
	  printf 'to retire that stack — named volumes survive, so its data does — or set the\n'; \
	  printf '*_CONTAINER_NAME lines in .env to run both side by side.\n'; \
	  exit 1; \
	fi

# A CLONE of the registry, because a submodule's `.git` is a pointer at a host path that
# resolves to nothing inside a container — so accepting a drift would refuse with MF0107, and
# dev must be able to do what prod can.
$(DEVREG):
	@mkdir -p $(RUN_DIR)
	git clone -q registry $(DEVREG)
	@echo "cloned the registry to $(DEVREG) — this is what the containers write to"

# **A dependency of `dev`, not a thing to remember.** The clone was made once and never
# touched again, so `make dev` served whatever the registry looked like the first time anybody
# ran it — every change in Plan 5A and 5B was invisible to the running stack, and the symptom
# was a blank builder with a 422 about a manifest field that had been replaced.
dev-refresh:  ## pull registry changes into the dev clone, if it has no work in it
	@if [ ! -d $(DEVREG) ]; then echo "no dev registry yet"; exit 0; fi; \
	if [ -n "`git -C $(DEVREG) status --porcelain`" ]; then \
		echo "dev registry has uncommitted work — left alone"; exit 0; fi; \
	want=`git -C registry rev-parse HEAD`; \
	have=`git -C $(DEVREG) rev-parse HEAD`; \
	if [ "$$want" = "$$have" ]; then echo "dev registry is current ($$(echo $$want | cut -c1-8))"; \
	else \
		git -C $(DEVREG) fetch -q origin HEAD && git -C $(DEVREG) reset -q --hard FETCH_HEAD && \
		echo "dev registry $$(echo $$have | cut -c1-8) -> $$(echo $$want | cut -c1-8)"; \
	fi
	@# **`fetch origin HEAD`, never a branch name.** This reset to `origin/HEAD`, and the
	@# clone's origin is the submodule *directory* — fetching a path gets its local branches,
	@# and the submodule's `main` never moves because the superproject pins a *commit* and
	@# leaves it detached. So it fetched a branch that had not moved in days and printed
	@# "dev registry refreshed". `HEAD` fetches whatever the submodule is actually on.
	@#
	@# The message now names the two commits, so a refresh that moves nothing says so. A
	@# success line that is unconditional on whether anything happened is `make drift`
	@# printing "skipped" over twelve edited contracts, in a new place.

dev-down:  ## stop Vite and the stack
	@if [ -f $(PIDFILE) ]; then kill -- -`cat $(PIDFILE)` 2>/dev/null || true; rm -f $(PIDFILE); fi
	$(DC) down

dev-logs:  ## tail the api and the worker
	$(DC) logs -f api worker

prod:  ## the same stack, with the unsafe parts removed
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-down:  ## stop the prod stack
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down
