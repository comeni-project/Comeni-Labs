# Forge MVP 4: tests as Wiener runs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a forged tool has tests, drafted from nf-core's and approved like any piece, that run as
Wiener runs and turn the adaptation green.

**Architecture:** a sixth piece `tests` in the pure forging model, a `ToolTest` shape the registry
loads, `build_test_pipeline` making an IR directly, a narrow `TestRunner` held only by the forge's
worker job, and a `forge_test_run` table polled by a cron.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy + Alembic, ARQ, httpx, React + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-10-30-forge-4-tests-design.md`

**Execution:** native, inline (the operator's standing choice for the forge). Run the forge's tests
per task and the whole Python suite once before the MVP's pull request; no Docker rebuilds.

## Global Constraints

- Inputs are paths inside `nf-core/test-datasets`, never URLs; the engine builds the URL.
- `data_commit` is stamped by the engine; a model's value is overwritten.
- Green is the run succeeded and every `expect` matched; it counts only for the draft digest it ran.
- Only the forge's test job holds a `TestRunner`. The builder's Run button is unchanged.
- `MENDEL_WIENER_TOKEN` is never logged, shown, or sent to a model, and is in the worker only.
- Pages say a green test shows the tool runs, not that its results are correct.
- No live model, Wiener or network in tests.

## Review Focus

1. Wiener unreachable or refusing (401) at submit or mid-run: the run fails with the reason and the
   adaptation returns to `assembled`, never stuck in `testing`. Test in Task 4.
2. A command lands while tests run: the outcome is recorded, the adaptation does not become
   `tested`. Test in Task 4.
3. A run that succeeds but publishes nothing matching a pattern is not green. Test in Task 4.
4. A hostile input path (`../x`, `https://…`, a space) is refused before storing. Test in Task 1.
5. Two clicks of *Run its tests* start one set of runs. Test in Task 4.

---

### Task 1: The test as data

**Files:**
- Create: `packages/comeni-core/src/comeni_core/declared/tooltest.py`
- Modify: `packages/mendel-forge/src/mendel_forge/forging/{model,rules,values,validate,assemble}.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py`,
  `packages/mendel-compiler/src/mendel_compiler/registry_lint.py`
- Modify: `packages/mendel-forge/src/mendel_forge/nfcore/source.py`,
  `packages/mendel-api/src/mendel_api/services/catalogue.py`, `models.py`, a migration
- Test: `packages/mendel-forge/tests/test_forge_tooltest.py`, the existing forging tests

**Interfaces:**
- Produces: `ToolTest` (`contract, name, data_commit, inputs: dict[str, list[DataPath]], setup:
  list[SetupStep], params: dict[str, str | int | float | bool], expect: list[Expected]`);
  `SetupStep(tool, inputs, feeds: dict[output port, input port])`; `Expected(port, pattern)`;
  `Piece.TESTS`, `tests:test:<name>`; `Stack.tests: dict[contract id, list[ToolTest]]`.

- [x] **Step 1: Write the failing tests**
  `test_a_path_outside_test_datasets_is_refused` (parametrised `../x`, `https://a/b`, `a b`, `/x`),
  `test_tests_come_after_rules_and_one_is_required` (`tests:none` refused MF0506, `next_piece` is
  `tests` until one is approved), `test_a_changed_parameter_reopens_tests`,
  `test_a_test_naming_an_unknown_port_or_param_is_MF0507`, `test_an_unexpected_output_is_MF0507`
  (a produced port neither in `expect` nor reasoned), `test_a_draft_layer_carries_its_tests`,
  `test_a_malformed_test_refuses_to_load`, `test_lint_accepts_a_tests_folder`.
- [x] **Step 2: Run; they fail.**
  Run: `uv run pytest packages/mendel-forge/tests/test_forge_tooltest.py -q`
- [x] **Step 3: Implement.** `DataPath` pattern
  `^[A-Za-z0-9_][A-Za-z0-9._-]*(/[A-Za-z0-9_][A-Za-z0-9._-]*)*$`. `DEPENDS`: contract and parameters
  gain `TESTS`; rules gains it too (a changed rule can change settings). `write_layer` stamps
  `data_commit` from a new `ModuleOrigin.data_commit`. `catalogue_sync.test_data_commit` (nullable)
  is read with `git ls-remote <test-datasets> refs/heads/modules` during sync; a failed read keeps
  the last one and never fails the sync. Update the forging test helpers to approve one test.
- [x] **Step 4: Run** `uv run pytest packages/mendel-forge packages/mendel-api/tests/forge -q`; pass.
- [x] **Step 5: Commit.**

