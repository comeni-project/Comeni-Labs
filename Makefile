# Development commands for Comeni Labs. Run `make help` to list targets.
# Sections: configuration; checks and tests; documentation; pipeline examples;
#           clients, migrations, and telemetry; development; local AI; production.
# Most Python commands use uv. Container targets need Docker Compose;
# pipeline gates also need Nextflow and Java.
# Start the app: make dev. Read the docs: make wiki-serve.
# Check changes: make test-db, then make check. Use make verify for pipeline execution checks.
# Each target below describes a command you can run as `make <name>`.

.PHONY: help registry-present names-free prepare database-ready check verify slow guards residue forge-ai-eval links doc-paths doc-sizes test test-db lint fmt types docs docs-status static stub profile forge clean demo-seed demo-fake-run \
	dev dev-down dev-logs dev-refresh prod prod-down client migrate wiki wiki-tools wiki-serve \
	ai-up ai-down ai-pull ai-logs

# -----------------------------------------------------------------------------
# 1. Configuration
# -----------------------------------------------------------------------------
# Run containers as the host user to keep mounted files writable and Git ownership consistent.
export DOCKER_UID := $(or $(DOCKER_UID),$(shell tools/command_env.py --setting DOCKER_UID $(shell id -u)))
export DOCKER_GID := $(or $(DOCKER_GID),$(shell tools/command_env.py --setting DOCKER_GID $(shell id -g)))

# Load dotenv in the recipe environment through Compose; never parse it as Make syntax.
SHELL := $(CURDIR)/tools/command_env.py
export

DC       := docker compose
RUN_DIR  := .run
PIDFILE  := $(RUN_DIR)/vite.pid
# npm updates this installation marker; compare it with the frontend lockfile.
NODEDEPS := frontend/node_modules/.package-lock.json
# Use the same wiki port for the container and host server; 8010 avoids the API default of 8000.
WIKI_PORT := $(shell tools/command_env.py --setting WIKI_HOST_PORT 8010)

# Test fixtures truncate rows. Use an isolated test server instead of the development database.
# Start and migrate it with make test-db before running database tests.
TEST_DB_CONTAINER := mendel-test-db
TEST_DB_IMAGE     := postgres:17-alpine
TEST_MENDEL_URL   := postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel
TEST_WIENER_URL   := postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener

# -----------------------------------------------------------------------------
# 2. Checks and tests
# -----------------------------------------------------------------------------
# Check for any registry files, since a layer does not require a fixed directory layout.
registry-present:  ## check that the registry submodule contains files
	@if [ -z "$$(ls -A registry 2>/dev/null)" ]; then \
	  echo "registry/ holds no registry data — it is a git submodule and was not checked out."; \
	  echo; \
	  echo "    git submodule update --init"; \
	  echo; \
	  echo "'git clone --recurse-submodules' avoids this. See .github/CONTRIBUTING.md."; \
	  exit 1; \
	fi

help:  ## list available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t20

# Use after editing code or documentation: this combines the regular tests and consistency checks.
check: registry-present lint test types docs docs-status links doc-paths doc-sizes  ## run repository checks and tests; use test-db for database coverage

# Keep the stages sequential, even when the caller passes -j; stop at the first failure.
# Use before validating a release or a change that affects pipeline execution.
verify:  ## run check, slow tests, and invariant guards in order (Docker and Nextflow)
	@$(MAKE) --no-print-directory -j1 check
	@$(MAKE) --no-print-directory slow
	@$(MAKE) --no-print-directory guards

# Execute Nextflow workflows and tool containers on test inputs; these checks can take minutes.
# Use after changing workflow generation or tool wiring. Regular tests exclude this group.
slow:  ## run pipeline execution tests (Docker and Nextflow; can take minutes)
	uv run pytest -m slow -v

# Guards are tests that catch violations of project boundaries and validation rules.
# Purity checks imports in deterministic packages; egress checks model-request schemas;
# construction checks that measurement profiles use approved validation paths.
# These run in make test too; use this smaller set when changing those boundaries.
guards:  ## check package boundaries, model-request fields, and measurement validation
	uv run pytest tests/guards/test_purity.py tests/guards/test_purity_runtime.py \
	  tests/guards/test_egress.py tests/guards/test_construction.py -v

