# PI requests: forget mode, testable bundle, decisions report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Compose stack that can forget between runs, a pipeline zip that runs its own test,
and a readable report of every decision and its reason.

**Architecture:** A Compose overlay selected by `COMENI_MEMORY` in the Makefile; two new entries
derived from `pipeline.yml` in the existing deterministic bundle; a pure HTML renderer beside
the emitter, served from the bundle and its own endpoint, linked from the Build page.

**Tech Stack:** Docker Compose, GNU Make, Python 3.12 (FastAPI, Pydantic, Jinja2 already used
by the emitter), React/TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-24-pi-requests-design.md` · issue #619 (under #600).

## Global Constraints

- `COMENI_MEMORY` takes `kept` (default) or `forget`; any other value stops `make` with a message naming both.
- Forget mode never references or removes the named volumes `comeni-pg`, `wiener-clickhouse`, `ollama-models`.
- Kept in both modes: `.run/registry`, `.run/registries`, `.run/chatgpt`, model weights, data roots (read-only).
- The bundle stays deterministic: fixed timestamps, sorted entries, two calls byte-identical.
- No network I/O in `mendel-compiler` (pure package); the report reads only a `Pipeline`, no clock.
- Tier and source words come from `comeni_core.plan.tiers.TIER_VOCABULARY` / `ValueSource`, not new labels.
- Report footer copy, verbatim: "Curated tools are reference material for a laboratory to validate. This pipeline is not a validated clinical test."
- No browser walk this round; UI behaviour goes to the walk list at the end.

## Review Focus

- Switching `kept` → `forget` → `kept`: kept drafts and database still there (overlay never touches named volumes) — Task 1 test.
- `forget` combined with `make prod`: the prod overlay's `!override` volume lists must not win over forget's — Task 1 test on the three-file merge.
- A pipeline with no `test` profile (an input lacks `test_data`): bundle has no samplesheet and the README says which inputs — Task 2 test.
- A reason or goal containing `<script>` or `&`: escaped in the report — Task 3 test.
- A pipeline with no tier-4 choices: the *Flagged for review* section says none, not omitted silently — Task 3 test.

---

### Task 1: Forget mode

**Files:**
- Create: `docker-compose.forget.yml`
- Modify: `Makefile` (configuration section; `dev`, `dev-down`, `prod`, `prod-down`)
- Modify: `tests/support/compose.py` (`configuration(..., forget=False)`)
- Modify: `.env.example` (section 1), `docs/how-to/development/local-stack.md`, `CHANGELOG.md` (Deployment)
- Test: `tests/repo/test_compose.py`

**Interfaces:**
- Produces: `configuration(tmp_path, production=False, token="", extra_env=None, forget=False)` adds `-f docker-compose.forget.yml` last.

- [ ] **Step 1: Write the failing tests** in `tests/repo/test_compose.py`:
  - `test_forget_keeps_no_state_in_a_named_volume`: effective forget config (dev and prod): `postgres`, `clickhouse` have no volume whose `source` is `comeni-pg` / `wiener-clickhouse`, and their data dirs (`/var/lib/postgresql/data`, `/var/lib/clickhouse`) are `tmpfs`.
  - `test_forget_moves_app_state_under_run_forget`: for every service mounting a target in `{/app/drafts, /app/forge, /app/workspace}` or a `…/.run/wiener` path, the source is under `ROOT/.run/forget/`; every `WIENER_*_ROOT` env value is under `.run/forget/wiener`, and the wiener mount's source equals its target.
  - `test_forget_keeps_the_installation`: `/app/registry`, `/app/registries`, `/app/chatgpt` sources unchanged from the kept config; `ollama` still mounts `ollama-models`.
  - `test_forget_names_only_services_the_base_has` (same shape as the prod one).
  Assert each collection nonempty before looping.
- [ ] **Step 2: Run** `make test ARGS="tests/repo/test_compose.py -k forget"` (or the Make target's equivalent pytest selection). Expected: FAIL (no overlay file).
- [ ] **Step 3: Write `docker-compose.forget.yml`.** `tmpfs:` for the two data dirs plus `volumes: !override` on `postgres`/`clickhouse` keeping only the `./ops/…:ro` init mounts; `volumes: !override` on `api`, `mendel-worker`, `ai-worker`, `wiener-*` repeating the base lists with the drafts/forge/workspace/wiener sources replaced by `./.run/forget/…` and `${PWD}/.run/forget/wiener:${PWD}/.run/forget/wiener`; the `WIENER_*_ROOT` env values repointed. Header comment: what it forgets, what it keeps, why the run dir is a host path. A prod-merge case may need the overlay to restate prod's lists (no `./packages` mount in prod): if so, add `docker-compose.forget.prod.yml` rather than a mount prod forbids, and extend the test to it.
- [ ] **Step 4: Makefile.** `MEMORY := $(shell tools/command_env.py --setting COMENI_MEMORY kept)`; a `memory-valid` prerequisite of `dev` and `prod` that refuses other values; `FORGET_FILES := $(if $(filter forget,$(MEMORY)),-f docker-compose.forget.yml)`; `DC := docker compose -f docker-compose.yml $(FORGET_FILES)` and prod's command gains it after the prod file. `dev`/`prod` run `rm -rf .run/forget && mkdir -p .run/forget/{drafts,forge,workspace,wiener}` before `up` when forgetting; `dev-down`/`prod-down` remove `.run/forget` after `down`. `make help` text says so.
- [ ] **Step 5: Run the tests** (same command). Expected: PASS. Also `docker compose -f docker-compose.yml -f docker-compose.forget.yml config -q` exits 0.
- [ ] **Step 6: Document.** `.env.example`: `# COMENI_MEMORY=kept` with two lines on `forget`. `local-stack.md`: a short "Keeping or forgetting" section. `CHANGELOG.md` Deployment entry.
- [ ] **Step 7: Commit** `feat(deploy): COMENI_MEMORY=forget runs the stack without keeping anything (#619)`.

