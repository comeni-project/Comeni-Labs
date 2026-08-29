.PHONY: help registry-present names-free check verify slow guards residue links test lint fmt types docs static stub profile forge clean \
	dev dev-down dev-logs dev-refresh prod prod-down client migrate

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
	  echo "'git clone --recurse-submodules' avoids this. See docs/guides/contributing.md."; \
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

check: registry-present lint test types docs links  ## everything CI runs on a pull request (~1 min, no Docker)

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
	uv run pytest tests/test_purity.py tests/test_purity_runtime.py \
	  tests/test_egress.py tests/test_construction.py -v

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

links:          ## every relative markdown link in docs/ and the root resolves
	uv run python tools/check_links.py

docs:           ## fail if docs/reference/diagnostics.md is stale
	uv run python tools/generate_diagnostics_doc.py --check

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

dev: names-free $(DEVREG) $(NODEDEPS)  ## the whole stack, plus Vite on the host for HMR
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
names-free:
	@names="$${API_CONTAINER_NAME:-mendel-api} $${WORKER_CONTAINER_NAME:-mendel-worker} $${WEB_CONTAINER_NAME:-mendel-web} $${WIENER_API_CONTAINER_NAME:-wiener-api} mendel-db mendel-redis wiener-db wiener-ingest wiener-worker"; \
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

dev-refresh:  ## pull registry changes into the dev clone, if it has no work in it
	@if [ -z "`git -C $(DEVREG) status --porcelain`" ]; then \
		git -C $(DEVREG) fetch -q origin && git -C $(DEVREG) reset -q --hard origin/HEAD && \
		echo "dev registry refreshed"; \
	else echo "dev registry has uncommitted work — left alone"; fi

dev-down:  ## stop Vite and the stack
	@if [ -f $(PIDFILE) ]; then kill -- -`cat $(PIDFILE)` 2>/dev/null || true; rm -f $(PIDFILE); fi
	$(DC) down

dev-logs:  ## tail the api and the worker
	$(DC) logs -f api worker

prod:  ## the same stack, with the unsafe parts removed
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-down:  ## stop the prod stack
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down
