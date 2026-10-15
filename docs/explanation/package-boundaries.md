# Package responsibilities

Mendel constructs a pipeline artifact; Wiener executes that artifact. Shared packages describe
values or provide reusable adapters. The application packages connect those pieces to HTTP,
files, databases and queues. Sharing a PostgreSQL server does not transfer ownership of tables
between the applications.

This map covers workspace source, package manifests, consumers and representative tests.
Paths are relative to the repository root. Dependency statements describe imports in current
source, including function-local imports; dynamically loaded registry pieces are noted separately.
The static workspace import graph contains no cycle. That check does not cover every possible
runtime import or establish that every module is placed well.

## Workspace owners and interfaces

| Package | Owns and exposes | Direct workspace dependencies | Workspace consumers |
|---|---|---|---|
| `comeni-core` | Declared contracts and vocabularies, goals, decisions, IR, saved artifacts, egress shapes and settings declarations. Interfaces are the typed models and their validators. | None. | AI, vendor, resolver, compiler, authoring, Forge, both API packages and Wiener core. |
| `dag-core` | Domain-neutral graph nodes, edges and layout arithmetic in `dag_core/graph.py` and `layout.py`. | None. | Compiler, both APIs and Wiener core. |
| `comeni-inspect` | Record/outcome shapes, bounded codec reading, inspection runner, wire format and conformance harness. `comeni-inspect` is the subprocess entry point. | None. | Mendel API; registry codec, format and measure pieces also import its record/outcome shapes. |
| `comeni-ai` | Provider configuration and transport, response validation, closed choices, chat, prompt-file loading and recorded transports. Callers supply domain prompts and reply models. | Core. | Mendel API, Forge and the deprecated compatibility wrapper. |
| `comeni-vendor` | Fetching module source and checking content pins through `ops.py`; `cli.py` exposes `comeni-vendor`. | Core. | Forge. |
| `mendel-resolver` | Layer loading, routing, four-tier resolution, rules, replay and validation. Exposes `Layers`, routing/resolution functions and the `AmbiguityResolver` port. | Core. | Compiler, Forge and Mendel API. |
| `mendel-compiler` | Nextflow emission, module conformance, staging, pipeline-file handling and gates. The `mendel` CLI composes those operations. | Core, resolver and graph layout. | Forge and Mendel API. |
| `mendel-authoring` | Conversation protocol, interpreter, legal commands, blueprint projections and authoring calculations. Storage and model access are supplied by the application. | Core. | Mendel API. |
| `mendel-forge` | Registry adaptation: upstream discovery, scaffold holes, candidate generation, verification, review transitions and landing. Exposes typed operations and the `forge` CLI. | Core, resolver, compiler, vendor and AI. | Mendel API. |
| `mendel-api` | Mendel HTTP routes, stored drafts/sessions/decisions, registry and workspace integration, application settings, worker entry points and queue orchestration. | Core, authoring, resolver, compiler, Forge, AI, inspection and graph layout. | Browser and external HTTP clients; worker processes load it directly. No other workspace package imports it. |
| `wiener-core` | Event normalization, run-state folds, execution policy, timelines, series, graph views and telemetry descriptions. | Core and graph layout. | Wiener API. |
| `wiener-api` | Run/artifact persistence, launch and ingest processes, Redis fan-out, execution worker, telemetry export and HTTP routes. | Core, Wiener core and graph layout. | Browser and external HTTP clients; ingest and worker processes load it directly. No other workspace package imports it. |
| `mendel-ai` | Compatibility re-exports and a deprecation warning. It implements no AI behavior and has no source consumer elsewhere in this workspace. | AI. | Released external consumers may still use the old import. Removal is tracked separately. |

Package manifests declare installation dependencies; `src/<module>/__init__.py` records exported
names where the package has a facade. Submodule imports are also current interfaces: an `__all__`
list alone is insufficient evidence that a module can be moved without affecting callers.

## Meaningful source groups

### Shared models

These groups live under `packages/comeni-core/src/comeni_core/`.

