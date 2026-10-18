# Part I.0 Plan B: the save file — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pipeline.yml` version 7 says what was wanted (`intent`) and what is known (`facts`) at the top, names where to fetch each registry layer, upgrades every v6 file unchanged in meaning, and is also the one file a person starts a build from.

**Architecture:** `Pipeline` stores `intent` and `facts` in place of `goal`, and `goal` becomes a computed property, so every reader is unchanged. A `before` validator regroups a v6 `goal:` (the upgrader). Each locked layer gains a locator (`source`, `commit`, `dirty`) that `mendel-compiler` reads with git and hands to `Pipeline.of`; `comeni-core` stays pure. A starter is a v7 file with only `intent` and `facts`.

**Tech Stack:** Python 3.12/3.13, Pydantic v2, PyYAML via `comeni_core.yaml_strict`, git through `subprocess` in `mendel-compiler` only, pytest.

**Spec:** [`docs/superpowers/specs/2026-10-13-part-i0-intent-facts-steps-design.md`](../specs/2026-10-13-part-i0-intent-facts-steps-design.md) §8 (except §8.4), §9's save-file rows, §10's *starter file*, *save file*, *purity* and *egress* items. Grounded in `main` at `a8425c4d`, after the operator's `comeni-core` artifact audit (`11689084`).

## Deviations from the spec, decided here