### Task 2: The test pipeline

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/testing.py`
- Modify: `packages/mendel-api/src/mendel_api/services/bundle.py` (extract the zip writer)
- Test: `packages/mendel-forge/tests/test_forge_testing.py`

**Interfaces:**
- Consumes: `ToolTest`; `layers.load`; `Pipeline.of`; `emit`, `emit_config`.
- Produces: `build_test_pipeline(test: ToolTest, stack: Layers, paths) -> Pipeline`;
  `params_for(test, pipeline) -> dict[str, str | list[str]]`; `TESTDATA_BASE`;
  `bundle.archive(pipeline, modules: Path) -> bytes`.

- [x] **Step 1: Write the failing tests** `test_a_test_pipeline_runs_only_this_tool` (one step, the
  contract's), `test_setup_steps_feed_the_tool` (edge from the setup's output to the port),
  `test_the_url_is_pinned_to_the_commit`, `test_params_fill_exactly_the_pipelines_holes`,
  `test_a_setting_comes_from_the_test` (a test's param reaches the step, others take defaults),
  `test_the_bundle_is_deterministic`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement** the IR by hand: one `IRNode` per setup and the tool, `selection` and
  `presence` at `Tier.STRUCTURAL` with reason `a forge test of this tool`, `IREdge`s, `Goal(have=
  entry types, want=produced types)`. No `resolve`.
- [x] **Step 4: Run; pass.** A real emit of `nf-core/fastqc` from `registry/` is part of the tests.
- [x] **Step 5: Commit.**

### Task 3: The runner

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/runner.py`,
  `packages/mendel-api/src/mendel_api/services/wiener_runner.py`
- Modify: `packages/mendel-api/src/mendel_api/settings.py`, `packages/mendel-api/pyproject.toml`
  (httpx), `uv.lock`, `docker-compose.yml`, `docker-compose.prod.yml`
- Test: `packages/mendel-api/tests/forge/test_wiener_runner.py`, `tests/guards/`

**Interfaces:**
- Produces: `TestRunner` Protocol (spec §2), `RunnerUnavailable(Exception)`,
  `WienerRunner(url, token, client=None)`, `runner() -> TestRunner | None`.

- [x] **Step 1: Write the failing tests** with `httpx.MockTransport`:
  `test_submit_uploads_then_runs_with_the_bearer_token`, `test_a_refusal_raises_with_its_reason`,
  `test_results_reads_every_page`, `test_no_url_means_no_runner`,
  `test_the_token_never_appears_in_an_error`, and the guard
  `test_only_the_forge_test_job_imports_the_runner`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.** `POST /api/artifacts`, `POST /api/runs`, `GET /api/runs/{id}`,
  `GET /api/runs/{id}/results`. Paths returned as `process/name`. Compose: `MENDEL_WIENER_URL:
  http://wiener-api:8001` and the token on `mendel-worker` only.
- [x] **Step 4: Run; pass.** Run `uv lock --check`.
- [x] **Step 5: Commit.**