# Audit the tests themselves: a guard should fail when someone introduces the problem it prevents.
# Estimate which guards lack that failure evidence in tests/fixtures/guard-ledger.md.
# This prints a report, not a pass/fail gate or a complete measure of test coverage.
residue:  ## report tests not yet recorded catching a bad change; ARGS=--list for details
	@uv run python tools/guard_residue.py $(ARGS)

# Inspect the examples and expected answers used to evaluate tool adaptation.
# This builds the evaluation data; it does not call a model or measure model performance.
forge-ai-eval:  ## build the Forge evaluation corpus and check answer keys; ARGS=--json for JSON
	@uv run python tools/forge_ai_eval.py $(ARGS)

# Point tests at the isolated server; unavailable database cases may skip unless required by CI.
test:  ## run tests against the isolated database prepared by test-db
	MENDEL_TEST_DATABASE_URL=$(TEST_MENDEL_URL) WIENER_TEST_DATABASE_URL=$(TEST_WIENER_URL) uv run pytest -v

# Reuse or create the test server on localhost:5442, then migrate both databases.
test-db:  ## start isolated PostgreSQL on localhost:5442 and migrate Mendel and Wiener
	@docker start $(TEST_DB_CONTAINER) >/dev/null 2>&1 || docker run -d --name $(TEST_DB_CONTAINER) \
	  -e POSTGRES_USER=mendel -e POSTGRES_PASSWORD=mendel -e POSTGRES_DB=mendel \
	  -p 127.0.0.1:5442:5432 $(TEST_DB_IMAGE) >/dev/null
	python3 tools/dev_services.py wait-db $(TEST_DB_CONTAINER)
	@docker exec $(TEST_DB_CONTAINER) psql -U mendel -qtAc "SELECT 1 FROM pg_database WHERE datname = 'wiener'" \
	  | grep -q 1 || docker exec $(TEST_DB_CONTAINER) psql -U mendel -qc 'CREATE DATABASE wiener'
	cd packages/mendel-api && MENDEL_DATABASE_URL=$(TEST_MENDEL_URL) uv run alembic upgrade head
	cd packages/wiener-api && WIENER_DATABASE_URL=$(TEST_WIENER_URL) uv run alembic upgrade head

# Find code mistakes and style problems without running the application.
lint:  ## check Python lint rules with Ruff
	uv run ruff check .

# Apply formatting changes to the files themselves; review the resulting diff.
fmt:  ## format Python files in place with Ruff
	uv run ruff format .

# Check the generated measurement type hints used by editors against registry declarations.
types:  ## check that generated measurement type stubs are current
	uv run python tools/generate_types.py --check

# Find explicit reminders left for the deferred Forge work; this is a search, not a test.
forge-rework:  ## list remaining FORGE-REWORK markers
	@grep -rn FORGE-REWORK packages/ frontend/src/ docs/notes/ 2>/dev/null \
	  | grep -v Binary || echo "nothing marked"

# -----------------------------------------------------------------------------
# 3. Documentation
# -----------------------------------------------------------------------------
# Use after moving or renaming documentation to catch broken links.
links:  ## check relative Markdown links
	uv run python tools/check_links.py

doc-paths:  ## check source paths mentioned in contributor and status documents
	uv run python tools/check_doc_paths.py

doc-sizes:  ## check the line budgets for CLAUDE.md (300) and now.md (150)
	uv run python tools/check_doc_sizes.py

# Use after changing schemas or documented behavior to find reference pages that need updating.
docs:  ## check generated diagnostics, protocol, and schema reference documentation
	uv run python tools/generate_diagnostics_doc.py --check
	uv run python tools/generate_protocol_doc.py --check
	uv run python tools/check_reference.py --check

# Check that documentation distinguishes implemented features from planned ones.
docs-status:  ## check wiki implementation-status labels
	uv run python tools/docs_status.py --check

