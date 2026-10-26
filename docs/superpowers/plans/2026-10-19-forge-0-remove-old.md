# Forge MVP 0 — Remove the Old Forge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the old forge — package, API, worker jobs, tables, screens, tests, docs — keeping only the model-call vocabulary the builder records with.

**Architecture:** Deletion in dependency order: first move what the builder still needs out of `mendel_forge`, then delete the API and worker code that reaches the forge, then the package itself, then the browser side, then documentation. The suite is green at the end of every task.

**Tech Stack:** Python 3.12 (uv workspace, FastAPI, SQLAlchemy, Alembic, arq), React 19, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-19-forge-0-remove-old-design.md` (issue #361).

## Global Constraints

- **Never bare `pytest` with the dev DB up:** database tests run through `make test-db` and `make test` only; confirm `MENDEL_DATABASE_URL` points at the isolated test database before running any fixture.
- No backward compatibility before v0.1.0: nothing is aliased, nothing migrated, no downgrade path.
- Stage explicit paths; never `git add -A` (`docs/notes/research/2026-10-17-why-not-mcp.md` is someone else's). Run checks separately before each commit.
- `uv.lock` is regenerated with `uv lock`, never hand-edited.
- Generated clients (`frontend/src/api/schema.d.ts`, `frontend/openapi.json`) are rebuilt with `make client`.
- The builder's behaviour does not change: authoring and build tests pass unmodified except for import paths.

## Review Focus

1. **The builder still records model calls** with the same `agent`, `purpose` and `state` values; a value lost in the move would break the `ai_invocation` check constraint at runtime, not import time. Task 1's test pins the value sets.
2. **The migration drops only the old forge's tables** (`forge_*`, `source_check`, `queue_visit`) and leaves `ai_invocation` rows whose `agent` is `forge` valid. Task 2's migration test.
3. **Home still loads** once `/attention` loses its `forge` half; the frontend type and Home's tests follow. Task 2 and Task 3.
4. **A diagnostic code still emitted somewhere** must not be deleted with the forge's band. Task 2 removes only codes nothing emits after the deletion, as the diagnostics guards report.
5. **Docs that link to deleted pages or paths** fail `make links` and `make doc-paths`; Task 4 runs both.

---

### Task 1: Move the model-call vocabulary out of the forge

**Files:**
- Create: `packages/mendel-api/src/mendel_api/invocations.py`
- Modify: `packages/mendel-api/src/mendel_api/models.py` (imports), `packages/mendel-api/src/mendel_api/services/authoring_ai.py` (import)
- Test: `packages/mendel-api/tests/infrastructure/test_invocations.py`

**Interfaces:**
- Produces: `mendel_api.invocations.Agent`, `InvocationPurpose`, `InvocationState` — `StrEnum`s with exactly the members `mendel_forge.workflow` has today (copy the members, not the forge's other enums).

- [x] **Step 1: Write the failing test**: `from mendel_api.invocations import Agent, InvocationPurpose, InvocationState`; assert each enum's set of values equals the current one (read the values from `mendel_forge/workflow.py` when writing the test and paste them as literals); assert `Agent.BUILDER == "builder"` and `Agent.FORGE == "forge"`.
- [x] **Step 2: Run** `make test-db` then `uv run pytest packages/mendel-api/tests/infrastructure/test_invocations.py` with the test database's URL (as `make test` sets it) — FAIL, module missing.
- [x] **Step 3: Create `invocations.py`** with the three enums and a docstring on what they record; point `models.py` and `authoring_ai.py` at it. `models.py` keeps importing the forge-only enums for the forge tables until Task 2 deletes those tables.
- [x] **Step 4: Run** `make test` — PASS.
- [x] **Step 5: Commit** `refactor(mendel-api): the model-call vocabulary moves out of the forge (#361)`.

### Task 2: Delete the old forge from the API, worker, database and workspace

**Files:**
- Delete: `packages/mendel-forge/` (whole package); `packages/mendel-api/src/mendel_api/routes/{forge,contracts,questions,sources,tools}.py`; `packages/mendel-api/src/mendel_api/services/{forge_adaptations,forge_candidate,forge_catalogue,forge_jobs,forge_overview,forge_review,forge_state,queue,sources,drift,answers,checked,tools,contracts}.py`; `packages/mendel-api/src/mendel_api/questions.py`; `packages/mendel-api/tests/forge/`; `tests/guards/test_forge_write_boundary.py`; `tools/forge_ai_eval.py`
- Create: `packages/mendel-api/migrations/versions/<rev>_the_old_forge_goes.py` (down-revision `a9d4e2c7b318`)
- Modify: `packages/mendel-api/src/mendel_api/main.py` (routers), `worker.py` (source sync, drift check), `ai_worker.py` (forge jobs, reclaim), `models.py` (delete `SourceCheck`, `QueueVisit`, `Forge*` and their imports), `shapes.py` (two `forge_*` shapes), `services/attention.py` (only `mendel`), `shape_versions.py` if it lists the tables, `packages/comeni-core/src/comeni_core/settings/catalogue.py` (Docker Hub, source check, GitHub token help), `packages/comeni-core/src/comeni_core/diagnostics.yml` (+ regenerate `docs/reference/pipelines/diagnostics.md`), `pyproject.toml`, `packages/mendel-api/pyproject.toml`, `uv.lock`, `Makefile` (forge targets), `tools/check_reference.py` (forge CLI), `tests/guards/test_purity.py` and `tests/support/purity.py` (adapter list), infrastructure tests that list routes, models, schedules or purposes
- Test: `packages/mendel-api/tests/infrastructure/test_old_forge_gone.py`

**Interfaces:**
- Consumes: `mendel_api.invocations` (Task 1).
- Produces: `GET /api/attention` returns `{ "mendel": [...] }` only.

- [x] **Step 1: Write the failing tests** in `test_old_forge_gone.py`:
  - `importlib.util.find_spec("mendel_forge") is None`;
  - `create_app().openapi()["paths"]` has no path starting `/api/forge`, `/api/contracts`, `/api/questions`, `/api/sources`, `/api/tools`, and still has `/api/attention`, `/api/pipeline/authoring`;
  - `Base.metadata.tables` has no name starting `forge_` and no `source_check`, `queue_visit`; still has `ai_invocation`;
  - after `alembic upgrade head` on the test database (the migration-test fixture the infrastructure tests already use), the database has no such table, and an `ai_invocation` row with `agent="forge"` inserted before the upgrade is still there;
  - a source scan: no `.py`, `.toml`, `Makefile`, `.yml` under the repository (excluding `docs/notes/`, `docs/superpowers/`, `.git`, `node_modules`, `migrations/versions/` before the new one) contains `mendel_forge` or `mendel-forge`.
- [x] **Step 2: Run** with `make test` — FAIL on each.
- [x] **Step 3: Delete and edit** per the file list. The migration drops the tables in foreign-key order (`forge_message`, `forge_event`, `forge_revision`, `forge_adaptation`, `forge_catalogue_item`, `forge_source_snapshot`, `source_check`, `queue_visit`); its `downgrade()` raises with *no backward compatibility before v0.1.0*. Diagnostics: delete each `MF`/`MI` code that nothing emits after the deletion — run the diagnostics guard (`uv run pytest tests/guards -k diagnostic` against the test DB setup) and remove what it reports as declared-but-unemitted, keeping any still used; regenerate the reference with `uv run python tools/generate_diagnostics_doc.py`. Settings: delete `DOCKERHUB` and `SOURCE_CHECK` from the Registry section; the GitHub token's help reads *Lets the forge open pull requests and publish releases on the registry*. `uv lock`.
- [x] **Step 4: Run** `make test`, then `make lint`, `make types`, `make guards` — PASS. Record in `tests/fixtures/guard-ledger.md` that `test_forge_write_boundary.py` was deleted with the package it scanned, and that part 5 (#366) brings the new boundary's guard.
- [x] **Step 5: Commit** in two commits: `refactor: the old forge's API, worker jobs and tables go (#361)` and `refactor: the mendel-forge package goes (#361)`, each with the suite green.

### Task 3: Delete the old forge from the browser

**Files:**
- Delete: `frontend/src/forge/`, `frontend/src/api/registry.ts`, `frontend/src/api/useAccept.ts`
- Modify: `frontend/src/app/router.tsx` (the `/forge…` routes and redirects), `frontend/src/app/Shell.tsx` (the *Registry* tab), `frontend/src/app/Shell.test.tsx`, `frontend/src/app/router.test.tsx`, `frontend/src/app/useUrlState.test.tsx`, `frontend/src/home/Home.tsx` and its test (the `Attention` type without `forge`), anything else `tsc` reports
- Regenerate: `make client`

- [x] **Step 1: Update the tests first**: the shell's sections are `["Build", "Runs"]` (part 1 restores *Registry*); the router test asserts `/forge` and `/forge/catalogue` render the not-found page (or the app's existing unknown-route behaviour), and drops the forge subnav and redirect cases; `useUrlState.test.tsx` loses forge-specific cases.
- [x] **Step 2: Run** `npx vitest run` — FAIL on the changed expectations.
- [x] **Step 3: Delete and edit**; `make client`; fix what `npx tsc -b` reports.
- [x] **Step 4: Run** `npx vitest run`, `npx tsc -b`, `npm run lint`, and `npx vitest run src/tokens.test.ts` — PASS.
- [x] **Step 5: Commit** `refactor(frontend): the old forge's screens go (#361)`.

### Task 4: Documentation, and the record

**Files:**
- Delete: `docs/how-to/registry/review-proposals.md`
- Modify: the pages that describe the old forge as current (the list in the spec's inventory: `docs/explanation/{invariants,registry,mendel-ai-ownership,authoring-protocol,architecture,package-boundaries}.md`, `docs/how-to/{index,install}.md`, `docs/how-to/development/{investigate,local-stack,configure-model}.md`, `docs/how-to/pipelines/watch.md`, `docs/reference/{tools.md,pipelines/cli.md,pipelines/glossary.md,registry/*.md,pipelines/pipeline-schema.md}`), `CLAUDE.md` (source map), `CHANGELOG.md` (*Removed* under `mendel-api`, `frontend`, and a `mendel-forge` entry)

- [x] **Step 1:** For each page, remove or replace each statement about the old forge's behaviour (adaptations, the question queue, drift, `land`, `mendel forge …` commands, the `/forge` screens) with a pointer to `docs/superpowers/specs/2026-10-19-forge-mvp-design.md` where the reader needs to know a forge is coming. Keep everything else on the page. Inventory before editing each page; report meaningful removals in the plan's Deviations.
- [x] **Step 2: Run** `make docs`, `make links`, `make doc-paths`, `make doc-sizes` — PASS.
- [x] **Step 3:** Tick this plan with a *Deviations* heading; set the spec's status.
- [x] **Step 4: Commit** `docs: the old forge leaves the documentation (#361)`.
- [x] **Step 5:** `make check` and `make guards` once more, then the final whole-branch review. The branch is **not merged** until part 1 (#362) is on it (spec, section 4).

## Deviations

- **Task 2 landed as one commit, not two.** `test_old_forge_gone.py` asserts that the package is
  gone, so an API-only commit with the package still present could not be green.
- **Task 2's source scan covers `.py`, `.toml`, `.yml` and `Makefile`, as the plan says**, and
  not yet `.ts`/`.tsx`: the generated `schema.d.ts` names a `mendel_forge` type until Task 3
  runs `make client`. Task 3 widens the scan.
- **`test_no_pure_package_imports_an_impure_one` was widened rather than deleted.** It
  searched for the text `mendel_forge`. It now checks each pure package's AST imports against
  every name in `IMPURE_PACKAGES`. The ledger records the break it caught.
- **The fixture `clean_forge` is now `clean_invocations`** (five users), and the unused
  `clean_db` (which truncated `queue_visit`) was deleted. Every `TRUNCATE` list lost the old
  tables, `shape_versions.py` lost their four entries, and their eight shape goldens were
  removed.
- **The migration test also inserts an `agent='forge'` invocation before upgrading** and checks
  that it survives (Review Focus 2). The first draft of the test left that check out.
- **Diagnostics:** 53 codes went (`MF0001`–`MF0406` and `MI0100`–`MI0114` except `MI0106`).
  The band comment marks `MF0001`–`MF0499` as retired, and the new forge allocates from `MF0500`.
  `MI0106` and the nine `MA` codes now name `authoring`, not `forge fill --model`, as where they
  fire.
- **Also touched to keep the suite green:**
  - `migrations/env.py` imported `SourceCheck`.
  - The settings menu golden was regenerated.
  - The `CLAUDE.md` source-map row was updated.
  - The forge test-index row in `tests/README.md` was removed.
  - `.gitignore` and `.dockerignore` lost `.forge/` and `.forge-demo/`.
  - The Makefile lost the `forge`, `forge-ai-eval` and `forge-rework` targets. The
    frontend's `FORGE-REWORK` markers go with Task 3.
- **Task 3 deleted more of the frontend than its file list names.** Regenerating the client
  left these with nothing to call or nothing calling them:
  - `useAnswer`, `useAnswerAll`, `useDecide`, `useDraft`, `usePropose` and their tests;
  - `registry.test.ts`;
  - `app/useKeys.ts` and `ui/Term.tsx`, which only the forge screens imported;
  - `ui/glossary.ts` and `Glossary.test.tsx`: `Term` was the glossary's only consumer, and
    no screen shows its words now.
  `types.ts`'s `Verdict` now takes its short generated name, since the forge's two
  `Verdict`s no longer collide with it. `legacyRoutes` went with the screens it mounted.
- **The refusal hint now reads `mendel explain <code>`**, test first. `forge explain` no longer
  exists, and `mendel explain` covers every code.
- **`/forge` and its old deep links answer as unknown pages** (the router's existing 404), with
  no redirects. Checked in headless Chrome at 1280×800 because the extension was not connected:
  Home loads with *Build* and *Runs*, and `/forge` shows the 404.
- **Task 4 inventory: what left the documentation, and where it went.**
  - **`how-to/registry/review-proposals.md` was deleted, with its screenshot.** Its old URLs
    forward to `explanation/registry.md` (`tools/documentation_locations.json`). Its worked
    example and queue table described the old forge. "After acceptance" (how registry data
    changes future builds) is already covered by `explanation/registry.md`'s *Before and
    after*. Pages that linked to it now link to *Writing a contract* or *Making a choice
    depend on your data*.
  - **`explanation/architecture.md`:**
    - §10 (the forge's modules, phase 2, the five-rung ladder, landing and its write guard)
      became a short *Where declared data comes from*, pointing to the forge MVP spec. The
      `comeni-ai` subsection was kept.
    - §4a lost the `Hole` / `FilledValue` half and the *one may return `None`* contrast,
      which needed a forge filler.
  - **`explanation/invariants.md`:**
    - Door 5 (the forge review chat) and the `ReviewTurn` / `ForgeReviewRequest` paragraph
      are gone. Their principle stays: a person's typed words reaching a model is a door.
    - The protection-profile row for sealing the forge chat is gone.
    - `DoorPath` / `doors_on()`, names the code never had, became `BoundaryFlow` /
      `payloads_for()`.
  - **`explanation/mendel-ai-ownership.md`:** the forge call path, the `mendel-forge`
    ownership row and the forge reclaim are gone. The page now says the AI worker has no
    recovery pass; recovery is still tracked under #310. The first refactoring step (the
    invocation vocabulary) is recorded as done.
  - **`explanation/package-boundaries.md`:** the `mendel-forge` rows and source groups are
    gone, and its open issue 2 (the vocabulary depends on the forge) is resolved. The
    ordinary worker's row now names its real jobs.
  - **`reference/pipelines/cli.md`:** the `forge` CLI section is gone.
  - **`reference/pipelines/glossary.md`:** `drift`, `hole` and `band` are gone (old forge
    queue terms that no screen uses).
  - **`reference/pipelines/diagnostics.md`:** the generator's six forge-only concern titles
    are gone, and `workflow` is titled *Authoring — sessions, turns and proposals*, which is
    what it now holds.
  - **`CHANGELOG.md`:** *Removed* under `mendel-api`, `frontend` and `mendel-forge`. The
    unreleased `mendel-forge` *Added* entry is replaced, since no forge version was ever
    tagged.
  - **Also updated:** the install and local-stack URL tables, `how-to/index.md`, `mkdocs.yml`
    nav, `tools/README.md`, `frontend/README.md` and the test indexes.
- **Final branch review (Task 4 step 5).** `make check` (3277 tests) and `make guards` (93) pass.
  The review found ten comments in live code that cited deleted modules (`forge_state`,
  `forge_jobs`, `test_forge_jobs.py`) as their reason, and rewrote each to stand alone. With
  the forge services gone, `test_nothing_under_src_moves_a_session_by_event` lost its
  `services/forge` exclusion. Commit `af19fbeb` had shipped one line over the lint limit
  (fixed in `19824a2d`): the Python lint was not rerun after the scan was widened.