### Task 2: The bundle runs its own test

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/bundle.py` (`archive`)
- Create: `packages/mendel-compiler/src/mendel_compiler/readme.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (expose `test_profile_missing(pipeline) -> list[str]`, the list `_test_profile` already computes)
- Test: `packages/mendel-api/tests/pipelines/test_bundle.py`, `packages/mendel-compiler/tests/test_readme.py`

**Interfaces:**
- Consumes: `emit.test_samplesheet(pipeline) -> str`, `emit.TEST_SAMPLESHEET`, `emit.entry_params`, `Pipeline.input_form`.
- Produces: `emit.test_profile_missing(pipeline: Pipeline) -> list[str]` (sorted params lacking `test_data`; empty = a `test` profile exists); `readme.render(pipeline: Pipeline) -> str`.

- [ ] **Step 1: Failing tests.**
  - `test_readme.py::test_a_runnable_pipeline_says_how_to_run_its_test`: contains `nextflow run . -profile test,docker` and the pipeline's goal.
  - `test_readme.py::test_without_example_data_it_names_what_is_missing`: a pipeline whose channel lacks `test_data` → no `-profile test` line; each missing param named.
  - `test_bundle.py::test_the_bundle_carries_its_test_samplesheet`: for the kept SPINE pipeline (assert first that it is a samplesheet pipeline with an empty `test_profile_missing`, else build a fixture that is), the archive has `README.md` and `test-samplesheet.csv` equal to `test_samplesheet(pipeline)`.
  - `test_bundle.py::test_no_samplesheet_entry_without_a_test_profile`.
  - Existing `test_bundle.py` determinism test stays and must still pass.
- [ ] **Step 2: Run** `make test ARGS="packages/mendel-api/tests/pipelines/test_bundle.py packages/mendel-compiler/tests/test_readme.py"`. Expected: FAIL.
- [ ] **Step 3: Implement.** `test_profile_missing` refactored out of `_test_profile` (which then calls it). `readme.render`: title, goal, steps in pipeline order, then either the run command (`-profile test,docker`, and `-profile docker --input <your samplesheet>` for real data) or the missing-inputs paragraph; plain Markdown, no clock. `archive()` writes `README.md` always and `TEST_SAMPLESHEET` only when `input_form is SAMPLESHEET` and `test_profile_missing` is empty. Update the module docstring's "four entries" paragraph.
- [ ] **Step 4: Run** the same tests, plus `packages/mendel-compiler/tests/test_emit.py`. Expected: PASS.
- [ ] **Step 5: Check Wiener.** `grep -rn "test-samplesheet\|README" packages/wiener-api/src` finds no writer of those names in an artifact dir; record the result in this step.
- [ ] **Step 6: CHANGELOG** (mendel-api, mendel-compiler). **Commit** `feat(bundle): the zip carries its test samplesheet and a README (#619)`.

