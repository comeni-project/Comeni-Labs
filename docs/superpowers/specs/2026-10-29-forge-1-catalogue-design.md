# Forge MVP 1 — sources, catalogue and the tool page

**Issue:** #362 (parent #360). **Status:** written for review (2026-10-29).
**Design:** [the forge MVP design](2026-10-19-forge-mvp-design.md), story steps 1 and 2.
**Boards:** the canvas *Forge MVP pages* (claude.ai artifact `8T3V69ZSUr9wLydNUHrKhS`), boards
*1 · Catalogue* and *2 · An imported tool*.

*(operator)* marks a choice made in chat on 2026-10-29; *(spec)* marks this document's own call.

## Why

`main` has no forge since part 0 (#361): registry data is written by hand, and nobody can see
which of nf-core's ~2,100 modules the registry already holds. Part 1 is the forge's front door:
a catalogue of every nf-core module against the registry, and a page for each imported tool
showing what the registry says about it. Parts 2–5 hang their actions off these two pages.

## Goals

- **Sync** `nf-core/modules` into a stored catalogue, behind a `CatalogueSource` interface, with
  `NfCoreSource` as its only implementation. pegi3s (#65) becomes a second source later, not a
  rewrite.
- **Extract everything nf-core declares** about a module, not only what the board shows
  *(operator)*.
- **Compare** each module with the registry the app loads, giving its state.
- **The Registry tab**, the **catalogue page** and the **imported tool page**, drawn as boards 1
  and 2, in the shell's identity.

## Non-goals

- **The pull request states are placeholders** *(operator)*. *In review* and *Merged, not
  released* appear in the filter list with no modules in them, and say they arrive with pull
  requests. Part 4 (#365) reads GitHub and fills them, with the rest of the git work.
- **Forging, tests, publishing and releases** (parts 2–5). Their buttons and tabs are drawn but
  disabled, each saying which part brings it (*Forging comes in part 2*, and so on).
- **Following registry releases** (part 5). Until then "the registry" is the one the app loads.
- pegi3s, other registries, accounts.

## Anti-goals

- A state, version or topic the catalogue guessed and showed as fact. What cannot be extracted
  is shown as unknown, with why.
- A description on the tool page that nobody wrote. Prose comes from the registry (`tool.yml`,
  `because`) or from nf-core's `meta.yml`, labelled with its source.
- The catalogue writing to the registry. Part 1 reads only.

## What exists today (2026-10-29)

- **The registry** is loaded by `mendel_api/services/registry.py` from `MENDEL_REGISTRY_ROOT`
  (in development, the clone at `.run/registry`; in this repository's tests, the `registry/`
  submodule). Each tool has `tool.yml` (name, description, homepage, citation); each module a
  `module.yml` (licence, `upstream: {repo, sha, path}`, digest) and a `contract.yml` whose id
  carries the tool version (`nf-core/star/align@2.7.11b`), with ports, params and their
  `because`, `priority_because`, `container` and `provenance` (`approved_by`, `approved_at`).
  Rules live in `rules/` per role. Three modules have no contract; task 0 removes them (#410).
- **`comeni-vendor`** fetches a module from `nf-core/modules` into the registry and verifies its
  pin. It knows the repository URL and the `modules/nf-core` prefix.
- **`mendel_api/services/module_page.py`** builds a read-only page model for one contract (ports,
  roles, conformance counts, rules aiming at it, neighbours). No route serves it today.
- **The worker** (`mendel_api/worker.py`, ARQ) runs non-model jobs and has cron jobs.
- **Settings** *Registry & sources* reports the registry root, its layers and whether the GitHub
  token is set. Nothing to add for part 1.
- **The shell** (`frontend/src/app/Shell.tsx`) has the tabs *Build* and *Runs*.
- **Diagnostics**: `MF0001`–`MF0499` are retired; the new forge allocates from `MF0500`.

## The design

### 1. Sources *(spec)*

A new workspace package, **`packages/mendel-forge/`**, holds the forge's own code (the name is
free again since part 0). It is an **adapter package**: syncing clones a git repository, so it is
not on the purity list, and the purity guard keeps the pure packages from importing it.

- **`CatalogueSource`** (a `Protocol`): `name`, `sync(workdir) -> Snapshot` (fetch the newest
  upstream into a working folder and return its commit), and `modules(snapshot) ->
  Iterable[UpstreamModule]`. Nothing outside a source knows its layout.
- **`NfCoreSource`** keeps a shallow clone of `nf-core/modules` (`--depth 1`, refreshed by fetch)
  in a cache folder, and reads `modules/nf-core/**/meta.yml` folders. The clone URL and prefix are
  shared with `comeni-vendor`, not copied.
- **Parsing is pure**: a function from a module folder's files to an `UpstreamModule`, tested on
  recorded folders. It never raises on one bad module: a module it cannot read is kept with a
  coded problem (`MF05xx`) and shown as such, so the count is honest.

### 2. What is extracted *(operator: everything nf-core declares)*

`UpstreamModule`, per module folder:

- **From `meta.yml`:** name, description, keywords; each tool (name, description, homepage,
  documentation, source repository, DOI, licence, bio.tools identifier); every input and output
  (name, type, description, file pattern, EDAM ontology terms); authors and maintainers.
- **From `environment.yml`:** the conda packages and their versions.
- **From `main.nf`:** the container images (Docker and Singularity) and the process label.
- **From `tests/`:** the nf-test file's test names and the `test-datasets` paths they reference
  (parts 3's starting point; shown, not run).
- **From git:** the commit of the snapshot and, per module, the date of its last upstream change
  (the *Newest upstream change* sort). A depth-1 clone has no history, so this comes from one
  `git log` over the module paths after a deeper fetch, or from the GitHub API; **left to the
  builder**, with the rule that a date it cannot get is shown as unknown.

**The tool version** is the conda package version for the module's tool: the package whose name
matches the module's top-level name (`star` for `star/align`), else the first `meta.yml` tool's
name. When neither matches one package, the version is **unknown** with a coded reason, never
the first package's version. This is the version registry ids already carry. *Matches* is the
normalisation `tests/registry/test_tool_versions.py` (#407) already uses — case-insensitive,
ignoring `-` and `_`, so `trimgalore` matches `trim-galore` — moved into `mendel-forge` and
shared by the guard and the catalogue, so one rule decides both *(spec, after the builder
check)*.

**Reads or makes** are the input and output file extensions (from patterns) and EDAM format
terms, normalised to lower case. **Topics** are derived *(spec, operator to adjust)*: a small
mapping in `mendel-forge` from keywords and EDAM topic or operation terms to the board's topics
(genomics, metagenomics, alignment, assembly, variant calling, quality control, proteomics,
imaging, …). A module matching none has no topic, not a guessed one.

### 3. The stored catalogue *(spec)*

Tables in `mendel-api`, one Alembic migration:

- **`catalogue_sync`**: one row per sync — source, upstream commit, started, finished, outcome,
  counts, coded problems.
- **`catalogue_module`**: one row per (source, module path) — the extracted fields above as
  columns where they are filtered or sorted (name, tool version, topics, formats, last upstream
  change) and the rest as one JSONB document; the sync that last saw it. A module gone upstream
  is marked gone, not deleted.

**State is computed on read, not stored**, by comparing each row with the loaded registry (the
registry changes without a sync, and a stored state would go stale silently). The comparison is
a pure function in `mendel-forge`:

| State | When |
|---|---|
| **Imported** | the registry has a module with the same upstream path and a contract whose version equals nf-core's tool version |
| **Update available** | the registry has the module, and nf-core's tool version differs from the contract's *(spec: "differs", not "is newer": versions like `2.7.11b` do not order reliably, and the details panel shows both)* |
| **Not imported** | the registry has no module at that upstream path |
| **Unknown** | the tool version could not be extracted (above) and the registry has the module |
| **Gone upstream** | the registry has a module whose upstream path no longer exists in nf-core (renamed or removed). Listed and counted, from the registry's side, so a registry tool never vanishes from its own catalogue *(spec, after the builder check)* |
| *In review*, *Merged, not released* | placeholders until part 4 |

Filters, search and counts run in the database over the stored columns; the state filter is
applied after joining the registry's small set of upstream paths (tens of rows). Search covers
name, description, keywords, tool names and formats; the matching method (Postgres full text or
trigram) is the builder's. **Best match** (the default sort) is search relevance when there is a
query; with none, it orders by state — update available, imported, unknown, gone upstream, then
not imported — and by name within each, so what the registry already holds comes first
*(spec, after the builder check)*. Every sort ends on the module path, so pages are stable.

### 4. Sync *(spec)*

- A worker job **`sync_catalogue`**, on a daily cron and on demand (**Sync now** on the
  catalogue page, `POST /forge/catalogue/sync`), single-flight by ARQ job id.
- A sync that fails (no network, a bad clone) records its outcome and leaves the stored catalogue
  as it was. The page footer says when the last *successful* sync ran and, after a failure, that
  the catalogue is stale and why.
- Before the first sync the catalogue page says so and offers **Sync now**.
- The clone's cache folder is a volume in Compose, so a restart does not re-clone.

### 5. API *(spec)*

- `GET /forge/catalogue` — modules, filtered (`state`, `topic`, `format`, `source`, `q`), sorted
  (`best`, `name`, `upstream_changed`), paginated; with the filter counts and the last sync.
- `GET /forge/catalogue/{source}/{path}` — one module's full extraction and its state.
- `POST /forge/catalogue/sync` — start a sync; answers with the job.
- `GET /registry/tools/{contract_id}` — the imported tool page (§7), building on
  `module_page.py` rather than beside it.

Refusals are coded `MF05xx` through `coded()`, declared in `diagnostics.yml`. Clients are
regenerated with `make client`.

### 6. The catalogue page (board 1) *(operator, as drawn)*

`/registry` in the shell: a third tab **Registry**, with sub-tabs **Catalogue**, **Forging**
(disabled, part 2) and **Releases** (disabled, part 5). The header line says what the builder
uses: the registry's git commit (or tag, when the loaded registry is at one), not a release
until part 5.

Three columns, as the board draws them: **filters** (state with counts, topic, reads or makes,
source with pegi3s disabled as *later*), **the module list** (search, sort, rows of name and
description, reads → makes, tool version, state with its icon; a footer with the count shown and
the last sync), and **the selected module** (reads, makes, tool version, state, nf-core link, a
sentence on what comes next, one action). Actions: **Open the tool** for imported modules; for
the rest the action is drawn and disabled, saying forging comes in part 2. Filters live in the
URL query so a view is linkable. Scrolling loads more (the board's *scroll for more*). At phone
width the columns stack, filters first, collapsed.

### 7. The imported tool page (board 2) *(operator: in part 1)*

`/registry/tools/:id`, reached from **Open the tool**, breadcrumbed to the catalogue. Filled
from the registry, and only from it:

- **Heading:** the tool's name and description (`tool.yml`) and its state.
- **Reads and makes:** each port, its type and states, including *by convention, not required*
  with its `state_conventional_because`.
- **Settings:** each param with its default or *asks the person*, how it is passed (`via`,
  template), its domain and its `because`; fixed `ext_args` with theirs.
- **When the builder chooses it:** the rules of every role the contract fills (a rule belongs to
  a role, not a tool), with citations, and the contract's `priority` with `priority_because`.
- **Where it comes from:** contract id, upstream commit (linked), container, licence, who
  approved it and when (`provenance`), and the registry commit it is loaded from (a release in
  part 5).
- **From nf-core** *(spec)*: the catalogue's entry — `meta.yml` description, EDAM formats,
  authors and nf-core's current tool version — so an update's difference is visible.
- **Tests:** *No tests yet*, with **Add tests** disabled (part 3). **Re-forge** disabled
  (part 2).

What the board drew and the registry does not hold is not invented: the board's version
(`@1.11.0`) and release (`v0.4.0`) are illustrations; the page shows the registry's.

## Testing

- Parser and version extraction on recorded module folders committed as fixtures, including a
  multi-package environment, a missing `environment.yml`, a malformed `meta.yml` and an unmatched
  tool name. No network in tests; `NfCoreSource.sync` is tested against a local git repository.
- The state comparison on a fixture registry: each state, and a version that cannot be extracted.
- API tests through the test database: filters, counts, search, pagination, a failed sync leaving
  the catalogue intact.
- Frontend: Vitest for the pages' behaviour; the pages checked in a browser against boards 1 and
  2 at 1440 and 390 px, and in dark.
- A live sync against `nf-core/modules` once, by hand, recorded in the journal.

## Left to the builder

- The exact table columns and indexes; the search method.
- How the last upstream change date is obtained.
- The topic mapping's first contents (the operator adjusts it).
- Whether `module_page.py`'s model is extended or replaced for §7.

## Order of work

0. **Every registry module has a contract** (#410) *(operator)*. Three modules
   (`picard/markduplicates`, `samtools/faidx`, `bedtools/sort`) carry nf-core source and no
   `contract.yml`, left over from the old forge's drafting targets. Loading a layer refuses a
   module without a contract (a coded diagnostic, with a guard that fails against today's
   registry), and the three are removed from `comeni-registry` by pull request there, then the
   submodule is bumped. After this, §3's table holds: a registry module always has a contract
   version to compare.
1. `mendel-forge` package: `CatalogueSource`, the parser, `NfCoreSource`, the state comparison.
2. Tables, the sync job, the catalogue API.
3. The tool page API.
4. The Registry tab and the catalogue page.
5. The tool page.
6. Documentation: a how-to for browsing the catalogue, the reference for the new routes, the
   changelog.
