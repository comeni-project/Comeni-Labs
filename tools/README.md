# Repository tools

These scripts generate derived files, check repository contracts and support local demos and
model experiments. Run commands from the repository root after `uv sync`. Some also need the
registry submodule, frontend dependencies or a running application; requirements are listed below.

Use the [Makefile](../Makefile) targets when provided. They specify the intended check mode and
order related generators. For scripts with an argument parser, `uv run python tools/<file> --help`
shows their options. The prompt-cache probe and some generators use positional arguments or
simple flags rather than a help parser; follow their documented commands.

## Development startup

| Tool | Entry point | Behavior |
|---|---|---|
| [command_env.py](command_env.py) | Make recipe shell | Loads root `.env` with the Compose CLI, preserving dotenv semantics and inherited overrides, then executes the recipe. Requires Python 3 and Compose when `.env` exists; no daemon is needed for parsing. Values are never evaluated as Make code. |
| [dev_services.py](dev_services.py) | `make prepare`, `make dev`, `make dev-refresh`, `make test-db` | Prepares runtime paths, safely fast-forwards the writable registry clone, checks Vite startup and bounds test-database readiness. Writes `.run/`; preserves local registry work and existing data. Vite failures report `.run/vite.log`. |
| [consolidate_postgres.py](consolidate_postgres.py) | `make database-ready`; `backup`, `restore`, `verify` subcommands | Requires Python 3.12+, Docker and PostgreSQL 17 client tools inside the database containers. Creates private backup archives/manifests, compares table data and sequence state, and records verified cutover. Restores into empty databases or accepts an already matching restore; never deletes source volumes. Stop application writers first. See [database operations](../ops/postgres/README.md). |

## Documentation and type checks

| Tool | Entry point | Reads or checks | Writes and limitations |
|---|---|---|---|
| [check_links.py](check_links.py) | `make links` | Local Markdown links in docs, repository entry points, `.github/` and `.design/`. | Reports missing targets; excludes historical notes/plans and exempts ignored generated docs. It does not check external URLs or anchors. |
| [check_doc_paths.py](check_doc_paths.py) | `make doc-paths` | Backticked source paths in the agent brief, current-work note and invariants. | Reports unresolved paths; recognizes the documentation location map. It does not scan every document. |
| [check_doc_sizes.py](check_doc_sizes.py) | `make doc-sizes` | Line budgets for `CLAUDE.md` and `docs/notes/now.md`. | Reports over-budget files without modifying them. |
| [check_reference.py](check_reference.py) | `make docs` | Documented model fields, CLI coverage, egress counts and executable rule examples. | Reports disagreements with code. Requires the registry and workspace dependencies; it does not verify every architecture claim. |
| [docs_status.py](docs_status.py) | `make docs-status` | Future-feature notices and development-guide scope markers. | `--check` validates notices and the inventory; without it, writes `docs/reference/status.md`. An empty inventory does not establish feature completeness. |
| [generate_types.py](generate_types.py) | `make types` | Registry measurement declarations. | Writes the profile type stub without `--check`; check mode detects stale output. The stub supplies editor/type-checker information, while runtime validation remains in the implementation. |

`make docs`, `make docs-status` and `make types` check freshness; they do not regenerate files.
After reviewing an intentional change, run the relevant generator without `--check`, inspect the
diff and rerun the check. `make check` also runs tests; database coverage needs `make test-db`.

## Generated documentation and site compatibility