wiki-tools:  ## generate the tool catalogue and registry documentation
	uv run mendel docs --registry registry/ --out docs/reference/tools/
	uv run python tools/generate_tools_catalogue.py

# Generate the tool catalogue before MkDocs builds: mkdocs.yml links to that generated page.
wiki: wiki-tools  ## build the documentation into site/
	uv run --group docs mkdocs build --strict

# Serve documentation on the host without Docker, using WIKI_HOST_PORT when configured.
wiki-serve: wiki-tools  ## serve documentation on the host with live reload (default localhost:8010)
	uv run --group docs mkdocs serve --dev-addr 127.0.0.1:$(WIKI_PORT)

# -----------------------------------------------------------------------------
# 4. Pipeline examples and Forge demo
# -----------------------------------------------------------------------------
# Check generated workflow syntax and connections before running an analysis.
static:  ## build the RNA-seq example and run lint/preview gates (Nextflow)
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate lint
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate preview

# Populate a local demo with saved examples; this writes data through the running APIs.
demo-seed:  ## add the example pipeline and fake runs to the running stack
	uv run python tools/seed_demo.py --fake-runs

demo-fake-run:  ## add a running demo record without launching Nextflow
	uv run python tools/seed_demo.py --fake-running

# Exercise the workflow with lightweight tool stand-ins to check how steps connect.
# This checks execution wiring, not the biological correctness of analysis results.
stub:  ## build the RNA-seq example and run its stub gate (Docker and Nextflow)
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub

# Generate the workflow for measuring input properties; this command does not execute it.
profile:  ## emit an input-profiling pipeline into profile-build/
	uv run mendel profile --have fastq.reads --out profile-build/

clean:  ## remove build outputs and Python test/lint caches
	rm -rf build/ profile-build/ dist/ .pytest_cache/ .ruff_cache/

# Recreate .forge-demo and demonstrate drafting a tool.
# Verification can refuse an incomplete draft; ignore that exit status for this demo.
forge:  ## recreate .forge-demo, draft an nf-core tool, and show verification findings
	@rm -rf .forge-demo
	uv run forge draft nf-core:samtools/sort --name sort --version 1.21.0 \
	  --workspace .forge-demo
	@echo
	uv run forge verify sort --workspace .forge-demo || true

# -----------------------------------------------------------------------------
# 5. API clients, migrations, and telemetry
# -----------------------------------------------------------------------------
# Update the browser's generated API descriptions after changing either API; this overwrites generated files.
client:  ## regenerate Mendel and Wiener TypeScript clients from OpenAPI
	uv run python -c "import json; from mendel_api.main import create_app; print(json.dumps(create_app().openapi()))" > frontend/openapi.json
	cd frontend && npx openapi-typescript openapi.json -o src/api/schema.d.ts
	uv run python -c "import json; from wiener_api.main import create_app; print(json.dumps(create_app().openapi()))" > frontend/openapi.wiener.json
	cd frontend && npx openapi-typescript openapi.wiener.json -o src/wiener/api/schema.d.ts

# Bring Mendel's database structure up to date after a schema change, using its configured database.
migrate:  ## apply Mendel database migrations
	cd packages/mendel-api && uv run alembic upgrade head

# Start the optional monitoring tools when investigating execution timings and traces.
telemetry:  ## start ClickHouse, the collector, and Grafana (default dashboard port 3001)
	docker compose --profile telemetry up -d clickhouse otel-collector grafana
	@echo "OTLP on localhost:4317 · boards on http://localhost:3001"
	@echo "point Wiener at it:  export WIENER_OTLP_ENDPOINT=http://localhost:4317"

# Apply the same kind of schema update to Wiener's separate database.
wiener-migrate:  ## apply Wiener database migrations
	cd packages/wiener-api && uv run alembic upgrade head

# -----------------------------------------------------------------------------
# 6. Development stack
# -----------------------------------------------------------------------------
# Prepare the registry, host frontend dependencies, and tool catalogue before starting Compose.
# The host Vite server refreshes the browser as frontend source files change.
database-ready: prepare  ## refuse an unverified switch from legacy PostgreSQL volumes
	python3 tools/consolidate_postgres.py check