| Group | Responsibility and boundary |
|---|---|
| `declared/` | Registry declarations, layer stacking, vocabularies, modules, tools and measurements. It describes registry data; resolver layer loading reads it from disk. |
| `goal/` | Requested outcomes, supplied inputs, measured profiles and premises. It does not select a route. |
| `plan/` | Draft graphs, resolved IR, decision records and tier classifications. Resolver calculations produce these values. |
| `artifact/` | Saved `Pipeline`, materialisation from supplied models, lockfile/digest values and emitted-file evidence. Compiler adapters read/write artifact files and emit Nextflow. |
| `egress/` | Typed outbound payloads and the boundary catalogue in `boundaries.py`. This catalogue describes allowed data; transport and protection checks live in callers. |
| `review/` | Questions, answers and verdict values shared by construction and registry review. |
| `spell/` | Marked strings, channel routes and process directive vocabulary. |
| `settings/` | Setting declarations, resolution, sections and storage interfaces. API adapters own PostgreSQL storage, secret encryption and service-specific installation construction. |
| Root modules | Diagnostic declarations and strict YAML loading. These are shared contracts, not application persistence. |

`comeni-inspect` keeps `records.py` and `outcome.py` separate from the runner. Registry pieces
import those shapes; `run.py`, `stream.py` and `wire.py` own execution and bounds, while
`harness.py` checks fixture reports. The API owns upload limits, trusted-layer selection,
subprocess launch and process timeout in `mendel_api/services/inspect.py`.

### Construction and authoring

| Source group | Responsibility |
|---|---|
| `mendel_resolver/rules/` | Rule shapes, loading/stacking and load-time validation. The rest of the resolver owns routing, premise evaluation, materialisation of drawn graphs and replay. `ports.py` supplies the adapter boundary for an unresolved choice. |
| `mendel_compiler/cli/` | Argument parsing, command composition and console rendering. Root modules own emission, conformance, gates, source staging and artifact-file I/O. Disk/subprocess work is not confined to the CLI. |
| `mendel_authoring/protocol.py`, `interpret.py`, `state.py`, `commands.py`, `types.py`, `payloads.py` | The declared conversation program, interpreter, legal transitions and values passed between actions. They do not own stored sessions. |
| Other `mendel_authoring` modules | Blueprint/draft projections, alternatives, amendments, decisions, gaps, needs, reviews, progress, pacing, memory and read-back calculations. `ports.py` describes the registry view those calculations need. |
| `mendel_api/authoring/` | Application-facing authoring shapes, immutable offer envelopes, canvas assembly, committed prompts and the model resolver adapter. Some values here are HTTP-specific; others support model interaction. |
| `mendel_api/stages/` | Persistence-aware action handlers bound to the pure protocol. `_rows.py` provides shared row operations and `_jobs.py` constructs queued work. `building/` groups amendments, cards and the step walk. |
| `mendel_api/services/` | Application use cases. Draft/decision/session modules own mutation and revisions; build/blueprint/registry modules compose the construction packages; sample/inspection modules own input handling; Forge modules adapt registry operations to stored jobs and review state; settings and retention modules own application lifecycle work. |
| `mendel_api/routes/` | HTTP validation, dispatch and serialization. The browser and external clients consume these endpoints, not the pure protocol directly. |
| `mendel_api/migration_data/` | Frozen converters used by historical Alembic revisions. They must remain independent of evolving runtime ORM/service implementations. |
| `mendel_api/models.py`, `decision_models.py`, `db.py`, migrations | Mendel-owned tables, transactions, decision history and migration chain. |

### Registry adaptation and reusable AI

| Source group | Responsibility |
|---|---|
| `mendel_forge/sources/` | Source adapters, upstream catalogues and normalization of observed metadata. These modules may perform network I/O. |
| Forge root modules | Typed operations, scaffold/workspace files, candidate verification, state vocabulary and controlled registry landing. `land.py` owns the registry-write boundary; application transactions remain outside the package. |
| `mendel_forge/ai/` | Dossier selection and budgets, proposal shapes, admission, bounded repair, rendering into candidate files and evaluation. These rules concern registry adaptation. |
| `mendel_forge/prompts/` | Forge-owned prompt text, versions and template lookup. |
| `mendel_forge/cli/` | Parsing and console rendering over the operation layer. It does not own a separate adaptation implementation. |
| `comeni_ai/access.py`, `client.py`, `formats.py` | Provider access, transport, validated responses and provider-specific response formats. |
| `comeni_ai/chat.py`, `choice.py`, `prompts.py`, `recorded.py` | Reusable conversation/choice helpers, loading/versioning of a caller's prompt files, and offline recorded transports. No subsystem's prompt text or database rows belong here. |

### Execution