### Task 4: Running them

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/forge_tests.py`, a migration
- Modify: `forging/protocol.py`, `services/forging.py`, `routes/forge.py`, `worker.py`, `models.py`,
  `shapes` registrations, `diagnostics.yml`
- Test: `packages/mendel-api/tests/forge/test_forge_tests.py`

**Interfaces:**
- Produces: `Phase.TESTING`, `Phase.TESTED`; `ForgeTestRun(id, adaptation, item, digest, run_id,
  state, outcome, problems, started_at, finished_at)`; `forge_tests.start(id) -> bool`,
  `forge_tests.poll() -> int`, `green(test, files) -> list[Problem]`; `POST
  /forge/adaptations/{id}/tests`; `AdaptationView.tests: list[TestRunView]`, `tests_available`,
  `tests_unavailable_because`; `MF0514` no Wiener, `MF0515` a test failed.

- [x] **Step 1: Write the failing tests** with a fake runner:
  `test_running_submits_each_test_and_enters_testing`,
  `test_every_expectation_met_is_green_and_tested`,
  `test_a_run_that_publishes_nothing_matching_is_not_green` (focus 3),
  `test_a_failed_run_returns_to_assembled_with_its_reason`,
  `test_wiener_refusing_at_submit_does_not_strand_testing` (focus 1),
  `test_wiener_unreachable_while_polling_retries_then_fails_after_an_hour` (focus 1),
  `test_a_command_during_testing_never_becomes_tested` (focus 2),
  `test_two_starts_make_one_set_of_runs` (focus 5), `test_green_counts_only_for_its_digest`,
  `test_no_runner_is_MF0514`, `test_tested_vocabulary_stays_pending`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.** Digest: sorted (path, sha256) over the draft folder. Start locks the
  row, requires `ASSEMBLED`, sets `TESTING`, then queues one job (`forge-tests:{id}`, `keep_result=0`)
  that submits. Poll cron every 30 seconds, finishing against the locked row as assembly's `_finish`
  does. `green` uses `fnmatch` over published names. `_after_change` and `_assembled_vocabulary`
  treat `TESTING`/`TESTED` like `ASSEMBLED`.
- [x] **Step 4: Run; pass.** Regenerate the forging diagram and diagnostics doc.
- [x] **Step 5: Commit.**

### Task 5: The AI drafts tests

**Files:**
- Create: `packages/mendel-api/src/mendel_api/forge/prompts/forge.tests.v1.md`
- Modify: `services/forging_ai.py`, `forge/replies.py`
- Test: `packages/mendel-api/tests/forge/test_forging_ai.py`

- [x] **Step 1: Write the failing tests** `test_drafting_tests_reads_the_modules_nf_test`,
  `test_a_drafted_data_commit_is_refused`, `test_drafting_tests_stores_proposals`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.** The piece's prompt adds `tests/main.nf.test`, the module's output
  patterns and the rules: `params.modules_testdata_base_path + 'x'` becomes the path `x`. The file
  is public module source, within the `forge_drafting` door. Absent file: an empty list and a
  sentence, and the AI drafts from `meta.yml`.
- [x] **Step 4: Run; pass,** with `tests/guards/test_egress.py`.
- [x] **Step 5: Commit.**

### Task 6: The pages

**Files:**
- Create: `frontend/src/registry/forging/Tests.tsx`
- Modify: `Adaptation.tsx`, `PieceItems.tsx` (summary), `useForgeActions.ts`, `useAdaptation.ts`,
  `ForgingList.tsx`, `../Tool.tsx`, generated client via `make client`
- Test: `frontend/src/registry/forging/Adaptation.test.tsx`

- [x] **Step 1: Write the failing tests** `tests is a real piece`, `run its tests starts them`,
  `a running test polls and shows its state`, `a failure says what was missing and links the run`,
  `green says what it proves`, `without Wiener it says why`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.** Poll every 5 seconds while `testing`. The board could not be read
  (spec header), so this follows the Forging pages' panels.
- [x] **Step 4: Run** `npx vitest run` and `npx tsc -b`; pass. A browser check waits for the stack.
- [x] **Step 5: Commit.**

### Task 7: Docs and the whole suite

- [x] **Step 1:** Add `docs/how-to/registry/` coverage, a dated exception in the place the boundary
  now lives, `CHANGELOG.md`, `docs/notes/now.md`, a journal entry.
- [x] **Step 2:** Run the whole Python suite, `make guards`, `make doc-sizes`.
- [x] **Step 3:** Commit, and record deviations below.

## Not in this plan

- Tests for the ten existing tools, and the first real Wiener run (spec §7): **MVP 4 stays open.**
- `ENGINE_REF` in `comeni-registry`: lands with MVP 5.

## Deviations

- A test's item value is a `TestDraft` with no `data_commit` field, so a model's commit is refused
  by the shape, not overwritten. `ToolTest` adds the contract, name and commit at assembly.
- `tests:none` is refused: a tool needs a test, and the piece needs one that stands. Tests gained an
  `unchecked` map, so an output no pattern can pin carries a stated reason.
- `MENDEL_WIENER_URL` is in the shared Mendel environment: the API reads it to say whether tests
  can run. The token stays on the worker alone, with a guard.
- `says` and the other run columns are plain, not JSON, so `forge_test_run` needs no shape
  registration. An `attempt` column keeps earlier sets, and only the latest counts.
- Task 4's tests were written with its code, so none was seen failing first. Each key behaviour was
  then broken by hand (the phase check in `conclude`, the pattern check, the digest in `proven`)
  and a test failed each time; the guard failed against a stray importer.
- `declares: test` is a new `DeclaredKind`, with `MD0026` for a test of an undeclared contract.
- `registry.yml` does not place `test` yet: it lands in comeni-registry with MVP 5, so
  `test_the_manifest_places_every_kind_that_exists` carries an allowance for that one kind.
- The tool page's disabled *Add tests* went: a tool gets tests by re-forging it.