### Task 3: The decisions report

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/report.py`, `packages/mendel-compiler/src/mendel_compiler/templates/decisions.html.j2` (beside `main.nf.j2`; reuse that Jinja environment with autoescape on for this template)
- Modify: `packages/mendel-api/src/mendel_api/services/bundle.py` (adds `decisions.html`), `packages/mendel-api/src/mendel_api/routes/build.py` (new route beside `/bundle`)
- Test: `packages/mendel-compiler/tests/test_report.py`, `packages/mendel-api/tests/pipelines/test_bundle.py`

**Interfaces:**
- Produces: `report.render(pipeline: Pipeline) -> str` (a complete HTML document, inline CSS with `@media print` and `prefers-color-scheme`); `GET /api/pipeline/drafts/{draft_id}/decisions` → `text/html`, 404 like `/bundle` when nothing is kept, `Content-Disposition: inline; filename="decisions-<id8>.html"`.

- [ ] **Step 1: Failing tests** in `test_report.py`, on a fixture pipeline with at least one tier-4 model choice that overrode a rule, one measured setting, one convention:
  - `test_every_choice_appears_with_its_reason`: each step id, each setting's value and `why.reason` occurs in the output (collections asserted nonempty).
  - `test_flagged_for_review_comes_first_and_holds_every_tier_4`: the "Flagged for review" heading precedes the first step section; every tier-4 reason appears in it, with the overridden rule.
  - `test_nothing_flagged_says_so`: no tier-4 → the section reads "Nothing is flagged for review."
  - `test_who_decided_uses_the_served_words`: each tier's `TIER_VOCABULARY[t].name` appears for the tiers present.
  - `test_text_is_escaped`: a reason `"<script>x</script> & y"` appears as `&lt;script&gt;` and `&amp;`.
  - `test_the_same_pipeline_renders_the_same_bytes`.
  - `test_the_footer_states_what_the_tools_are`: the verbatim footer copy.
  - In `test_bundle.py`: `decisions.html` in the archive equals `report.render(pipeline)`; the route returns 200 `text/html` for a kept draft and 404 otherwise.
- [ ] **Step 2: Run** `make test ARGS="packages/mendel-compiler/tests/test_report.py packages/mendel-api/tests/pipelines/test_bundle.py"`. Expected: FAIL.
- [ ] **Step 3: Implement `report.render`.** Sections in spec order: pipeline (goal, steps, layers with digests), *Flagged for review*, then one section per step (tool, each setting: value · who decided (tier word + source) · reason · premise facts · layer / displaced layer · overrode), decision records, footer. Who-decided text: tier word from `TIER_VOCABULARY`, source from `ValueSource` (`model` → "the AI", `human`/`said` → "the person", `measured` → "measured", `resolver` → "a rule"); add a mapping in `report.py` only for sources not already worded elsewhere (grep the frontend `useTiers` source words first and match them).
- [ ] **Step 4: Bundle and route.** `archive()` writes `decisions.html`; the route mirrors `/bundle`'s error handling.
- [ ] **Step 5: Run** the tests; `make client` to regenerate the API client for the new route. Expected: PASS, client diff limited to the route.
- [ ] **Step 6: Build page link.** In `frontend/src/build/living/PipelineFile.tsx`, beside *Download*: when `kept`, a *Download zip* control (fetches `/pipeline/drafts/{id}/bundle`, saves `pipeline-<id8>.zip`) and a *Decisions report* link (opens `/api/pipeline/drafts/{id}/decisions` in a new tab). A vitest in the file's existing test: both present when kept, absent when not. Run `cd frontend && npx vitest run src/build/living && npx tsc -b`.
- [ ] **Step 7: CHANGELOG**, `docs/explanation/builder-agent.md` or the Build how-to page gets one line pointing at the report (find the page that documents *Download*). **Commit** `feat(report): a decisions report from pipeline.yml, in the bundle and on Build (#619)`.

### Task 4: End of part

- [ ] `make check`, then `make guards`; `make verify` if Docker/Nextflow are free (the PC is busy: if skipped, say so in the PR). Record counts.
- [ ] Tick #619's three boxes as each lands; journal entry `docs/notes/journal/2026-11-24-pi-requests.md`.

## Saved for the walk

- `forget`: start, build, stop, start → empty. `kept`: survives. Switch back and forth: kept data intact.
- Download zip from Build, unzip, `nextflow run . -profile test,docker` green.
- *Decisions report* from Build: reads well light and dark, prints to PDF on A4.