- **§8.4 (open a saved file) is deferred** to [#357](https://github.com/comeni-project/Comeni-Labs/issues/357), operator, 2026-10-18: nothing opens a saved file today, so there is nothing to extend.
- **`"goal"` is still read as `said`.** Session blueprints, draft provenance and saved files hold `source: goal`; a rename that refused it would break replay. Writing always says `said` **(plan)**.
- **Locators only where a file is written or shown:** `orchestrate.build` (CLI build/upgrade) and `drafts._materialised` (keep and preview). The canvas frame and `build.of`'s view never write a file and are read on every poll; they pass none **(plan)**.
- **`source` is a network URL or nothing.** A remote with credentials (`https://user:token@…`) is stripped of them; a local-path remote (`/home/…`, `file://`) records no `source`, because `lockfile.py` keeps local paths out of the file by design **(plan)**.

## Global Constraints

- `comeni-core` and `mendel-authoring` stay in both purity guards; `subprocess`/git only in `mendel-compiler` (`tests/guards/`).
- `FREE_TEXT_FIELDS` and `SAMPLE_FIELDS` do not change. Every new string field is a declared mark in `comeni_core/spell/marks.py` (`tests/guards/test_egress.py::test_no_payload_carries_an_undeclared_string`).
- Nothing the person typed enters the file: no quote, no `not_offered`.
- **Same goal → byte-identical `.nf`** (`tests/golden/spine/main.nf`) before and after every task.
- A v6 file loads, upgrades in memory, and re-emits a byte-identical `.nf`; one with `emitted.from_digest` reads as *predates the schema*, never as hand-edited.
- Containers by digest and the Nextflow version are out of scope (#308).
- Diagnostics are declared in `diagnostics.yml` and raised through `coded()`; the new ones are **MD0231** and **MD0232**.
- Commits end with the session's `Co-Authored-By` line; tests run against the test database only (`make test-db`, `make test`).

## Review Focus

1. **A layer whose remote URL carries a token** — the file must never hold it. *(Task 3: `test_a_remote_with_credentials_records_no_userinfo`.)*
2. **A v6 file that was emitted and stamped** — after upgrade it must not be called hand-edited (`MD0214`) or stale (`MD0213`). *(Task 2: `test_a_stamped_v6_file_predates_the_schema_not_hand_edited`.)*
3. **A starter that also has `steps:`, or a file with both `goal:` and `intent:`** — refused with a sentence, not silently half-read. *(Task 2: `test_goal_beside_intent_is_refused`; Task 5: `test_a_starter_with_steps_is_not_a_starter`.)*
4. **Old JSON rows carrying `source: goal`** (session blueprints) — still load after the rename. *(Task 1: `test_goal_is_read_as_said`.)*
5. **A layer outside git, or with uncommitted edits** — the build still succeeds and says once why the file cannot rebuild alone. *(Task 3: `test_build_warns_for_an_unversioned_and_a_dirty_layer`.)*

---

### Task 1: `said` replaces `goal` as who settled a value

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/review/answer.py` (`ValueSource`), and every `ValueSource.GOAL` use: `comeni_core/goal/profile.py`, `comeni_core/declared/measurement.py`, `comeni_core/artifact/{pipeline,materialise}.py`, `mendel_resolver/{premises,resolve}.py`, `mendel_authoring/decisions.py`, `mendel_api/stages/gathering.py`, `mendel_api/stages/building/amending.py`, and the tests `grep -rl ValueSource.GOAL` lists.
- Test: `packages/comeni-core/tests/test_review_base.py`

**Interfaces:**
- Produces: `ValueSource.SAID = "said"`; `ValueSource("goal") is ValueSource.SAID`. `PremiseOrigin.GOAL` is a different enum and is not touched.

- [x] **Step 1: Write the failing tests**

```python
def test_goal_is_read_as_said():
    assert ValueSource("goal") is ValueSource.SAID
    assert Measured(measurement="paired", value=True, source="goal").source is ValueSource.SAID

def test_said_is_what_is_written():
    assert Measured(measurement="paired", value=True).model_dump(mode="json")["source"] == "said"
```

- [x] **Step 2: Run them; expect `AttributeError: SAID`.** `uv run pytest packages/comeni-core/tests/test_review_base.py -q` (pure package: no database).
- [x] **Step 3: Rename `GOAL` to `SAID = "said"`** and add `_missing_` mapping `"goal"` to `SAID`, with a one-line comment citing this plan; replace every `ValueSource.GOAL`. Update docstrings that say *goal* for this source.
- [x] **Step 4: Run `make test`; expect PASS.** The golden `.nf` does not change (sources are not emitted).
- [x] **Step 5: Commit** `refactor(core): who settled a value the person stated is "said", and "goal" still reads (Plan B)`.

### Task 2: version 7 — `intent` and `facts` at the top, and the v6 upgrader

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py` (add `Intent`, `Facts`; `Goal.intent`, `Goal.facts`, `Goal.of`), `comeni_core/artifact/pipeline.py` (fields, `goal` property, `_v6_to_v7`, `SCHEMA_VERSION = 7`), `comeni_core/artifact/materialise.py` (construct with intent/facts), `packages/mendel-compiler/src/mendel_compiler/pipeline_file.py` (`HEADER`: `intent:` and `facts:` are inert to `emit`), `tests/support/pipeline.py` (`SERIALISED_SHAPE`), `docs/reference/pipelines/pipeline-schema.md`.
- Create: `tests/fixtures/pipeline-v7/pipeline.yml` (golden, from the spine example), `tests/artifact/test_pipeline_v7.py`.

**Interfaces:**
- Consumes: `ValueSource.SAID` (Task 1).
- Produces: `Intent(want: list[TypeId], constraints: Constraints)`, `Facts(inputs: list[GoalInput], measurements: list[Measured])`, both `extra="forbid"`; `Goal.of(intent: Intent, facts: Facts) -> Goal`; `Goal.intent -> Intent`, `Goal.facts -> Facts`. `Pipeline.intent`, `Pipeline.facts` (declared right after `version`, so they dump first); `Pipeline.goal -> Goal` (property, not serialised). `Pipeline(goal=...)` keeps working through the upgrader.

- [x] **Step 1: Write the failing tests** in `tests/artifact/test_pipeline_v7.py`:
  - `test_a_v7_file_puts_intent_and_facts_first`: `list(yaml.safe_load(pipeline_file.dump(p)))[:3] == ["version", "intent", "facts"]` for the spine build.
  - `test_the_golden_v7_file_is_what_the_spine_builds`: building `examples/rnaseq-goal.yml` dumps exactly `tests/fixtures/pipeline-v7/pipeline.yml`.
  - `test_a_v6_file_upgrades_with_the_same_goal_and_nf`: `tests/fixtures/pipeline/rnaseq-spine.yml` loads; `version == 7`; `p.goal` equals the v6 `goal:` with every `source: goal` read as `said`; emitting it equals `tests/golden/spine/main.nf`.
  - `test_a_stamped_v6_file_predates_the_schema_not_hand_edited`: a spine build stamped, its `version` set to 6 and `intent`/`facts` folded back into `goal:` by hand in the YAML; `pipeline_file.predates_schema(load(...))` is `True` and `hand_edited(...) == []`.
  - `test_goal_beside_intent_is_refused`: a mapping with `goal:` and `intent:` raises `ValidationError` whose message names both keys.
- [x] **Step 2: Run them; expect failures** (`AttributeError: intent`, version 6). `uv run pytest tests/artifact/test_pipeline_v7.py -q`.
- [x] **Step 3: Implement.** `_v6_to_v7` runs last in `_migrate`, when `"goal" in data`: refuse if `intent` or `facts` is also present; else `intent = {want, constraints}`, `facts = {inputs: have, measurements: profile.measurements}`, and `version = SCHEMA_VERSION`. Layer locators stay absent. `materialise.of` passes `intent=goal.intent, facts=goal.facts`. `SERIALISED_SHAPE["Pipeline"]` lists `intent`, `facts` in place of `goal`. Generate the golden v7 fixture once from `mendel build`, read it, and commit it.
- [x] **Step 4: Run `make test`; expect PASS,** including `test_a_schema_change_bumps_the_version` and the spine golden `.nf`. Update `pipeline-schema.md` (v7 layout, `said`, the upgrade from 6).
- [x] **Step 5: Commit** `feat(core): pipeline.yml v7 puts intent and facts at the top; v6 upgrades in memory (Plan B)`.

### Task 3: each layer says where to fetch it

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/spell/marks.py` (`RepoUrl`, `CommitSha`, their `Mark` members), `comeni_core/artifact/lockfile.py` (`Locator`; `LockedLayer.source/commit/dirty`; `Lockfile.of(..., locators=None)`), `comeni_core/artifact/{pipeline,materialise}.py` (`Pipeline.of(..., locators=None)` threads through), `packages/mendel-compiler/src/mendel_compiler/orchestrate.py`, `packages/mendel-api/src/mendel_api/services/drafts.py` (`_materialised`), `comeni_core/diagnostics.yml` (MD0231, MD0232), `mendel_compiler/cli/resolve_verbs.py` (print them on `build` and `upgrade`), `tests/support/pipeline.py` (`SERIALISED_SHAPE` gains `LockedLayer` if listed; the version stays 7).
- Create: `packages/mendel-compiler/src/mendel_compiler/locate.py`, `packages/mendel-compiler/tests/test_locate.py`.

**Interfaces:**
- Consumes: `Pipeline.of` (Task 2's shape).
- Produces: `Locator(source: RepoUrl | None, commit: CommitSha | None, dirty: bool | None)` in `lockfile.py`; `LockedLayer` gains the same three fields, all `None` by default and dropped from the dump when `None`; `Pipeline.of(ir, registry, vocab, measurements=None, layers=(), *, goal, ai=None, locators: Mapping[LayerName, Locator] | None = None)`. In `mendel_compiler.locate`: `locate(layer: Path) -> Locator`, `locators(layers: Sequence[Path]) -> dict[LayerName, Locator]`.
- `RepoUrl`: `https://host/path`, `ssh://host/path` or `user@host:path`; no userinfo on `http(s)`; no local path or `file://`. `CommitSha`: 40 lowercase hex.

- [x] **Step 1: Write the failing tests** (`test_locate.py`, each in a `tmp_path` git repo made with `git init`, one commit, `git remote add origin …`):
  - `test_a_clean_layer_names_its_remote_and_commit`: `locate(layer) == Locator(source="https://github.com/comeni-project/comeni-registry", commit=<rev-parse HEAD>, dirty=False)`.
  - `test_an_edited_layer_is_dirty`: an untracked file under the layer → `dirty is True`; an edit **outside** the layer's folder → `dirty is False`.
  - `test_a_layer_outside_git_records_nothing`: `locate(tmp_path) == Locator(source=None, commit=None, dirty=None)`.
  - `test_a_remote_with_credentials_records_no_userinfo`: origin `https://bot:s3cret@github.com/x/y` → `source == "https://github.com/x/y"`, and `"s3cret" not in pipeline_file.dump(...)` for a build against that layer.
  - `test_a_local_remote_records_no_source`: origin `/home/someone/registry` → `source is None`, `commit` set.
  - In `packages/comeni-core/tests/`: `test_repo_url_refuses_userinfo_and_paths` (`RepoUrl` rejects `https://a:b@h/p`, `/abs/path`, `file:///x`).
  - In `tests/artifact/`: `test_build_warns_for_an_unversioned_and_a_dirty_layer` (CLI `build` against an un-versioned copy of `registry/` prints `MD0231`; against a dirty clone prints `MD0232`; both exit 0).
- [x] **Step 2: Run them; expect `ModuleNotFoundError: mendel_compiler.locate`.**
- [x] **Step 3: Implement.** `locate` runs `git -C <layer>`: `rev-parse --show-toplevel` (fails → not in git), `remote get-url origin` (absent → `source=None`), `rev-parse HEAD`, `status --porcelain -- .`; strip userinfo before validating; a local path → `None`. `orchestrate.build` and `drafts._materialised` pass `locators(paths)`. MD0231 (*a layer is not in git; this pipeline cannot be rebuilt from its file alone*) and MD0232 (*a layer has uncommitted edits*): `emitted_by: compiler`, `refuses: false`, `fires_on: [build, upgrade]`.
- [x] **Step 4: Run `make test` and `make guards`; expect PASS,** including the purity guards (git only in `mendel-compiler`) and `test_no_payload_carries_an_undeclared_string`.
- [x] **Step 5: Commit** `feat: each registry layer in pipeline.yml names its source and commit (Plan B)`.

### Task 4: `mendel upgrade` says which commit to check out

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/lockfile.py` (`drift_against`)
- Test: `tests/artifact/test_lockfile.py`

**Interfaces:**
- Consumes: `LockedLayer.source`, `LockedLayer.commit` (Task 3).

- [x] **Step 1: Write the failing test** `test_a_changed_layer_names_the_commit_it_was_locked_at`: a lock whose layer has `source` and `commit`, compared with a changed layer → the line reads `layer comeni-registry has changed since it was locked; it was locked at <commit> of <source>`. A layer with no locator keeps today's sentence exactly (`test_a_changed_layer_without_a_locator_reads_as_before`).
- [x] **Step 2: Run; expect FAIL** on the missing clause.
- [x] **Step 3: Implement** the clause in `drift_against`, only when both are known.
- [x] **Step 4: Run `make test`; expect PASS.**
- [x] **Step 5: Commit** `feat(upgrade): a changed layer names the commit it was locked at (Plan B)`.

### Task 5: one file to start from

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` or a new `comeni_core/artifact/starter.py` (`Starter`), `packages/mendel-compiler/src/mendel_compiler/pipeline_file.py` (`goal_from`), `mendel_compiler/cli/resolve_verbs.py` and `cli/parse.py` (`mendel build <file>`; `--goal` reads either format), `packages/mendel-api/src/mendel_api/settings.py` (`example_goal`), `mendel_api/services/build.py` (`example()` through `goal_from`), `Makefile`, `tests/support/pipeline.py` (`GOAL`), `docs/reference/pipelines/goal-schema.md`, `docs/reference/pipelines/cli.md`, `docs/how-to/registry/add-tool.md`, `docs/how-to/registry/add-layer.md`.
- Create: `examples/rnaseq.yml` (the starter); delete `examples/rnaseq-goal.yml`. Test: `tests/artifact/test_starter.py`.

**Interfaces:**
- Consumes: `Intent`, `Facts`, `Goal.of` (Task 2).
- Produces: `Starter(version: Literal[7], intent: Intent, facts: Facts)` with `.goal -> Goal`, `extra="forbid"`; `pipeline_file.goal_from(path: Path) -> Goal` reading a starter, or the old goal format (`have`/`want`/`profile`).

- [x] **Step 1: Write the failing tests:**
  - `test_a_starter_builds_the_spine_byte_for_byte`: `mendel build examples/rnaseq.yml --out <tmp>` writes a v7 `pipeline.yml` and a `main.nf` equal to `tests/golden/spine/main.nf`.
  - `test_the_old_goal_format_still_builds`: `mendel build --goal <the old rnaseq-goal.yml content in tmp>` → the same `main.nf`.
  - `test_a_starter_with_steps_is_not_a_starter`: `goal_from` on a full `pipeline.yml` raises with a sentence saying a full file is upgraded with `mendel upgrade`, not built.
  - `test_the_example_starter_is_intent_and_facts_only`: `set(yaml.safe_load(examples/rnaseq.yml)) == {"version", "intent", "facts"}`.
- [x] **Step 2: Run; expect FAIL** (no `Starter`, `examples/rnaseq.yml` missing).
- [x] **Step 3: Implement.** Write `examples/rnaseq.yml` from the current example's meaning (`source: said` for `paired`, `read_length`, `strandedness`; `n_samples` as in the old file). `build` takes the positional `target` or `--goal`, both through `goal_from`; neither given is the existing `parser.error`. `settings.example_goal` defaults to `./examples/rnaseq.yml`.
- [x] **Step 4: Run `make test`; expect PASS.** Update the four docs pages to the starter form; `goal-schema.md` becomes the starter's reference, saying the old format still reads.
- [x] **Step 5: Commit** `feat(cli): a starter is a v7 pipeline.yml with only intent and facts (Plan B)`.

### Task 6: finish

- [ ] **Step 1:** `make check` (expect exit 0), then `make verify` (resolution, emission and the saved schema changed: it needs Docker and Nextflow; ask the operator before starting it, since it uses the machine).
- [ ] **Step 2:** `CHANGELOG.md`, under Unreleased → `comeni-core` and `mendel-compiler`: schema 7 (breaking for readers of `goal:`; v6 still loads), `said`, layer locators, the starter, MD0231/MD0232.
- [ ] **Step 3:** A journal entry; tick this plan; one line in `now.md` under *The emitted pipeline*.
- [ ] **Step 4:** Commit `docs: Plan B, the save file`; open a PR closing nothing but referring to #307 and #357.

## Self-review

- **Spec coverage:** §8.1 → Tasks 1, 2; §8.2 → Tasks 3, 4; §8.3 → Task 2; §8.4 → deferred (#357); §8.5 → Task 5; §9's *v6 file* and *dirty layer* rows → Tasks 2, 3; §10's save-file, starter, purity and egress items → Tasks 2, 3, 5 and the guards in Task 3 Step 4. §10's *`mendel upgrade` from a lone v7 file rebuilds identically* → covered by `test_a_v6_file_upgrades_with_the_same_goal_and_nf` and the existing `tests/artifact/test_upgrade.py`, re-run in Task 2 Step 4.
- **Types:** `Intent`, `Facts`, `Goal.of`, `Locator`, `locators`, `Starter`, `goal_from` are each defined in one task and used by name after.
- **Estimate:** six tasks. My estimates on this project have run about ten times long, so expect several sessions; if the work passes twice this plan's shape, I stop and say why.

## Execution notes

*(Deviations and rulings recorded here as the work proceeds.)*
