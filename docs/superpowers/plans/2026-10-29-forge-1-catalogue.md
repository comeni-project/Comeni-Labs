# Forge MVP 1 — catalogue and tool page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every nf-core module listed against the registry, with filters and search, and a page
for each imported tool, after first making every registry module carry a contract.

**Architecture:** A new adapter package `mendel-forge` holds the source interface, the nf-core
source (git), a pure parser and a pure state comparison. `mendel-api` stores the catalogue in two
tables, syncs it in the worker, and serves the catalogue and the tool page. The frontend adds a
*Registry* tab with the catalogue page and the tool page, drawn as boards 1 and 2.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLAlchemy 2 + Alembic (Postgres), ARQ, git CLI;
React, react-router, TanStack Query, Tailwind, Vitest.

**Status (2026-10-29):** done on `forge-1-catalogue` except Task 0 step 6, which waits on
comeni-registry#22. Deviations are listed at the end.

**Spec:** `docs/superpowers/specs/2026-10-29-forge-1-catalogue-design.md` (issues #362, #410).
Boards: canvas *Forge MVP pages*, `https://claude.ai/artifact/8T3V69ZSUr9wLydNUHrKhS`, boards
`Main.dc.html` (catalogue) and `Tool.dc.html` (tool page).

## Global Constraints

- Pure packages (`comeni-core`, `mendel-resolver`, `mendel-compiler`, …) never import
  `mendel-forge`; `mendel-forge` is an adapter (it runs `git`).
- No network in tests: git is exercised against a local repository made in `tmp_path`.
- New diagnostics: `MD0025` (loading) and `MF0500`–`MF0504` (forge), declared in
  `packages/comeni-core/src/comeni_core/diagnostics.yml`, emitted through `coded()`.
- Nothing shown as fact that was not extracted: unknown versions, topics and dates are `None`
  and the UI says *unknown*.
- *In review* and *Merged, not released* are placeholders: listed with count 0 and the note
  *Arrives with pull requests (part 4)*.
- Disabled actions say which part brings them: *Forging comes in part 2*, *Tests come in part 3*,
  *Releases come in part 5*.
- Registry changes land in a writable clone of `comeni-project/comeni-registry`, never in the
  detached `registry/` submodule; the operator merges that pull request.
- Generated clients are rebuilt with `make client`, never hand-edited.
- Python tests run from the repository root. Tests without a database: `uv run pytest <path>
  -q`. Database tests (`needs_db`): `make test-db` once, then
  `MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run
  pytest <path> -q` (written `DBTEST <path>` below).

## Review Focus

1. **A module folder nf-core half-wrote** (no `environment.yml`, or `meta.yml` failing to parse):
   kept, counted, shown with its coded problem, never dropping the sync. Test in Task 2.
2. **A sync that fails midway** (network drops after clone, parse error raised from a bug): the
   previous catalogue stays whole; nothing half-written. Test in Task 6.
3. **A second *Sync now* while one runs**: answers *already running*, not a second clone into the
   same folder. Test in Task 7.
4. **A contract id in a URL** (`nf-core/star/align@2.7.11b` has `/` and `@`): the tool page loads
   by direct link and on reload. Test in Tasks 8 and 10.
5. **Search text with SQL wildcard or quote characters** (`%`, `_`, `'`): treated literally.
   Test in Task 7.

---

### Task 0: Every registry module has a contract (#410)

**Files:**
- Registry (writable clone at `$SCRATCH/comeni-registry`): delete `tools/nf-core/picard/`,
  `tools/nf-core/bedtools/`, `tools/nf-core/samtools/faidx/`; regenerate docs
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py` (in `load`, after
  `registry = Registry.of(...)`)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (add `MD0025`; band comment)
- Test: `tests/registry/test_loading_diagnostics.py`
- Modify: `tests/fixtures/guard-ledger.md`
- Modify: `registry` submodule pointer

**Interfaces:**
- Produces: `MD0025` — *a module is declared with no contract binding it*. Refuses. Fires on
  `[build, upgrade, profile, publish, conformance, registry lint]`. Its message names the module
  id and its `module.yml` path. Fix text: add a `contract.yml` beside `module/`, or remove the
  module folder.

- [x] **Step 1: Write the failing test** `test_MD0025_a_module_without_a_contract` in
  `tests/registry/test_loading_diagnostics.py`: build `_layer(tmp_path)` with the baseline
  contract, add `tools/x/orphan/module.yml` declaring `module`, `id: nf-core/orphan`, and assert
  `"MD0025" in message` and `"nf-core/orphan" in message`. Add
  `test_a_module_bound_by_a_contract_in_another_layer_loads`: base layer holds the module, an
  overlay holds the contract whose `nf_include` keys to it; `layers.load([base, overlay])` loads.
- [x] **Step 2: Run** `uv run pytest tests/registry/test_loading_diagnostics.py -k MD0025 -q`.
  Expected: FAIL, no `MD0025` raised.
- [x] **Step 3: Implement** in `load`: after `Registry.of`, compute
  `bound = {key_of(c.nf_include) for c in registry.all()}` and raise
  `coded("MD0025", ...)` for the first `module.id` (sorted) in `vendored.entries` not in `bound`.
  Declare `MD0025` in `diagnostics.yml` with `emitted_by: core`, `concern: loading`.
- [x] **Step 4: Run the new tests**: PASS. Then run `uv run pytest tests/registry -q`: expect the
  shipped-registry tests to FAIL with `MD0025` naming `nf-core/bedtools/sort`. **That failure is
  the guard's evidence** — record it in `tests/fixtures/guard-ledger.md` (test name, the defect
  it catches, the command, the failing output's first line, 2026-10-29).
- [x] **Step 5: Registry pull request.** `gh repo clone comeni-project/comeni-registry
  $SCRATCH/comeni-registry`, branch `remove-modules-without-contracts`, delete the three folders
  (and `picard/` and `bedtools/` whole, since nothing else is under them), run
  `uv run mendel docs --registry $SCRATCH/comeni-registry --in-place`, commit, push, open the pull
  request referencing Comeni-Labs#410. It loads under the old engine too, so no `ENGINE_REF`
  bump. **Stop and ask the operator to merge it.**
- [ ] **Step 6: Bump the submodule** to the merged commit:
  `git -C registry fetch && git -C registry checkout origin/main`, then
  `uv run pytest tests/registry -q`: PASS.
- [x] **Step 7: Run** `make check`: PASS. Commit (`fix(registry): a module without a contract
  refuses to load (#410)`).

### Task 1: `mendel-forge` package and the upstream module model

**Files:**
- Create: `packages/mendel-forge/pyproject.toml` (modelled on `comeni-vendor`'s; depends on
  `comeni-core`, `pydantic`, `pyyaml`), `README.md`, `LICENSE` (copy of the repository's)
- Create: `packages/mendel-forge/src/mendel_forge/__init__.py`, `model.py`, `versions.py`
- Modify: root `pyproject.toml` (`dependencies`, `[tool.uv.sources]`), regenerate `uv.lock`
  with `uv lock`
- Modify: `packages/mendel-api/pyproject.toml` (depend on `mendel-forge>=0.1.0`)
- Modify: `tests/registry/test_tool_versions.py` (use `mendel_forge.versions`)
- Test: `packages/mendel-forge/tests/test_versions.py`

**Interfaces:**
- Produces, in `mendel_forge.model` (frozen Pydantic models, `extra="forbid"`):
  - `Channel(name: str, type: str | None, description: str | None, pattern: str | None,
    ontologies: list[str])` — one input or output.
  - `UpstreamTool(name: str, description: str | None, homepage: str | None,
    documentation: str | None, tool_dev_url: str | None, doi: str | None,
    licence: list[str], biotools: str | None)`.
  - `CondaPackage(channel: str | None, name: str, version: str)`.
  - `NfTest(name: str, datasets: list[str])`.
  - `Problem(code: str, says: str)`.
  - `UpstreamModule(source: str, path: str, name: str, description: str | None,
    keywords: list[str], tools: list[UpstreamTool], inputs: list[Channel],
    outputs: list[Channel], authors: list[str], maintainers: list[str],
    packages: list[CondaPackage], tool_version: str | None, containers: list[str],
    label: str | None, tests: list[NfTest], topics: list[str], formats_in: list[str],
    formats_out: list[str], upstream_changed: datetime | None, problems: list[Problem])`.
    `path` is the module path under the source (`star/align`).
- Produces, in `mendel_forge.versions`:
  - `same_name(a: str, b: str) -> bool` — lower-cased, `-` and `_` removed, equal.
  - `parse_packages(environment_yml: str) -> list[CondaPackage]` — `PIN` regex from
    `test_tool_versions.py`, moved here.
  - `tool_version(packages: list[CondaPackage], module_path: str, tool_names: list[str]) ->
    str | None` — the one package `same_name` to `module_path`'s first segment, else to
    `tool_names[0]`; `None` when zero or several match.

- [x] **Step 1: Write failing tests** in `test_versions.py`:
  `test_trimgalore_matches_trim_galore` (`tool_version([CondaPackage(channel="bioconda",
  name="trim-galore", version="0.6.10")], "trimgalore", []) == "0.6.10"`);
  `test_the_tool_not_the_first_package` (packages `htslib 1.21`, `samtools 1.21`, `star 2.7.11b`,
  path `star/align` → `"2.7.11b"`); `test_falls_back_to_the_meta_tool_name` (path
  `foo/bar`, tool names `["baz"]`, packages `baz 1.0`, `htslib 1.21` → `"1.0"`);
  `test_several_matches_is_unknown` (path `bwa/mem`, packages `bwa 0.7.19` and `BWA 0.7.18` →
  `None`);
  `test_no_match_is_unknown_not_a_guess` (path `foo`, packages `bar 1.0` → `None`).
- [x] **Step 2: Run** `uv run pytest packages/mendel-forge/tests -q`: FAIL (no module).
- [x] **Step 3: Implement** the package, models and `versions.py`; switch
  `test_tool_versions.py` to `parse_packages` + `tool_version` (its behaviour unchanged).
- [x] **Step 4: Run** `uv run pytest packages/mendel-forge/tests tests/registry/test_tool_versions.py
  -q`: PASS. `uv lock --check`: OK. `make guards`: PASS (purity unaffected).
- [x] **Step 5: Commit** (`feat(forge): the mendel-forge package and the shared tool-version rule
  (#362)`).

### Task 2: Parse one nf-core module folder

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/nfcore/parse.py`
- Create: fixtures `packages/mendel-forge/tests/fixtures/nf-core/` — real copies of
  `star/align`, `fastqc`, `bwa/mem`, `samtools/sort` (meta.yml, environment.yml, main.nf,
  tests/main.nf.test) taken from `nf-core/modules` at one commit (recorded in a `SOURCE.md`),
  plus hand-made `broken-meta/` (invalid YAML), `no-environment/`, `two-tools/` (no package
  matches)
- Test: `packages/mendel-forge/tests/test_parse.py`

**Interfaces:**
- Consumes: Task 1 models, `tool_version`.
- Produces: `parse_module(folder: Path, path: str, source: str = "nf-core") -> UpstreamModule`.
  Never raises for module content; problems are `Problem("MF0500", ...)` (*a module's
  `meta.yml` cannot be read*) and `Problem("MF0501", ...)` (*no package is the module's tool:
  version unknown*). `topics`, `formats_*` and `upstream_changed` are left empty here (Tasks 3
  and 4 fill them).

nf-core's current `meta.yml` nests channels as lists of single-key maps (`input: [[{meta: …},
{reads: {type, description, pattern, ontologies: [{edam: url}]}}]]`); older modules use a flat
list. Parse both; a channel is every non-`meta*` key. Containers come from `main.nf`'s
`container` expression: collect every quoted image string in it. The label is the first
`label 'process_*'`. nf-test names come from `test("...")`; datasets from every
`params.modules_testdata_base_path + '...'` or `test-datasets` path string.

- [x] **Step 1: Write failing tests**: `test_star_align_reads_everything` (name `star/align`,
  `tool_version == "2.7.11b"`, an input named `reads` with an EDAM ontology URL, outputs include
  `bam`, `containers` nonempty, `label == "process_high"`, `tests` nonempty with a dataset path);
  `test_flat_and_nested_channel_shapes_agree` (fastqc vs star/align both give `Channel`s);
  `test_broken_meta_is_kept_with_MF0500` (returns a module with `problems[0].code == "MF0500"`
  and `name == "broken-meta"`); `test_missing_environment_gives_unknown_version_MF0501`;
  `test_two_tools_gives_unknown_version_MF0501`.
- [x] **Step 2: Run** `uv run pytest packages/mendel-forge/tests/test_parse.py -q`: FAIL.
- [x] **Step 3: Implement** `parse_module`; declare `MF0500`, `MF0501` in `diagnostics.yml`
  (`emitted_by: forge`, `refuses: false`) and update the band comment to `MF0500-MF0599 the
  forge: the catalogue`.
- [x] **Step 4: Run**: PASS. Commit (`feat(forge): read everything an nf-core module declares`).

### Task 3: Topics and formats

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/topics.py`
- Test: `packages/mendel-forge/tests/test_topics.py`

**Interfaces:**
- Produces: `TOPICS: dict[str, frozenset[str]]` — topic → keywords/EDAM labels that select it.
  First contents: `genomics`, `metagenomics`, `alignment`, `assembly`, `variant calling`,
  `quality control`, `transcriptomics`, `epigenomics`, `proteomics`, `imaging`, `phylogenetics`.
  `topics_of(keywords: list[str], ontologies: list[str]) -> list[str]` (sorted, possibly empty);
  `formats_of(channels: list[Channel]) -> list[str]` — extensions from each `pattern`
  (`*.{fastq,fq}.gz` → `fastq`, `fq`; compression suffixes `gz`, `bz2`, `zst` dropped), lower
  case, sorted, unique. `parse_module` calls both.

- [x] **Step 1: Failing tests**: `test_alignment_keyword_gives_alignment`;
  `test_no_match_gives_no_topic` (`topics_of(["frobnicate"], []) == []`);
  `test_brace_patterns_expand_and_drop_compression` (`formats_of([Channel(pattern=
  "*.{fastq,fq}.gz", ...)]) == ["fastq", "fq"]`); and in `test_parse.py`,
  `test_star_align_has_topics_and_formats` (`"alignment" in m.topics`, `"bam" in m.formats_out`).
- [x] **Step 2–4:** run (FAIL), implement, run (PASS).
- [x] **Step 5: Commit** (`feat(forge): topics and formats from nf-core's own words`).

### Task 4: `CatalogueSource` and `NfCoreSource`

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/source.py`,
  `packages/mendel-forge/src/mendel_forge/nfcore/source.py`
- Modify: `packages/mendel-forge/pyproject.toml` (depend on `comeni-vendor>=0.1.0`, whose
  `ops.REPOS` and `ops.PREFIX` give the clone URL and `modules/nf-core`, unchanged)
- Test: `packages/mendel-forge/tests/test_nfcore_source.py`

**Interfaces:**
- Produces, in `mendel_forge.source`:
  - `Snapshot(source: str, commit: str, root: Path)` (frozen dataclass).
  - `class CatalogueSource(Protocol)`: `name: str`; `sync(self, cache: Path) -> Snapshot`;
    `modules(self, snapshot: Snapshot) -> Iterator[UpstreamModule]`.
  - `class SourceUnavailable(Exception)` — raised by `sync` for a failed clone or fetch, with
    git's stderr.
- Produces: `NfCoreSource(url: str = REPOS["nf-core"])`, `name = "nf-core"`. `sync` makes or
  refreshes a **blobless** clone (`git clone --filter=blob:none --no-checkout`, then
  `git fetch` + `git checkout --detach origin/HEAD -- modules/nf-core` on later syncs) in
  `cache / "nf-core-modules"`. `modules` walks `modules/nf-core/**/meta.yml`, calls
  `parse_module`, and fills `upstream_changed` from **one** pass of
  `git log --format=%x00%cI --name-only -- modules/nf-core` (newest first; the first date seen
  for a module's folder is its last change).

- [x] **Step 1: Failing tests** against a local repository built in `tmp_path` with
  `modules/nf-core/fastqc/` and `modules/nf-core/star/align/` copied from Task 2's fixtures in
  two commits with fixed dates (`GIT_COMMITTER_DATE`): `test_sync_clones_and_reports_the_commit`;
  `test_modules_lists_both_with_their_last_change` (star/align's date is the second commit's);
  `test_a_second_sync_sees_a_new_module`; `test_unreachable_url_raises_SourceUnavailable`
  (`NfCoreSource("file:///nonexistent")`).
- [x] **Step 2–4:** run (FAIL), implement, run (PASS).
- [x] **Step 5: Commit** (`feat(forge): the catalogue source interface and nf-core behind it`).

### Task 5: The state comparison

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/state.py`
- Test: `packages/mendel-forge/tests/test_state.py`

**Interfaces:**
- Consumes: `mendel_resolver.layers.Layers` (`.modules`, `.registry.all()`), `key_of`.
- Produces:
  - `class State(StrEnum)`: `IMPORTED = "imported"`, `UPDATE = "update_available"`,
    `NOT_IMPORTED = "not_imported"`, `UNKNOWN = "unknown"`, `GONE = "gone_upstream"`,
    `IN_REVIEW = "in_review"`, `MERGED = "merged_not_released"` (the last two never returned in
    part 1).
  - `Held(module_id: str, contract_id: str, version: str, upstream_path: str)` — one registry
    module bound by its contract.
  - `held(stack: Layers) -> dict[str, Held]` keyed by upstream path (`star/align`, from
    `Module.upstream.path` minus `modules/nf-core/`); modules without `upstream` are skipped.
  - `state_of(path: str, tool_version: str | None, held: dict[str, Held]) -> State`.
  - `gone(held: dict[str, Held], upstream_paths: set[str]) -> list[Held]`.
  - `BEST_ORDER: tuple[State, ...] = (UPDATE, IMPORTED, UNKNOWN, GONE, NOT_IMPORTED)`.

- [x] **Step 1: Failing tests** (fixture `held` dicts, plus one test on the shipped registry):
  `test_same_version_is_imported`; `test_different_version_is_update_available`
  (`"2.7.11a"` vs held `"2.7.11b"` → `UPDATE`, not ordered); `test_absent_is_not_imported`;
  `test_unknown_version_of_a_held_module_is_unknown`;
  `test_unknown_version_of_an_absent_module_is_not_imported`;
  `test_a_held_path_missing_upstream_is_gone`;
  `test_the_shipped_registry_holds_star_align` (`held(layers.load(REGISTRY))["star/align"]
  .version == "2.7.11b"`).
- [x] **Step 2–4:** run (FAIL), implement, run (PASS).
- [x] **Step 5: Commit** (`feat(forge): a module's state against the registry, computed on read`).

### Task 6: Tables and the sync

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py` (two tables)
- Create: `packages/mendel-api/migrations/versions/<rev>_forge_catalogue.py`
  (`down_revision = "d2a6c8e4f1b7"`)
- Create: `packages/mendel-api/src/mendel_api/services/catalogue.py`
- Modify: `packages/mendel-api/src/mendel_api/settings.py` (`forge_cache: Path =
  Path("./.run/forge")`)
- Modify: `packages/mendel-api/src/mendel_api/worker.py` (job + daily cron at 03:00)
- Modify: `docker-compose.yml` (`mendel-worker`: `./.run/forge:/app/forge`, env
  `MENDEL_FORGE_CACHE=/app/forge`)
- Test: `packages/mendel-api/tests/forge/test_catalogue_sync.py`

**Interfaces:**
- Produces tables:
  - `CatalogueSync` (`catalogue_sync`): `id` int pk, `source` str, `commit` str null,
    `started_at`, `finished_at` null (tz datetimes), `outcome` str (`running`, `ok`, `failed`),
    `modules` int null, `problems` int null, `error` text null.
  - `CatalogueModule` (`catalogue_module`): pk (`source`, `path`); `name` str; `tool_version`
    str null; `topics` ARRAY(str); `formats` ARRAY(str) (in ∪ out); `upstream_changed` tz
    datetime null; `search` text (name, description, keywords, tool names, formats joined,
    lower case); `document` JSONB (`UpstreamModule.model_dump(mode="json")`); `seen_in` int FK
    `catalogue_sync.id`; `gone` bool default false. Indexes on `name`, `tool_version`, GIN on
    `topics` and `formats`, trigram GIN on `search` (`CREATE EXTENSION IF NOT EXISTS pg_trgm` in
    the migration).
- Produces, in `services/catalogue.py`:
  - `run_sync(source: CatalogueSource | None = None) -> CatalogueSync` — records a `running`
    row, calls `source.sync(settings.forge_cache)`, upserts every module and marks rows not seen
    as `gone=True` **in one transaction** (`db.transaction()`), then `ok`; on any exception the
    module rows are untouched and the sync row is `failed` with `error`. Default source
    `NfCoreSource()`.
  - `last_sync() -> CatalogueSync | None` and `last_good_sync() -> CatalogueSync | None`.
- Produces, in `worker.py`: `async def sync_catalogue_job(ctx) -> int` (returns the sync id),
  in `WorkerSettings.functions` with `max_tries=1`, and `cron(sync_catalogue_job, hour=3,
  minute=0)`.

- [x] **Step 1: Failing tests** (`needs_db`, a fake `CatalogueSource` yielding Task 2 fixture
  modules): `test_a_sync_stores_every_module`; `test_a_module_gone_upstream_is_marked_not_deleted`;
  `test_a_failing_source_leaves_the_catalogue_whole` (first sync ok with two modules; second
  source raises after yielding one → still two rows, both `seen_in` the first sync, second sync
  row `failed`); `test_a_module_with_problems_is_stored_and_counted`.
- [x] **Step 2: Run** `make test-db`, then `DBTEST packages/mendel-api/tests/forge`: FAIL.
- [x] **Step 3: Implement** models, migration, service, worker job, setting and Compose mount;
  add `.run/forge` to `.gitignore` if `.run/` is not already ignored.
- [x] **Step 4: Run**: PASS. `cd packages/mendel-api && MENDEL_DATABASE_URL=<test url> uv run
  alembic downgrade -1 && uv run alembic upgrade head`: both succeed.
- [x] **Step 5: Commit** (`feat(api): the stored catalogue and its daily sync (#362)`).

### Task 7: The catalogue API

**Files:**
- Create: `packages/mendel-api/src/mendel_api/routes/forge.py` (`APIRouter(prefix="/forge",
  tags=["forge"])`), registered in `main.py`
- Modify: `services/catalogue.py` (queries)
- Modify: `diagnostics.yml` (`MF0502`, `MF0503`)
- Test: `packages/mendel-api/tests/forge/test_catalogue_api.py`

**Interfaces:**
- Produces response models (in `services/catalogue.py`):
  - `ModuleRow(source, path, name, description: str | None, formats_in: list[str], formats_out:
    list[str], tool_version: str | None, state: State, registry_version: str | None,
    contract_id: str | None, problems: list[Problem])`.
  - `Counts(states: dict[State, int], topics: dict[str, int], formats: dict[str, int],
    sources: dict[str, int])` — `in_review` and `merged_not_released` always present as 0.
  - `SyncView(outcome, finished_at, commit, error: str | None, stale: bool)` — `stale` when the
    last sync failed after a good one.
  - `CataloguePage(rows: list[ModuleRow], total: int, counts: Counts, last_good: SyncView | None,
    last: SyncView | None, next_offset: int | None, registry_at: str)` — `registry_at` from
    Task 8's `registry_label()`, defined in this task in `services/registry.py`: `git describe
    --tags --always` of the registry root, else `sha256:<registry.digest()>`.
  - `ModuleDetail(row: ModuleRow, module: UpstreamModule)`.
- Routes:
  - `GET /forge/catalogue?state=&topic=&format=&source=&q=&sort=best|name|upstream_changed&offset=0&limit=50`
    → `CataloguePage`. `topic` and `format` repeatable (any-of). Gone rows come from the
    registry's side: a `Held` with no live row is listed as `gone_upstream` with its registry
    name and version.
  - `GET /forge/catalogue/{source}/{path:path}` → `ModuleDetail`; unknown → 404 `MF0503`
    (*no module at that path in the catalogue*).
  - `POST /forge/catalogue/sync` → `202 {"queued": bool}`; `False` means already running
    (`enqueue("sync_catalogue_job", job_id="sync_catalogue")`). No sync possible because the
    queue is unreachable → 503 `MF0502`.
- `best`: with `q`, order by `similarity(search, q)` descending; without, by `BEST_ORDER` then
  `name`; every sort ends on `path`. `q` is passed as a bound parameter and matched with
  `ILIKE` on an escaped pattern plus trigram similarity, never interpolated.

- [x] **Step 1: Failing tests** (`needs_db`, `client` fixture, catalogue seeded through
  `run_sync` with a fake source and the shipped registry): `test_filters_by_state_and_counts`;
  `test_topic_and_format_filters_are_any_of`; `test_best_puts_held_modules_first`;
  `test_search_matches_description_and_ranks`; `test_search_wildcards_are_literal`
  (`q="%"` returns only rows whose text contains `%`; `q="'"` answers 200);
  `test_pages_are_stable` (offset 0 + offset 50 cover every row once);
  `test_pull_request_states_are_present_as_zero`;
  `test_unknown_module_is_MF0503`; `test_second_sync_request_says_already_queued` (monkeypatch
  `jobs.enqueue` to return `False` → `{"queued": false}`);
  `test_a_held_module_gone_upstream_is_listed`.
- [x] **Step 2–4:** `DBTEST packages/mendel-api/tests/forge/test_catalogue_api.py` (FAIL),
  implement, run again (PASS).
- [x] **Step 5:** `make client`; `cd frontend && npx tsc -b`: PASS. Commit
  (`feat(api): the catalogue, filtered, searched and paged`).

### Task 8: The tool page API

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/module_page.py` (extend `ModulePage`;
  its unused neighbour fields stay)
- Modify: `packages/mendel-api/src/mendel_api/routes/registry.py`
  (`GET /registry/tools/{contract_id:path}`)
- Modify: `diagnostics.yml` (`MF0504`)
- Test: `packages/mendel-api/tests/forge/test_tool_page.py`

**Interfaces:**
- Produces `ModulePage` additions: `name: str`, `description: str | None` (from the tool's
  `tool.yml`), `consumes`/`produces` ports gain `states_required: list[str]`,
  `states_conventional: list[str]`, `conventional_because: str | None`;
  `params: list[ParamView(name, default: object | None, asks_person: bool, via: str, template:
  str | None, domain: dict | None, because: str | None)]` (`asks_person` when `tier_hint == 4`
  and no default); `ext_args: str | None`, `ext_args_because: str | None`; `priority: int |
  None`, `priority_because: str | None`; `rules: list[RuleView(role, id, citation: str | None,
  branches: list[str])]` for every role the contract fills; `upstream: {repo, sha, path} | None`;
  `licence: str | None`; `approved_by: str | None`, `approved_at: str | None`;
  `registry_at: str` (Task 7's `registry_label()`); `catalogue: ModuleDetail | None` (Task 7's, by upstream path).
- Route: unknown contract id → 404 `MF0504` (*no tool with that id in the registry*).

- [x] **Step 1: Failing tests**: `test_star_align_page_carries_the_registry` (status 200 for
  `/api/registry/tools/nf-core/star/align@2.7.11b`; `star_ignore_sjdbgtf` has a `because`;
  `seq_platform.asks_person`; port `reads` has `states_conventional == ["trimmed"]`;
  `approved_by == "rafael"`; `rules` has role `alignment`; `registry_at` nonempty);
  `test_unknown_tool_is_MF0504`; `test_page_has_catalogue_when_synced` (`needs_db`).
- [x] **Step 2–4:** run (FAIL), implement, run (PASS).
- [x] **Step 5:** `make client`. Commit (`feat(api): an imported tool's page, from the registry`).

### Task 9: The Registry tab and the catalogue page

**Files:**
- Create: `frontend/src/registry/RegistryTabs.tsx` (sub-tabs; Forging and Releases disabled with
  their notes; header line *Builder uses comeni-registry <registry_at>*)
- Create: `frontend/src/registry/Catalogue.tsx`, `Filters.tsx`, `ModuleTable.tsx`,
  `Selected.tsx`, `useCatalogue.ts` (TanStack Query over `GET /forge/catalogue`, infinite by
  `next_offset`; filters in the URL query: `state`, `topic`, `format`, `q`, `sort`, `module`)
- Modify: `frontend/src/app/Shell.tsx` (`<Tab to="/registry">Registry</Tab>` after Runs),
  `frontend/src/app/router.tsx` (`/registry`)
- Test: `frontend/src/registry/Catalogue.test.tsx`, `frontend/src/app/Shell.test.tsx`

**Interfaces:**
- Consumes: Task 7's routes via the regenerated `components["schemas"]`.
- State labels and icons as board 1: *Imported* (check, teal), *Update available* (up arrow,
  amber), *In review* (branch, blue), *Merged, not released* (clock, grey), *Not imported*
  (dashed circle, grey), plus *Unknown* (question mark, grey) and *Gone upstream* (crossed
  circle, amber). Selected-panel action: *Open the tool* → `/registry/tools/<contract_id>` for
  imported/update/unknown/gone; otherwise a disabled button *Forge <name>* with *Forging comes
  in part 2*. Footer: *<shown> of <total> · nf-core/modules · synced <relative time>*, or
  *stale since <time>: <error>* after a failed sync; before any sync, an empty state with
  **Sync now**.

- [x] **Step 1: Failing tests** (mocked `get`): `renders rows, counts and the last sync`;
  `the state filter writes the URL and refetches`; `selecting a row fills the panel and links an
  imported tool`; `not imported shows a disabled forge action saying part 2`;
  `pull request states show 0 and the part 4 note`; `before any sync it offers Sync now`;
  Shell: `the Registry tab is present`.
- [x] **Step 2: Run** `cd frontend && npx vitest run src/registry src/app`: FAIL.
- [x] **Step 3: Implement**, following the shell's tokens (`text-ink`, `border-line`,
  `bg-paper`, …) and board 1's three columns; columns stack at phone width with filters
  collapsed behind a *Filters* button.
- [x] **Step 4: Run** vitest and `npx tsc -b`: PASS.
- [x] **Step 5: Browser check**: `make dev`, sync once (live, by hand), open `/registry` at
  1440 px and 390 px, light and dark; compare with board `Main.dc.html`. Fix differences.
- [x] **Step 6: Commit** (`feat(frontend): the registry catalogue, as board 1 draws it`).

### Task 10: The tool page

**Files:**
- Create: `frontend/src/registry/Tool.tsx` (+ `Tool.test.tsx`)
- Modify: `frontend/src/app/router.tsx` (`/registry/tools/*`, the splat is the contract id)

**Interfaces:**
- Consumes: Task 8's `GET /registry/tools/{contract_id}`.
- Sections as board 2: heading with state chip; *Reads and makes*; *Settings*; *When the builder
  chooses it*; aside *Where it comes from* (registry commit, not a release) and *Change it*
  (**Re-forge** disabled, *Forging comes in part 2*); *Tests* (*No tests yet*, **Add tests**
  disabled, *Tests come in part 3*); plus *From nf-core* (catalogue description, formats,
  authors, nf-core's version; *Not synced yet* when `catalogue` is null).

- [x] **Step 1: Failing tests**: `loads by direct link with a slash and an at sign in the id`
  (memory router at `/registry/tools/nf-core/star/align@2.7.11b` requests that exact id);
  `shows each param's reason and asks-the-person`; `update available shows both versions`;
  `re-forge and add tests are disabled with their part`; `an unknown id shows the MF0504
  refusal`.
- [x] **Step 2–4:** run (FAIL), implement, run (PASS); `npx tsc -b`.
- [x] **Step 5: Browser check** at 1440 and 390 px, light and dark, against `Tool.dc.html`;
  reload on the page to confirm the direct link.
- [x] **Step 6: Commit** (`feat(frontend): an imported tool's page, as board 2 draws it`).

### Task 11: Documentation and records

**Files:**
- Create: `docs/how-to/registry/browse-the-catalogue.md` (task-first: find a module, read its
  state, open a tool; what *unknown* and *gone upstream* mean; Sync now)
- Modify: the API reference page that lists routes (find it with
  `grep -rl "/registry/types" docs/reference`), `CHANGELOG.md` (Unreleased: `mendel-forge` new,
  `mendel-api`, `frontend`, `mendel-resolver` MD0025), `CLAUDE.md` source map (add
  `packages/mendel-forge/`; drop *the forge is being rebuilt* wording if now wrong), 
  `docs/notes/now.md` (the forge section: part 1 done, next part 2), a journal entry, this plan
  (ticks, deviations)
- Test: `make doc-sizes`, `make check`

- [x] **Step 1:** Write the pages; link the how-to from `docs/index.md`'s how-to list.
- [x] **Step 2: Run** `make check` and `make guards`: PASS. `make verify` is not required (no
  resolution, compiler or `pipeline.yml` change) — except that Task 0 changed loading, so run
  `make verify` once: PASS.
- [x] **Step 3: Commit** (`docs: forge part 1 — the catalogue how-to, changelog, journal, ticked
  plan (#362)`).

## Deviations

- Task 0: four test fixtures that deleted a contract and left its module now delete the folder;
  `MD0025` is `emitted_by: resolver`.
- Task 1: test files are `test_forge_*.py` (pytest's default import mode collides on basenames);
  `mendel-forge` depends on `comeni-vendor` and `mendel-resolver` from the start.
- Task 6: the new package reuses the name `mendel_forge`, so part 0's guard
  (`test_old_forge_gone.py`) names the old package's modules and routes instead.
- Task 7: counts are over the whole catalogue; a held module never seen by any sync is not
  listed as gone; *Sync now* checks for a running sync and keys the job id on the last sync.
- Task 8: `RuleView` carries each row's condition, choice, reason and citation (the rule files
  have no id); outputs carry `states_made`.
- After the live sync: tool versions ignore conda ecosystem prefixes (`r-`, `bioconductor-`,
  `perl-`, `python-`, `ncbi-`), taking unknown versions from 450 to 397 of 2,123; `prepare`
  makes `.run/forge`; the status page's links are relative to `reference/`.
- Tasks 9–10: *Show more* instead of loading on scroll; the registry line sits in the Registry
  bar; the table's scroll box uses `contain: inline-size` so pages fit at 390 px.
- The issues number the forge one ahead of the design (#363 is the tool page, built here).
