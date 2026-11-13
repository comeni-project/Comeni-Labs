# The forge drafts measurers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a forge adaptation can draft, approve, assemble, prove on Wiener and publish a
`by: tool` measurer (its parser's code and tests) for the tool being forged.

**Architecture:**
- **A new last forge step.** `Piece.MEASURERS` has two item families: the measurer, and its
  measurement when new.
- **One check for parser code.** The pieces' import check moves from a test guard into
  `mendel lint` as MD0027. Item validation, assembly, publishing, the guard and the registry's CI
  all call that one function.
- **The forge's test pipeline gains the generated measuring step.** `measure_steps` already builds
  one for a built pipeline. A test is green only when Wiener's `/runs/{id}/measured` reports a value
  for each drafted measurer.

**Tech Stack:** Python 3.12, Pydantic, pytest, React and vitest. The registry branch is
`measurers`.

**Spec:** `docs/superpowers/specs/2026-11-13-forge-measurers-design.md`

## Global Constraints

- **Branch.** Work on `feat/constraints-phase-1-stages-5-6`. Never push.
- **Git.** Use `git -C`; never chain git after `cd`.
- **Checks.** Run them separately before each commit, with targeted tests per task. Full checks
  run once at the end: `make check`, `make guards`, slow tests, `npx vitest run` and
  `npx tsc -b`.
- **Test database.** Use 5442 via the Make targets or the
  `MENDEL_TEST_DATABASE_URL`/`WIENER_TEST_DATABASE_URL` env vars. Never run bare pytest with the
  dev DB up.
- **Parser code never runs in Mendel's process,** in tests of the forge service included. The
  forge only checks it statically and proves it through the runner.
- **Fixed fields of a drafted measurer:**
  - `by: tool`, `runs: [pipeline]`, `version: 1.0.0`;
  - `uses:` the adaptation's contract id;
  - `entry: piece/<id>.py`; tests in `piece/test_<id>.py`.
- **Registry changes** go on `../comeni-registry-measurers` (branch `measurers`), with
  `approved_by: unreviewed`. Then fetch them into `registry/`.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Diagnostics** are declared in `diagnostics.yml`. Regenerate the doc with
  `uv run python tools/generate_diagnostics_doc.py`.

## Review Focus

1. **A measurer whose output no test expects** is never proven. Validation refuses it with
   "no test expects output X" (Task 2).
2. **A parser that reports "undetermined"** on the test output fails the test with its reason,
   rather than passing (Task 4).
3. **A measurement re-declared from both the vocabulary step and the measurers step** is refused at
   assembly (MF0511), not silently last-wins (Task 3).
4. **Publishing a measurement that differs from the registry's in more than `assertion_only`** is
   still refused (MF0517) (Task 6).
5. **A measurer id that is not a Python identifier** (e.g. `n50-quast`) would break the step's
   module name and the import of its tests, so validation refuses it (Task 2).

---

### Task 1: The pieces' import check is a lint rule (MD0027)

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/registry_lint.py`
- Modify: `tests/guards/test_inspector_pieces.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Test: `packages/mendel-compiler/tests/test_registry_lint_pieces.py` (create)

**Interfaces:**
- Produces:
  - `registry_lint.piece_problems(code: str) -> list[str]`: what a piece's source reaches that it
    may not, sorted. An empty list means it keeps the rules. A syntax error is one problem, its
    message.
  - `registry_lint.pieces(root: Path) -> list[Diagnostic]`: MD0027 for each piece code file under
    `measurers/*/*/piece/` (not `test_*.py`, not under `fixtures/`). `lint(root)` includes it
    whatever the manifest says, so the forge's draft layer (which has no `layout:`) is checked
    too.
  - The constants `ALLOWED`, `BANNED_CALLS`, `BANNED_METHODS`, `BANNED_NAMES` move here from the
    guard.

- [ ] **Step 1: Write the failing tests**
  - `test_allowed_code_has_no_problems`: `piece_problems("from comeni_inspect.outcome import Value\nimport re\n") == []`.
  - `test_each_reach_is_named`: `piece_problems("import os\nopen('x')\nfrom . import y\n")` ==
    `["<open()>", "<relative import>", "os"]`.
  - `test_a_syntax_error_is_a_problem`: `piece_problems("def (")` has length 1 and starts with
    `"syntax error"`.
  - `test_lint_reports_md0027_without_a_layout`: write `registry.yml` (no layout) and
    `measurers/measures/x/piece/x.py` holding `import socket`. Then `[d.code for d in lint(root)] == ["MD0027"]`
    and `"socket"` is in the summary.

- [ ] **Step 2: Run** `uv run pytest packages/mendel-compiler/tests/test_registry_lint_pieces.py -q`.
  Expected: FAIL, because `piece_problems` is not defined.

- [ ] **Step 3: Implement.**
  - Move `_reaches`'s AST walk from the guard into `piece_problems`, working on a string.
  - Add `pieces(root)` and call it from `lint` before the layout early-return.
  - Declare MD0027 (`emitted_by: compiler`, `concern: layout`,
    `says: "a measurer piece reaches outside what pieces may import or call"`,
    `fires_on: [registry lint]`, `refuses: true`, plus a fix and an explanation drawn from the
    guard's docstring).
  - Rewrite the guard's allowlist test to call `piece_problems` over `CODE`. Keep its structure
    tests and its `there_are_pieces` assertion.
  - Regenerate the diagnostics doc.

- [ ] **Step 4: Run** the new tests, `uv run pytest tests/guards/test_inspector_pieces.py -q` and
  `uv run pytest packages/mendel-compiler/tests -q -k lint`. Expected: PASS.

- [ ] **Step 5: Commit** `feat: the pieces' import check is a lint rule, MD0027 (#487)`.

### Task 2: The measurers step and its items

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/forging/model.py` (`Piece.MEASURERS` last, `KEY` grammar)
- Modify: `packages/mendel-forge/src/mendel_forge/forging/rules.py` (`DEPENDS`)
- Modify: `packages/mendel-forge/src/mendel_forge/forging/values.py` (`MeasurerDraft`, families)
- Modify: `packages/mendel-forge/src/mendel_forge/forging/validate.py` (`_measurer_problems`)
- Modify: `packages/comeni-core/src/comeni_core/egress/forge.py` (`ForgePiece.MEASURERS`)
- Modify: `packages/mendel-api/src/mendel_api/services/forge_constructors.py`
- Modify: `frontend/src/registry/forging/pieces.ts`, `ValueDetails.tsx`, `constructors.fixture.json`
- Test: `packages/mendel-forge/tests/test_forge_values.py`, `test_forge_validate.py`,
  `test_forge_forging_rules.py`; `frontend/src/registry/forging/ItemConstructor.test.tsx`

**Interfaces:**
- Produces:
  - `values.MeasurerDraft(_Frozen)` with these fields:
    - `measures: str`;
    - `output: str`;
    - `explain: str` (1–300 characters);
    - `decided: dict[str, JsonValue] = {}`;
    - `code: str` (1–20000 characters);
    - `tests: str` (1–20000 characters).
  - `_FAMILIES` gains `measurers:measurer` → `MeasurerDraft` and `measurers:measurement` →
    `Measurement`.
  - `DEPENDS`: `CONTRACT` and `VOCABULARY` gain `MEASURERS`; `MEASURERS: frozenset()`.
  - Item keys: `measurers:measurer:<id>`, `measurers:measurement:<id>` and `measurers:none`.

- [ ] **Step 1: Write the failing tests**
  - `test_values`:
    - `validate_value("measurers:measurer:genome_length_fai", {...})` returns a `MeasurerDraft`;
    - an extra field such as `by` is refused;
    - `measurers:measurement:x` validates as `Measurement`.
  - `test_forging_rules`:
    - `PIECES[-1] is Piece.MEASURERS`;
    - an adaptation with every other piece settled has `next_piece` equal to `MEASURERS`;
    - approving a change to `contract:output:fai` re-opens an approved `measurers:measurer:x`.
  - `test_validate`, with `_measurer_problems` reached through `check_items`. One problem each
    for:
    1. an unknown `measures` (not in `seen.measurements`, nor a `measurers:measurement:` or
       `vocabulary:measurement:` item here);
    2. an `output` with no `contract:output:` item;
    3. an output that no `tests:test:` item expects: "no test expects output 'fai', so the parser
       cannot be proven";
    4. `code` that `piece_problems` refuses: the problem names it;
    5. `code` with no `def parse(`;
    6. `tests` with no `def test_`;
    7. an id that is not a Python identifier (`n50-quast`);
    8. a `measurers:measurement:<id>` whose value's `id` differs from its key.

    All are MF0507. A good draft yields none.

- [ ] **Step 2: Run** `uv run pytest packages/mendel-forge/tests -q -k "values or validate or forging_rules"`.
  Expected: FAIL.

- [ ] **Step 3: Implement.**
  - Add `measurers` to `KEY` and to `ForgePiece`.
  - Add `("measurers:measurer", "Measurer", True)` and
    `("measurers:measurement", "Measurement", True)` to `KINDS`, and `measurers` to the `:none`
    list.
  - `PIECE_HELP.measurers`: "Review each parser that reads a fact from this tool's output: the
    measurement, the output it reads, its code and its tests. Most tools need none. Tests after
    Assembly run each parser on the tool's real output."
  - In `ValueDetails`, render the string fields `code` and `tests` in a monospace `<pre>`.
  - Regenerate `constructors.fixture.json` the way the existing fixture test says.

- [ ] **Step 4: Run** the Step 2 command and `cd frontend && npx vitest run src/registry/forging`.
  Expected: PASS.

- [ ] **Step 5: Commit** `feat: the forge's measurers step and its items (#487)`.

### Task 3: Assembly writes measurements and measurers (#490)

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/forging/assemble.py` (`write_layer`, `prove`, `_blamed`)
- Test: `packages/mendel-forge/tests/test_forge_assemble.py`; `packages/mendel-api/tests/forge/test_forging_assembly.py`

**Interfaces:**
- Consumes: Task 1's `registry_lint.pieces`; Task 2's `MeasurerDraft`.
- Produces: the draft layer holds the following.
  - `vocabulary/measurements/<id>.yml` (`declares: measurement`) for each approved
    `vocabulary:measurement` and `measurers:measurement` item.
  - `measurers/measures/<id>/measurer.yml`, written as:
    ```yaml
    declares: measurer
    id: <id>
    version: 1.0.0
    measures: <measures>
    by: tool
    uses: <contract id>
    output: <output>
    entry: piece/<id>.py
    runs: [pipeline]
    decided: <decided>   # only when non-empty
    ```
    The item's `explain` is the YAML's leading comment.
  - `measurers/measures/<id>/piece/<id>.py` (`code`) and `piece/test_<id>.py` (`tests`).
  - `prove` runs `registry_lint.pieces(draft)`. Any MD0027 blames `Piece.MEASURERS`.

- [ ] **Step 1: Write the failing tests**
  - `test_a_vocabulary_measurement_is_written` (#490): an approved `vocabulary:measurement:depth`
    lands at `vocabulary/measurements/depth.yml` and loads.
  - `test_a_measurer_is_written_and_loads`: the faidx-style items give the three files above, and
    `layers.load([base, draft]).inspection.measurers["genome_length_fai"].uses` equals the contract
    id.
  - `test_one_measurement_from_two_pieces_is_refused`: the same id under `vocabulary:` and
    `measurers:` raises MF0511, naming both keys.
  - `test_a_piece_that_reaches_out_reopens_measurers` (API): an approved measurer whose code holds
    `import os` (written by a person, so it bypasses drafting validation) fails assembly. The
    message says MD0027, and the measurer item is re-opened.

- [ ] **Step 2: Run** `uv run pytest packages/mendel-forge/tests/test_forge_assemble.py -q` and the
  API assembly test via the test DB. Expected: FAIL.

- [ ] **Step 3: Implement** in `write_layer` and `prove` as above. Make `_blamed` map
  `"MD0027"` and `"measurer"` to `MEASURERS`.

- [ ] **Step 4: Run** the Step 2 commands. Expected: PASS.

- [ ] **Step 5: Commit** `feat: assembly writes measurements and measurers; pieces checked (#487, #490)`.

### Task 4: The test run proves each parser on the tool's real output

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/testing.py` (`build_test_pipeline`, `module_files`)
- Modify: `packages/mendel-forge/src/mendel_forge/runner.py` (`TestRunner.measured`)
- Modify: `packages/mendel-api/src/mendel_api/services/wiener_runner.py` (`measured`)
- Modify: `packages/mendel-api/src/mendel_api/services/forge_tests.py` (`_submit`, `_verdict`, `proven_parsers`)
- Modify: `packages/mendel-api/src/mendel_api/services/bundle.py` (`archive` accepts bytes)
- Test: `packages/mendel-forge/tests/test_forge_testing.py`; `packages/mendel-api/tests/forge/test_forge_tests.py`, `test_wiener_runner.py`

**Interfaces:**
- Consumes: `measure_steps.steps_for(catalogue, registry) -> list[MeasureStep]`;
  `measure_module.files(step) -> dict[str, bytes]`; Task 3's draft layout.
- Produces:
  - `testing.parsers_for(test, stack) -> list[MeasureStep]` returns the generated steps of
    `by: tool` measurers whose `uses == test.contract` and whose `output` the test expects, sorted
    by id.
  - `build_test_pipeline(test, stack)` adds one node per such step. Its id is
    `measure_<measurer id>`, and an edge runs from `tool.<output>` to `measure_<id>.data`. It
    routes with `stack.registry.with_contracts([s.contract for s in steps])`.
  - `module_files(pipeline, stack)` yields `(str, Path | bytes)`. A generated step's files come
    from `measure_module.files`, under `modules/comeni/measure/<name>/`.
  - `TestRunner.measured(run_id) -> list[dict]` returns the run's facts as
    `{measurement, value, undetermined}`. `WienerRunner` reads `GET /api/runs/{id}/measured` and
    keeps `facts`.
  - `forge_tests.parsers_green(measurers: list[str], facts: list[dict]) -> list[Problem]` gives
    MF0515 per measurement with no fact, `"measurer <id>: reported nothing"`, or with only
    undetermined facts, `"measurer <id>: undetermined: <reason>"`.

- [ ] **Step 1: Write the failing tests**
  - `test_forge_testing`, against a stack holding `samtools/faidx` and `genome_length_fai`:
    - `build_test_pipeline` of a faidx test that expects `fai` has a step whose contract id starts
      with `comeni/measure/genome_length_fai`, fed from the tool's `fai`;
    - a test that does not expect `fai` has no such step;
    - `module_files` yields `modules/comeni/measure/genome_length_fai/main.nf` as bytes.
  - `test_wiener_runner`: `measured` reads `facts` from a mocked `/measured`.
  - `test_forge_tests`:
    - with a faidx adaptation that has a measurer, `FakeRunner.facts = [{"measurement": "genome_length", "value": 29903, "undetermined": None}]`
      plus the right files makes the run `passed`;
    - with `facts=[]` it fails, saying `"measurer genome_length_fai: reported nothing"`;
    - an undetermined fact fails with its reason.
  - `parsers_green` unit cases for the three outcomes.

- [ ] **Step 2: Run** the three test files. Expected: FAIL.

- [ ] **Step 3: Implement.** `_verdict` adds `parsers_green(...)` after `green(...)` for runs whose
  draft has measurers. It reads the draft's measurer ids from the draft folder, as `_declared` does
  for the test. `FakeRunner` in both forge API test modules gains `facts` and `measured`.

- [ ] **Step 4: Run** the Step 2 tests. Expected: PASS.

- [ ] **Step 5: Commit** `feat: a forge test runs each drafted parser on the tool's output (#487)`.

### Task 5: The AI drafts the measurers step

**Files:**
- Create: `packages/mendel-api/src/mendel_api/forge/prompts/forge.measurers.v1.md`
- Modify: `packages/mendel-api/src/mendel_api/services/forging_ai.py` (`_DRAFTED_WITH`, `_PURPOSE`)
- Test: `packages/mendel-api/tests/forge/test_forging_ai.py`

**Interfaces:**
- Consumes: Task 2's item shapes and `_measurer_problems`. The `ForgeRequest` stays as it is.
- Produces: `_DRAFTED_WITH[Piece.MEASURERS] = "forge.measurers.v1"`, with purpose
  `IMPLEMENTATION`.

**Prompt content.** Follow `forge.tests.v2`'s structure.
- What a measurer is: one fact from one output.
- When to say `measurers:none`, which is the usual answer: an output that is data for another
  step, not a summary of it.
- The value shape from Task 2.
- The parser contract, copied from the registry README:
  - `parse(stream, decided)` reads a binary line stream;
  - it returns `Value(value=..., evidence={...})` or `Undetermined(reason=..., evidence={...})`
    from `comeni_inspect.outcome`;
  - it never raises and never guesses;
  - its imports come only from the listed allowlist (the module constant rendered in).
- What the tests must do: import the module by its id, and cover a value, an empty input and a
  malformed line.
- A worked example: `genome_length_fai` in full.
- A new measurement goes as a `measurers:measurement:<id>` item. An existing `assertion_only`
  measurement this tool measures is re-declared without the flag.

- [ ] **Step 1: Write the failing test.** `test_measurers_are_drafted_with_their_prompt`: a fake
  client, as in that file, replies with the `genome_length_fai` items. Assert the invocation
  recorded `forge.measurers.v1`, and the item `measurers:measurer:genome_length_fai` is proposed.
  A second reply whose code imports `os` is refused once, with MD0027's words in the retry's
  problems.
- [ ] **Step 2: Run** it. Expected: FAIL (it drafts with `forge.draft.v9`).
- [ ] **Step 3: Implement** the prompt and the two dict entries.
- [ ] **Step 4: Run** `test_forging_ai.py` and the prompts' render tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: the AI drafts measurers with their parser code (#487)`.

### Task 6: Publishing carries measurers and may drop `assertion_only`

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/publishing.py` (`_shared`)
- Test: `packages/mendel-forge/tests/test_forge_publishing.py`

**Interfaces:**
- Produces: `_shared` accepts a `vocabulary/measurements/<id>.yml` whose parsed draft equals the
  registry's file minus `assertion_only` and `assertion_only_because`, and overwrites it. Every
  other difference is still MF0517.

- [ ] **Step 1: Write the failing tests**
  - `test_place_drops_assertion_only`: the target holds `assertion_only: true` with a reason, and
    the draft is the same without them. The target is replaced.
  - `test_place_refuses_another_measurement_change`: a changed `description` is refused with
    MF0517.
  - `test_place_adds_a_measurer_folder`: the three measurer files are placed under
    `measurers/measures/<id>/`, and `check(checkout)` (which lints MD0027) passes.
- [ ] **Step 2: Run** `uv run pytest packages/mendel-forge/tests/test_forge_publishing.py -q`.
  Expected: FAIL on the first test.
- [ ] **Step 3: Implement** a `_drops_assertion_only(source, target) -> bool` beside
  `_states_missing`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: publishing a measurer, and dropping assertion_only (#487)`.

### Task 7: End to end — re-create `genome_length_fai` through the forge

**Files:**
- Test: `packages/mendel-api/tests/forge/test_forge_measurers.py` (create)

**Interfaces:**
- Consumes everything above.

- [ ] **Step 1: Write the test.** `test_faidx_measurer_from_draft_to_publish_record`:
  1. Re-forge `nf-core/samtools/faidx@1.24` with fake source, runner and publisher, following the
     pattern of `test_forge_tests.py` and `test_forge_publish.py`.
  2. Approve the seeded items; write `vocabulary:none` and `rules:none` and a test that expects
     `fai`.
  3. Draft measurers with a fake client replying the `genome_length_fai` items, then approve them.
  4. Assemble, test (the fake reports the fact), publish to a temporary checkout.
  5. Assert the checkout's `measurers/measures/genome_length_fai/piece/genome_length_fai.py`
     equals the drafted code.
  6. Assert the pull request's record lists `measurers:measurer:genome_length_fai` as drafted by
     the AI and decided by the person.
- [ ] **Step 2: Run** it through the test DB. Expected: PASS. If it fails, the defect is in an
  earlier task: fix it there, with a test that fails first.
- [ ] **Step 3: Commit** `test: the forge re-creates genome_length_fai end to end (#487)`.

### Task 8: Registry CI, docs and the finish

**Files:**
- Registry (`../comeni-registry-measurers`): `.github/workflows/ci.yml` gains a step, "The pieces'
  tests pass". It installs `comeni-inspect` at `ENGINE_REF` with pytest and runs
  `uv run --with pytest --with "comeni-inspect @ git+…#subdirectory=packages/comeni-inspect" pytest measurers -q`.
  `measurers/README.md` gains "The forge can draft one" (two sentences pointing to the forge's
  Measurers step).
- Comeni-Labs: the forge how-to page (find it with `grep -rl "Tests after" docs/`); `CHANGELOG.md`
  under mendel-forge and mendel-api; the journal note; `docs/notes/now.md`.

- [ ] **Step 1: Make the registry edits.** Commit on `measurers`, then
  `git -C registry fetch -q ../comeni-registry-measurers measurers && git -C registry checkout -q FETCH_HEAD`.
- [ ] **Step 2: Edit the docs.**
- [ ] **Step 3: Run the full checks**, each separately: `make check`, `make guards`, slow tests,
  `npx vitest run`, `npx tsc -b`. Expected: all pass.
- [ ] **Step 4: Commit** `docs: the forge drafts measurers (#487)` and tick this plan.
- [ ] **Step 5: Run the final review.** A fresh reviewer on the most capable model reviews the
  branch range. Fix Critical and Important findings test-first, and add Minors to #489.