| Tool | Inputs | Output or role |
|---|---|---|
| [generate_diagnostics_doc.py](generate_diagnostics_doc.py) | Shared diagnostic declarations. | Writes `docs/reference/pipelines/diagnostics.md`; `--check` compares without writing. |
| [generate_protocol_doc.py](generate_protocol_doc.py) | The authoring protocol declaration. | Writes the protocol diagram; `--check` detects stale, missing or orphaned pages. Write mode removes obsolete generated pages and preserves hand-written pages. |
| [generate_tools_catalogue.py](generate_tools_catalogue.py) | Tool pages previously emitted by `mendel docs`. | Writes the catalogue grouped by organization. Use `make wiki-tools` to generate tool pages first. |
| [documentation_theme.py](documentation_theme.py) | MkDocs `extra.stage`. | Generates the stage badge stylesheet during each site build. The adjacent [theme override](documentation_theme/main.html) preserves diagram source during local-file browsing. |
| [documentation_locations.py](documentation_locations.py) and [documentation_locations.json](documentation_locations.json) | Old-to-current documentation addresses. | Resolve historical source references and provide generated forwarding pages during a MkDocs build. These are library/configuration files, with no standalone CLI. |

`make wiki-tools` writes generated registry documentation under `docs/reference/tools/`.
`make wiki` then builds the site; `make wiki-serve` starts the documentation server. Both site
commands need the docs dependency group. Canonical authored pages remain in the Diátaxis paths.

## Reports and release support

| Tool | Command | Behavior |
|---|---|---|
| [guard_residue.py](guard_residue.py) | `make residue` or `make residue ARGS=--list` | Estimates refusal-shaped tests lacking recorded failure evidence in the guard ledger. Reads tests and the ledger; prints a report. Its classification and name matching are heuristics, not a coverage measure or pass/fail gate. |
| [forge_ai_eval.py](forge_ai_eval.py) | `make forge-ai-eval ARGS=--json` | Loads the registry and reports evaluation cases and available answer-key fields. Fails if a required contract is missing. Calls no model and produces no model-performance score. |
| [changelog_section.py](changelog_section.py) | `uv run python tools/changelog_section.py <package> <version>` | Prints one package's notes from the shared changelog for release automation. Rejects `Unreleased` and missing headings; writes no files. |
| [migrate_authoring_decisions.py](migrate_authoring_decisions.py) | `uv run python tools/migrate_authoring_decisions.py --dry-run` | Prints a read-only legacy-decision inventory against the configured Mendel database. Read-only is also the default. The Alembic upgrade owns migration application. |

## Demos and model experiments

These commands operate on services rather than temporary test fixtures. Choose the target
application deliberately; session and demo records remain after the command finishes.

| Tool | Prerequisites | Effects and output |
|---|---|---|
| [seed_demo.py](seed_demo.py) | Running Mendel API; the default RNA-seq goal and registry. Fake runs also need Wiener, kept draft files and Docker Compose access to its database. | Creates or refreshes a draft by name and keeps it by default. `--fresh` creates another draft; `--no-keep` skips keeping. Fake-run flags upload an artifact and insert simulated run/projection data through `psql`; they do not launch Nextflow. |
| [measure_models.py](measure_models.py) | Running builder and AI worker, a configured model connection and available models. Purpose settings must be editable. | Temporarily changes purpose-specific model settings, creates sessions and calls models. Prints outcome counts and median latency/token usage; attempts to restore prior settings in `finally`. Session/call records remain. |
| [probe_prompt_cache.py](probe_prompt_cache.py) | API container, registry and an Ollama server reachable as `ollama:11434`, with the selected model available. | Sends three direct model requests and prints server timings/token counts. `--split` separates fixed instructions from the question. Its internal prompt helpers must agree with the current application. |

For a local demo, use `make demo-seed` for completed fake runs or `make demo-fake-run` for a
simulated running record. To create only an editable draft:

```bash
uv run python tools/seed_demo.py --no-keep
```

Model comparison:

```bash
uv run python tools/measure_models.py --connection "Local Ollama" ollama_chat/gemma3:4b
```

The cache probe runs on the Compose network. With default container names:

```bash
docker cp tools/probe_prompt_cache.py mendel-api:/tmp/
docker exec mendel-api python /tmp/probe_prompt_cache.py gemma3:12b --split
```

Use the actual container name if `API_CONTAINER_NAME` was changed. Configure models through
[the model setup guide](../docs/how-to/development/configure-model.md); these experiments can
consume provider tokens or local compute.