prepare:  ## prepare writable local state and safely refresh the registry
	python3 tools/dev_services.py prepare

dev: database-ready prepare names-free $(NODEDEPS) wiki-tools  ## start the app with bounded Vite startup
	$(DC) up -d --build
	python3 tools/dev_services.py vite
	@echo "Built app: http://localhost:$${WEB_HOST_PORT:-80}/"
	@echo "Mendel API: http://localhost:$${API_HOST_PORT:-8000}/docs"
	@echo "Wiki: http://localhost:$(WIKI_PORT)/"
	@echo "Logs: make dev-logs; Vite: .run/vite.log"

# Refresh host frontend dependencies when the lockfile changes, before Vite starts.
$(NODEDEPS): frontend/package-lock.json
	@echo "frontend dependencies changed — installing"
	cd frontend && npm install

# Read container names from Compose so .env overrides and defaults match the upcoming startup.
# Report names owned by another project; skip the check if the configuration cannot be read.
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

# Preparation creates the clone before attempting any refresh, even under make -j.
dev-refresh: prepare  ## fast-forward a clean registry; preserve dirty, ahead or divergent work

# Stop the recorded Vite process group and Compose containers; keep named volumes.
dev-down:  ## stop Vite and the development stack
	@if [ -f $(PIDFILE) ]; then kill -- -`cat $(PIDFILE)` 2>/dev/null || true; rm -f $(PIDFILE); fi
	$(DC) down

# Follow server output when a page or background job fails; Ctrl+C stops viewing logs.
dev-logs:  ## follow Mendel API and worker logs
	$(DC) logs -f api mendel-worker

# -----------------------------------------------------------------------------
# 7. Local AI
# -----------------------------------------------------------------------------
# Start local models explicitly. ai-up may pull the server image; ai-pull downloads model weights.
# ai-down stops the server and keeps downloaded models.
AI_MODEL ?= $(shell tools/command_env.py --setting AI_MODEL qwen2.5-coder:14b)
# Set OLLAMA_GPU=rocm to add the AMD device overlay; leave unset for the base configuration.
OLLAMA_GPU ?= $(shell tools/command_env.py --setting OLLAMA_GPU "")
DC_AI = $(DC) $(if $(OLLAMA_GPU),-f docker-compose.yml -f docker-compose.ollama-$(OLLAMA_GPU).yml)

# Print a Compose service URL: workers reach Ollama at ollama:11434, not their own localhost.
ai-up:  ## start Ollama without downloading model weights; print configuration
	$(DC_AI) --profile ai up -d ollama
	@echo
	@echo "put these in .env, then \`make dev\` (or restart ai-worker):"
	@echo "  COMENI_AI_MODEL=ollama_chat/$(AI_MODEL)"
	@echo "  COMENI_AI_BASE_URL=http://ollama:11434"
	@echo
	@echo "the model itself:  make ai-pull MODEL=$(AI_MODEL)"

# Use when the model you want is not in local storage; downloading weights may take time and disk space.
ai-pull:  ## download model weights; set MODEL=, for example MODEL=qwen2.5-coder:14b
	@test -n "$(MODEL)" || { echo "MODEL= is required, e.g. make ai-pull MODEL=$(AI_MODEL)"; exit 2; }
	$(DC_AI) --profile ai up -d ollama
	$(DC_AI) --profile ai exec ollama ollama pull $(MODEL)
	@echo "pulled $(MODEL) — set COMENI_AI_MODEL=ollama_chat/$(MODEL)"

ai-logs:  ## follow AI worker and Ollama logs
	$(DC_AI) --profile ai logs -f ai-worker ollama

ai-down:  ## stop Ollama and retain downloaded models
	$(DC_AI) --profile ai stop ollama

# -----------------------------------------------------------------------------
# 8. Production overrides
# -----------------------------------------------------------------------------
# Prepare writable state before applying the production overlay.
# Use to exercise the built browser app and production overrides, without the host Vite server.
prod: database-ready prepare  ## prepare state and start the stack with production overrides
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-down:  ## stop the production stack and retain named volumes
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down