| Source group | Responsibility |
|---|---|
| `wiener_core/state.py`, `events.py`, `policy.py`, `signals.py` | Interpret supplied events, fold state and decide typed actions. The caller performs actions and supplies clocks/events. |
| Other `wiener_core` modules | Graph, timeline, overview, resource-series and span descriptions derived from recorded state. The OpenTelemetry SDK is an API-side adapter. |
| `wiener_api/routes/` | Run, artifact and monitoring HTTP interfaces. |
| `wiener_api/services/` | Artifact storage, process launch, projections, live streams, telemetry export, retention, deletion and execution verbs. |
| Wiener root modules and migrations | Database models/repository/query shapes, settings, Redis jobs, app factories and worker composition. Wiener alone owns its schema and Alembic history. |

The frontend owns browser navigation, rendering and interaction state. Its Mendel and Wiener
clients use separate API surfaces; generated schema types are outputs of those interfaces.
Shared visual tokens do not justify sharing backend database tables. See the
[frontend guide](https://github.com/comeni-project/Comeni-Labs/blob/main/frontend/README.md).

## Runtime owners

| Process | Code entry point | Owns |
|---|---|---|
| Mendel API | `mendel_api.main:app` | Mendel routes, transactions and schema migration before serving. |
| Mendel ordinary worker | `mendel_api.worker.WorkerSettings` | `arq:queue`: gates, source checks/sync, scaffolding, publishing and scheduled maintenance. |
| Mendel AI worker | `mendel_api.ai_worker.AIWorkerSettings` | `arq:queue:ai`: builder calls and Forge generation/review calls. Application settings select access and concurrency. |
| Wiener API | `wiener_api.main:create_app` | Run-management requests and Wiener's schema migration before serving. |
| Wiener ingest | `wiener_api.main:create_ingest_app` | Accept execution events independently of the launch worker. |
| Wiener worker | `wiener_api.worker.WorkerSettings` | Execute run intents, fold/project events and perform execution-side maintenance through Wiener's Redis configuration. |

Both subsystems use one PostgreSQL server with separate databases and login roles. They retain
independent migrations and application models. Redis database 0 serves Mendel; database 1 serves
Wiener. Source sync performs network I/O but belongs to the ordinary queue because it does not
call a model. See [AI ownership](mendel-ai-ownership.md) for the call paths and recovery limits.

## Findings and decisions

1. **Mendel AI behavior and persistence share a module.**
   `mendel_api/services/authoring_ai.py` composes/admit replies, selects access and writes
   `AiInvocation` rows. Separating this requires explicit application adapters; moving the whole
   module into shared `comeni-ai` would move database and builder knowledge with it. Keep package
   boundaries now and use the proposed subpackage boundary in [#310](https://github.com/comeni-project/Comeni-Labs/issues/310).
2. **Builder invocation vocabulary depends on Forge.**
   The same module imports `Agent` and `InvocationState` from `mendel_forge.workflow`, while
   `mendel_api.models` stores invocations for both agents. A change to the generic invocation
   lifecycle therefore reaches a registry-adaptation module. First separate that vocabulary from
   Forge-specific adaptation states, preserving persisted enum strings and schema checks. Track
   this with the AI ownership work in #310; it is not evidence for combining every AI workflow.
3. **The compatibility package is easy to misread as a proposed new owner.**
   `mendel-ai` only re-exports `comeni-ai`; its tests prohibit new in-repo consumers. Remove it
   under [#298](https://github.com/comeni-project/Comeni-Labs/issues/298), after resolving its released-consumer compatibility policy. Do not put builder AI code there.
4. **Egress declarations need an explicit placement policy.**
   `comeni_core/egress/` describes both pipeline and Forge payloads, while protection and transport
   live in API/adaptor code. Keep those roles distinct; moving a shape must preserve boundary
   lookup and public imports. [#300](https://github.com/comeni-project/Comeni-Labs/issues/300) owns that schema/layout decision.

The remaining package placements have supported responsibilities in this review. Similar
Mendel/Wiener ORM helpers and settings adapters are independently owned; their resemblance
alone does not justify a new shared application package. A compiler containing filesystem and
subprocess adapters is also not a reason to weaken the resolver/authoring purity boundary.

Validation uses `tests/guards/test_purity.py`, `test_purity_runtime.py`, `test_egress.py` and
`test_inspector_pieces.py`, each package's tests, and API tests grouped by authoring, Forge,
pipelines, settings and infrastructure. The source/consumer map is evidence for review, not a
replacement for import, serialization and caller checks when a later move is implemented.
No package extraction or public-import rename is part of this ownership review.
