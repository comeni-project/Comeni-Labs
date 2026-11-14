# Per-sample stage 1: grain, scope and sources — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A rule, a module's `meta` or a tool rule can read a fact that differs per sample. Each
sample's value comes from its samplesheet cell, then a measurement in the run, then a fallback
fixed at build time. The build folds everything it already knows.

**Architecture:** `Grain` replaces `Scope` and `Cardinality`. A measurement's scope is derived
from the grain of the type it describes. Part 4's run-time lookup (`AtRun`) is generalised from one measured fact
to several facts, each from a cell or a measurement. One case generator gives the build its
coverage and overlap checks, and gives the agreement tests their cases. The samplesheet gains typed fact columns, checked
when the run starts. A contract's `when` may read `fact.<measurement>`, evaluated per sample.

**Tech Stack:** Python 3.12 (pydantic), Nextflow DSL2 / Groovy, FastAPI, React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md` (stage 1 of its Stages; goals
A, B, C, D, with the parts of I that stage 1 shows).

## Global Constraints

- The same goal and recorded decisions give the same pipeline. Sort unordered sets before serialising.
- Every run-time value is computed only from the closed tests and operations of `comeni_core.plan.at_run`, written as Groovy by `mendel_compiler.groovy_lookup`.
- Mendel never sees a samplesheet cell (invariant 15). Cells are checked inside the pipeline.
- No backward compatibility before v0.1.0: `Scope`, `Cardinality`, `per_sample` and `MD0328` go, with no aliases.
- New diagnostics are declared in `packages/comeni-core/src/comeni_core/diagnostics.yml` and raised through `coded()`, starting at `MD0331`.
- `pipeline.yml` changes bump `SCHEMA_VERSION` to 9. Stored shapes that embed a changed model get version bumps and an alembic migration in `packages/mendel-api/migrations/versions/`, following `d4a7c2e9b815_measured_coverage.py`.
- Registry edits go on the `measurers` branch in `../comeni-registry-measurers`, and the submodule pointer moves with them.
- Checks run separately before each commit. Never chain git after `cd`; use `git -C`. Never run bare pytest while the dev DB is up. Run DB tests with `make test` or with `MENDEL_TEST_DATABASE_URL` and `WIENER_TEST_DATABASE_URL` on port 5442. Only one DB run at a time.
- After each task, a fresh reviewer (opus) reviews it, and its findings are fixed before the next task.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A cell outside its allowed values** (`Forward`, `yes`, `1.5` for an integer, a blank in a required column). The run stops before any process starts, naming the row, the sample and the column. It is never read as blank. Pinned in Task 6.
2. **A sample whose fact comes back undetermined, for a setting with no default.** It gets the fallback the person chose at build time, a value or "stop the run". It never silently gets the tool's own value. Pinned in Tasks 5 and 8.
3. **A goal that states a fact and also says it varies.** Refused at the goal boundary, naming the fact. Pinned in Task 3.
4. **Boundary values in Python and Groovy.** A row `>= 70` against 70, 69, `70.0` and an integer fact given `69.5` gives the same answer in the resolver and in Nextflow. Pinned in Task 4's cases and Task 5's agreement test.
5. **A fact column on a pipeline with one per-sample input.** It becomes a samplesheet pipeline. The run sheet shows the column and its allowed values, and a glob is no longer offered. Pinned in Tasks 6 and 8.

---

### Task 1: Grain replaces scope and cardinality

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/tiers.py` (`Scope` → `Grain`)
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py` (`Cardinality`, `InputPort.cardinality` → `InputPort.grain`, `InputPort.many`)
- Modify: `packages/comeni-core/src/comeni_core/declared/vocabulary.py` (`scopes` → `grains`; the type file's `scope:` → `grain:`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`Channel.scope` → `Channel.grain`, validation, `SCHEMA_VERSION = 9`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py`, `packages/comeni-core/src/comeni_core/egress/forge.py` (`TypeScope`), `packages/mendel-compiler/src/mendel_compiler/emit.py`, `packages/mendel-forge/src/mendel_forge/testing.py`, and every other file `grep -rn "Scope\.\|Cardinality\|cardinality\|TypeScope"` lists under `packages/*/src`
- Modify: forge prompts that name `cardinality` or `scope` (`packages/mendel-api/src/mendel_api/forge/prompts/parts/`). Edit only the newest version of each part, and bump its version as the prompts' README says.
- Modify: `frontend/src/build/living/CollectionChannel.tsx`, `LivingCanvas.tsx`, `fake.ts`, `frontend/src/registry/forging/QuestionCards.tsx`, `frontend/src/registry/Tool.tsx` and their tests (`"run"` → `"study"`); `make client`
- Registry: `vocabulary/types/{genome.fasta,genome.fai,annotation.gtf}.yml` (`scope: run` → `grain: study`), `tools/nf-core/multiqc/contract.yml` (`cardinality: "*"` → `grain: study, many: true`)
- Migration: new `packages/mendel-api/migrations/versions/<rev>_grain.py`, with shape bumps in `packages/mendel-api/src/mendel_api/shape_versions.py` for every stored shape that embeds a `Channel`, a `TypeScope` or a contract port
- Docs: `docs/reference/registry/contract-schema.md`, the type schema page, `docs/reference/pipeline-schema.md` (find them with `grep -rln "cardinality\|scope:" docs/reference`)
- Test: `tests/registry/test_grain.py` (new); existing `tests/emit/test_fan_in.py`, `test_fan_out.py` and `test_samplesheet.py` updated

**Interfaces:**
- Produces: `class Grain(StrEnum): STUDY = "study"; SAMPLE = "sample"` in `comeni_core.plan.tiers`. Ruling: `group`, `unit` and `part` are added by the stages that give them meaning. `InputPort.grain: Grain | None = None` (None = the type's grain). `InputPort.many: bool = False`: one invocation takes every item of a finer grain, gathered with `.collect()`; serialised only when true. `Channel.grain: Grain`. `Vocabulary.grains: dict[TypeId, Grain]`. `TypeScope` → `TypeGrain` with the same two values.

- [x] **Step 1: Write the failing tests** in `tests/registry/test_grain.py`:
  - `test_a_reference_type_is_study_grain`: `layers.load(ROOT/"registry").vocabulary.grains["genome.fasta"] is Grain.STUDY`, and `"fastq.reads"` is absent, so it defaults to `SAMPLE`.
  - `test_multiqc_gathers_the_study`: the multiqc contract's `reports` port has `grain is Grain.STUDY and many is True`.
  - `test_cardinality_is_gone`: `ModuleContract.model_validate` of a contract whose port says `cardinality: "*"` raises with `extra` forbidden.
  - `test_many_on_a_study_type_is_refused`: `many: true` on a port whose type is already study grain raises `MD0331` ("nothing finer to gather").
- [x] **Step 2: Run** `uv run pytest tests/registry/test_grain.py -q`. Expected: FAIL, because `Grain` does not exist.
- [x] **Step 3: Implement the rename everywhere the grep lists.** Materialise's `gather` becomes `port.many`. `_as_value` keys on `Grain.STUDY`. `_form` and the samplesheet validator count `Grain.SAMPLE` channels. Declare `MD0331` ("a port gathers a type that is already study-wide"). Move the registry edits on the `measurers` branch and the submodule pointer.
- [x] **Step 4: Write the migration.** Each upgrader rewrites `scope: run|sample` → `grain: study|sample` and `cardinality: "*"` → `grain: study, many: true` wherever the bumped shapes store them, and leaves everything else untouched. Add a test beside the existing migration tests (`grep -rln d4a7c2e9b815 tests`) running each upgrader on one old payload.
- [x] **Step 5: Run** `uv run pytest tests/registry/test_grain.py tests/emit -q -m "not slow"`, `make check`, `make guards`, and `cd frontend && npx vitest run && npx tsc -b`, each separately. Expected: all pass. `make static` builds the example with `grain` in `pipeline.yml`.
- [x] **Step 6: Commit** `refactor: grain replaces scope and cardinality (#466)`.

### Task 2: A measurement's scope comes from what it describes

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/measurement.py` (drop `per_sample`; add `MeasurementRegistry.scope_of`)
- Modify: `packages/comeni-core/src/comeni_core/goal/profile.py` (the list docstring), `packages/mendel-resolver/src/mendel_resolver/layers.py` (pass the grains to the measurement registry at load)
- Modify: `diagnostics.yml` (`MD0312` and its sibling texts name the scope, not `per_sample`), forge prompt parts that offer `per_sample` (newest versions only)
- Registry: `vocabulary/measurements/read_length.yml` (drop `per_sample: true`)
- Docs: the measurement schema page
- Test: `tests/registry/test_measurement_scope.py` (new)

**Interfaces:**
- Consumes: `Grain`, `Vocabulary.grains` (Task 1).
- Produces: `MeasurementRegistry.scope_of(measurement_id: str) -> Grain`. It is the grain of the measurement's `describes` type, defaulting to `SAMPLE` for a type with no declared grain, and `STUDY` when it describes nothing. A profile list is valid iff `scope_of` is `SAMPLE`.

- [x] **Step 1: Write the failing tests:**
  - `test_read_length_is_per_sample`: `scope_of("read_length") is Grain.SAMPLE`.
  - `test_genome_length_is_study`: `scope_of("genome_length") is Grain.STUDY`, because `genome.fasta` is study grain.
  - `test_organism_is_study`: it describes nothing, so `scope_of("organism") is Grain.STUDY`.
  - `test_a_list_for_a_study_fact_is_refused`: `measurements.profile({"genome_length": [1, 2]})` raises and names `genome_length`.
  - `test_per_sample_is_gone`: a measurement declaring `per_sample: true` fails to load.
- [x] **Step 2: Run** `uv run pytest tests/registry/test_measurement_scope.py -q`. Expected: FAIL.
- [x] **Step 3: Implement.** The registry learns the grains at `layers.load`. A registry built without them (tests constructing it directly) treats every `describes` type as `SAMPLE`. Delete `per_sample` from the model, the registry file and the prompts.
- [x] **Step 4: Run** the new tests, then `make check`, separately. Expected: pass.
- [x] **Step 5: Commit** `refactor: a measurement's scope is its type's grain (#466)`.

### Task 3: "It varies" — a person says a fact differs between samples

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py` (`Constraints.varies`)
- Modify: `packages/mendel-api/src/mendel_api/authoring/types.py` (`Fact.varies`), `services/gaps.py` (the option), `stages/gathering.py` (`_fact_for`, `compose_goal`), `stages/goal.py` (`readback_context`), and the goal card view, so it shows "varies between samples"
- Modify: `diagnostics.yml` (`MD0332`)
- Frontend: the gap card and the goal card. Options come from the server, so only the label of a fact that varies is new (`grep -rn "person_said" frontend/src/build`).
- Migration: `Fact` is stored in turns, so bump the turn shape. Old rows lack the field and read false, so the upgrader is the identity.
- Test: `tests/goal/test_varies.py` (new; create the folder if absent), plus a gathering test beside the existing `_answer_gap` tests (`grep -rln "_answer_gap\|AnswerGap" tests`)

**Interfaces:**
- Consumes: `MeasurementRegistry.scope_of` (Task 2).
- Produces:
  - `Constraints.varies: list[MeasurementId]`, sorted and unique, excluded when empty.
  - `Fact.varies: bool = False`, which is only valid with `source=PERSON_SAID` and `value=None`.
  - The gap option id `"varies"`.
  - `MeasurementRegistry.check_varies(goal) -> None`, which raises `MD0332` naming the fact when a fact in `varies` is study-scoped or also has a value in `goal.profile`.

- [x] **Step 1: Write the failing tests:**
  - `test_a_fact_cannot_be_stated_and_vary`: a goal with `profile: {strandedness: reverse}` and `varies: [strandedness]` raises `MD0332`, naming `strandedness`.
  - `test_a_study_fact_cannot_vary`: `varies: [genome_length]` raises `MD0332`.
  - `test_the_gap_offers_varies_for_a_sample_fact`: the strandedness gap for the rnaseq want, from `gaps.gaps`, lists an option `"varies"`. The genome_length gap does not.
  - `test_answering_varies_composes_it`: after `_answer_gap` with `option="varies"` on strandedness, `compose_goal(session).constraints.varies == ["strandedness"]` and `profile.get("strandedness") is None`.
- [x] **Step 2: Run** them. Expected: FAIL.
- [x] **Step 3: Implement.** Offer `"varies"` when the measurement is sample-scoped and every reader of it can take a per-sample value: a `param` decision, a `meta_key` carried on the type it describes, or a contract `fact.` condition (Task 7; until then, the first two). Its label is "It differs between samples". The resolver calls `check_varies` where it validates the profile.
- [x] **Step 4: Run** the tests, then `make test`, separately. Expected: pass.
- [x] **Step 5: Commit** `feat: a person can say a fact varies between samples (#466)`.

### Task 4: The cases of a rule — coverage and overlap

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/cases.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules/validate.py` (`hit: unique` overlap at load)
- Modify: `diagnostics.yml` (`MD0333` overlap, `MD0334` too many cases)
- Test: `tests/resolver/test_cases.py` (new; place it beside the existing rule tests, `grep -rln "hit: unique\|hit=\"unique\"" tests`)

**Interfaces:**
- Produces:
  - `UNDETERMINED: object`, a sentinel for a fact that could not be decided.
  - `cases(facts: dict[str, Measurement], literals: dict[str, list]) -> list[dict[str, object]]`. Every combination of a representative value per fact, plus `UNDETERMINED` for each. Booleans give `True` and `False`. Enums give their `values`. Numbers give each literal the rows compare against, a value between each neighbouring pair, one below the lowest and one above the highest, clipped to `minimum`/`maximum`. For `integer` the in-between values are whole numbers where a whole number exists between them, plus `literal ± 1`. The order is deterministic, and more than `CASE_BOUND = 4096` raises `MD0334`.
  - `uncovered(decision: Decision, unknown: dict[str, Measurement], known: dict) -> list[dict]`: the cases no row matches, evaluated with `matches` after substituting `known`.
  - `overlapping(decision, unknown, known) -> list[tuple[int, int, dict]]`: pairs of row indexes that match one case.

- [x] **Step 1: Write the failing tests:**
  - `test_numeric_cases_straddle_each_threshold`: for `read_length` (integer, minimum 1) with literals `[70]`, the cases are exactly `[1, 69, 70, 71, UNDETERMINED]` in that order.
  - `test_alignment_rows_leave_only_undetermined_uncovered`: `uncovered` of `registry/rules/alignment.yml`'s decision over `{read_length}` is `[{"read_length": UNDETERMINED}]`.
  - `test_a_gap_between_rows_is_uncovered`: rows `>= 70` and `< 50` leave `{read_length: 50}` and `{read_length: 69}` (and undetermined) uncovered.
  - `test_overlapping_unique_rows_are_refused_at_load`: a `hit: unique` table with rows `>= 70` and `>= 50` fails `RuleTable.load` with `MD0333`, naming rows 1 and 2 and the case `read_length: 70`.
  - `test_two_facts_take_their_product`: an enum of three values and a boolean give `(3 + 1) * (2 + 1) = 12` cases.
  - `test_too_many_cases_is_refused`: seven enum facts of four values each raise `MD0334`, since 5^7 > 4096.
- [x] **Step 2: Run** `uv run pytest tests/resolver/test_cases.py -q`. Expected: FAIL, because the module does not exist.
- [x] **Step 3: Implement `cases.py`.** Call `overlapping` from the `hit: unique` validation, with every fact the decision reads that is not a derived fact unknown.
- [x] **Step 4: Run** the new tests and `make check`, separately. Expected: pass. Any shipped `unique` table that now fails is a real overlap: report it, don't loosen the check.
- [x] **Step 5: Commit** `feat: a rule's cases, its coverage and its overlaps (#466)`.

### Task 5: A run-time lookup over several facts, each from a cell or a measurement

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/plan/at_run.py` (model)
- Modify: `packages/mendel-resolver/src/mendel_resolver/at_run.py` (`needed`, `rows_of`, `lookup`, `deferrable`), `resolve.py` (where `needed` is consumed), `packages/mendel-api/src/mendel_api/services/gaps.py` (`_decided_in_the_run`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/groovy_lookup.py` (`closure`), `emit.py` (`_decided`, `_check_measuring`)
- Modify: `diagnostics.yml` (retire `MD0328` as `MD0003` was retired; see line ~1887)
- Modify: `packages/mendel-api/src/mendel_api/views/…` `AtRunView` (`grep -rn "def at_run_view"`), `frontend/src/build/Settings.tsx`
- Test: `tests/resolver/test_at_run.py` (extend), `tests/emit/test_at_run_agreement.py` (extend, slow), `tests/emit/test_star_index_at_run_gate.py` (must still pass unchanged in behaviour)

**Interfaces:**
- Consumes: `cases`, `uncovered`, `UNDETERMINED` (Task 4); `Constraints.varies` (Task 3).
- Produces:
  - `class AtRunSource(StrEnum)`: `CELL = "cell"`, `MEASURED = "measured"`, `CELL_OR_MEASURED = "cell_or_measured"`.
  - `class AtRunFact(BaseModel)`: `measurement`, `meta_key`, `source: AtRunSource`, `measured_by: ContractId | None`. `measured_by` is set iff the source involves `MEASURED`.
  - `class AtRunCondition(BaseModel)`: `fact`, `test: AtRunTest`, `operand`.
  - `AtRunRow`: `when: list[AtRunCondition]` replaces `test`/`operand`. `takes: MeasurementId | None` replaces `takes_fact`. `then`, `transform` and `integer` stay as they are.
  - `AtRun`: `facts: list[AtRunFact]` (sorted by measurement) replaces `fact`/`meta_key`/`measured_by`. `rule`, `rows`, `fallback`, `fallback_reason` and `fallback_is` stay.
  - `AtRunFallback.STOP = "stop"`: the run stops, naming the sample and the rule.
  - `Needed`: `facts: tuple[str, ...]` replaces `fact`.
  - Semantics:
    - A condition on a null fact is false.
    - A row with `takes` is skipped when that fact is null.
    - The fallback applies when no row matches.
    - `STOP` emits `error("sample ${meta.id}: <rule> has no row for its <facts>")`.

- [x] **Step 1: Write the failing tests** in `tests/resolver/test_at_run.py`:
  - `test_a_setting_waits_on_two_facts`: a fixture rule with `param` rows over `read_length` (measured) and `strandedness` (in `varies`) gives one `Needed` with `facts == ("read_length", "strandedness")`. Its `AtRun.facts` sources are `MEASURED` and `CELL`.
  - `test_varies_without_a_measurer_is_a_cell`: `strandedness` in `varies`, read by a param rule, gives `source is AtRunSource.CELL` and `measured_by is None`.
  - `test_a_varying_fact_with_a_measurer_is_cell_or_measured`: `read_length` in `varies` gives `CELL_OR_MEASURED`.
  - `test_the_fallback_order`, for a setting whose rows leave cases uncovered: with a default, `fallback_is VALUE`; omittable with no default, `TOOL`; neither, `QUESTION`. A recorded answer of `"stop"` gives `STOP`.
  - `test_star_index_unchanged`: the shipped rnaseq goal with no genome length gives the same rows as before (one fact, `genome_length`, `MEASURED`).
- [x] **Step 2: Extend the agreement test** (`tests/emit/test_at_run_agreement.py`). For every shipped run-time rule and the two-fact fixture, run every case from `cases()` through the resolver and through Nextflow. Pass `UNDETERMINED` to Groovy as `null`. Assert equal results, including `69.5` for an integer fact.
- [x] **Step 3: Run** the pure tests. Expected: FAIL. Run the agreement test after Step 4.
- [x] **Step 4: Implement.**
  - `needed` accepts any number of unknown facts. Each must be reachable from a cell (in `varies`) or a measurer through lineage (part 4's `_measurable`). A fact reachable by neither leaves the setting to the lower tiers, as today.
  - `rows_of` substitutes known facts and keeps conditions on the unknown ones. A `then: {fact}` chain may read any one unknown fact.
  - The fallback follows the spec's order. The setting's existing tier-4 question gains the legal answer `"stop"` ("Stop the run and name the sample"), which is validated where answers are received.
  - `closure` reads several `meta` keys.
  - Retire `MD0328`.
  - The view and `Settings.tsx` list every fact with its source: "from the samplesheet", "measured in the run", or "from the samplesheet, measured where left blank".
- [x] **Step 5: Run** `uv run pytest tests/resolver -q`, `uv run pytest tests/emit/test_at_run_agreement.py tests/emit/test_star_index_at_run_gate.py -q` (slow, Docker and Nextflow), `make check`, and the frontend tests, each separately. Expected: all pass.
- [x] **Step 6: Commit** `feat: a run-time setting reads several facts, from cells or measurements (#466, #217)`.

### Task 6: The samplesheet's fact columns

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`SheetFact`, `Pipeline.sheet_facts`, the samplesheet validator)
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py` (derive `sheet_facts`; a varying fact leaves `Channel.meta`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_from_samplesheet` reads cells; `_check_rows`; `_joined` measures only rows left blank; `_decided` records the source)
- Modify: `packages/mendel-compiler/src/mendel_compiler/gates.py` and `emit.test_samplesheet` (the test profile's one row fills each fact column with its test value: the first allowed value, or `auto` where measured)
- Modify: `packages/wiener-api/src/wiener_api/services/measured.py` and `wiener_core/measured.py` (read the decided tsv's new columns)
- Modify: `diagnostics.yml` (`MD0335`: a samplesheet pipeline whose fact columns would collide with a file column or `sample`)
- Test: `tests/emit/test_sheet_facts.py` (new; pure, plus one `slow` Nextflow run), `tests/artifact/test_sheet_facts.py` (new)

**Interfaces:**
- Consumes: `AtRun.facts` and `AtRunSource` (Task 5); `Constraints.varies` (Task 3).
- Produces:
  - `class SheetFact(BaseModel)`:
    - `measurement`, `column: NfIdentifier` (the measurement id), `kind: MeasurementKind`;
    - `values: list[str]`, `minimum`, `maximum`;
    - `required: bool`; `auto: bool` (a measurer fills a blank or `auto`);
    - `meta: list[MetaKeyOf]`, each `{key, translate: list[MetaValue]}`: the fact id for lookups, plus the module's `meta_key` with its `meta_values`;
    - `why: Why`.
  - `Pipeline.sheet_facts: list[SheetFact]`, sorted by column and excluded when empty.
  - **Derivation** (materialise):
    - every fact in `varies`, required unless a measurer reaches it;
    - every fact an `AtRun` reads as `CELL_OR_MEASURED`;
    - a measured-only fact gets no column unless the pipeline already takes a samplesheet. Then it gets an optional `auto` column (ruling: a direct-input pipeline that only measures stays direct).
  - A non-empty `sheet_facts` makes the input form a samplesheet, even with one sample-scoped channel. The validator's "at least two" becomes "at least two, or a fact column".
  - The decided tsv line is `sample\tvalue\t<fact>=<value>:<cell|measured|fallback>` per fact, sorted by fact.

- [x] **Step 1: Write the failing tests:**
  - `test_varying_strandedness_is_a_required_column`: the rnaseq goal with `varies: [strandedness]` materialises `sheet_facts == [SheetFact(column="strandedness", kind=enum, values=["forward","reverse","unstranded"], required=True, auto=False, ...)]`. The reads channel's `meta` has no `strandedness` entry, and the input form is samplesheet.
  - `test_cells_reach_meta`: the emitted `main.nf` projection includes `strandedness: row.strandedness` translated through `meta_values`, and the fact id key.
  - `test_a_bad_cell_stops_the_run` (slow): run the emitted pipeline's stub on a two-row sheet whose second row says `Forward`. Expected: non-zero exit, and stderr contains `samplesheet row 2 (sample S2), column strandedness: 'Forward' is not one of forward, reverse, unstranded`.
  - `test_a_blank_required_cell_stops_the_run` (slow), likewise: `column strandedness is required`.
  - `test_only_blank_cells_are_measured` (slow): a fixture pipeline with `read_length` as `CELL_OR_MEASURED` over two rows, one `150` and one blank. The measuring step runs once, and the decided tsv says `read_length=150:cell` for the first row and `...:measured` for the second.
  - `test_an_integer_cell_must_be_whole` (slow): `69.5` in an integer column stops the run naming the row and column.
- [x] **Step 2: Run** them. Expected: FAIL.
- [x] **Step 3: Implement.**
  - `_check_rows` is emitted after `splitCsv` and before any projection. It checks every fact column for allowed values and kind, `minimum`/`maximum`, blank only where not required, and `auto` only where `auto`. `boolean` accepts `true`/`false` only.
  - Each projection's `meta` gets the parsed cells, null for blank or `auto`.
  - `_joined` branches each channel carrying measured facts. Rows with every measured fact non-null go around the measuring step; the others go through it and join. The two are mixed. A cell wins over a measurement.
  - `_decided` writes the source. The source is carried on `meta.comeni_from`, a map from fact to source, which modules ignore.
  - Wiener's reader takes the new columns, and shows the source on the run page.
- [x] **Step 4: Run** the pure tests, then the slow ones, then `make check`, `make static` and `make test`, each separately. Expected: all pass.
- [x] **Step 5: Commit** `feat: the samplesheet carries per-sample facts, checked when the run starts (#466)`.

### Task 7: A tool rule reads a per-sample fact

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py` (`_when_keys` accepts `fact.<measurement>`)
- Modify: `packages/comeni-core/src/comeni_core/declared/constraints.py` (`Setup.facts`, `Setup.unknown_facts`; worlds over them)
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py` (checks `fact.` keys against the measurements, `MD0336`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`SampleRule`, `Step.sample_rules`), `materialise.py`, `emit.py` (the per-sample guard; a forbidden setting dropped per sample)
- Modify: the forge's constraint drafting prompt and checks, so a drafted `when` may use `fact.` (newest prompt part; `services/forge_checks.py`)
- Test: `tests/constraints/test_per_sample_rules.py` (new; place beside the #460 constraint tests, `grep -rln "holds_at_run_time" tests`), `tests/emit/test_sample_rules.py` (pure, plus one slow run)

**Interfaces:**
- Consumes: `cases` (Task 4); `AtRunCondition` (Task 5); `meta` cells (Task 6).
- Produces:
  - `Setup.facts: dict[str, Any]` (known per-sample facts) and `Setup.unknown_facts: dict[str, list]` (their cases).
  - `Verdict.per_sample: list[str]`: sentences of rows only a sample's facts can settle.
  - `class SampleRule(BaseModel)`: `when: list[AtRunCondition]`, `says: Line`.
  - `Step.sample_rules: list[SampleRule]`, excluded when empty.
  - `MD0336`: a contract's `fact.<m>` names a measurement no layer declares, or a study-scoped one. The contract is dropped, as `MD0327` drops a measurer.

- [x] **Step 1: Write the failing tests:**
  - `test_a_rule_broken_by_some_samples_is_per_sample`: a fixture contract (fastp-like) with `save_merged` and the row `{when: {fact.paired: false}, forbids: [save_merged], because: "merging needs both reads"}`. It is evaluated with `params={"save_merged": True}` and `unknown_facts={"paired": [True, False, UNDETERMINED]}`, giving `per_sample == [that sentence]` and nothing `forbidden`.
  - `test_a_rule_broken_by_every_sample_is_refused`: the same contract with `facts={"paired": False}` gives `forbidden == ["save_merged"]`.
  - `test_a_default_setting_is_dropped_per_sample`: when `save_merged` came from the contract's default, the emitted `ext.args` closure gives no `--save_merged` for a sample with `meta.paired == false`. The step card lists it as "not set for single-end samples: merging needs both reads".
  - `test_a_person_setting_stops_the_sample` (slow): when a person set `save_merged`, a single-end row stops the run with `sample S2: merging needs both reads (save_merged)`.
  - `test_an_unknown_fact_drops_the_contract`: `fact.nonsense` gives `MD0336`, and the other contracts load.
- [x] **Step 2: Run** them. Expected: FAIL.
- [x] **Step 3: Implement.**
  - The worlds are the product of unknown inputs and fact cases.
  - A row broken in some worlds whose break depends on a fact goes to `per_sample`. It becomes a `SampleRule`, or an `AtRun` row that unsets the setting, under the spec's rule:
    - a default or a rule's value is dropped for those samples;
    - a person's value stops the sample.
  - The guard is a `.map` on the step's first input that raises `error` naming `meta.id` and the sentence.
  - The forge's checker accepts `fact.` keys over declared sample-scoped measurements.
- [x] **Step 4: Run** the tests, `make check`, `make guards` and the slow test, each separately. Expected: all pass.
- [x] **Step 5: Commit** `feat: a tool rule can read a per-sample fact (#466, #460)`.

### Task 8: The run sheet and the step card show it

**Files:**
- Modify: `packages/wiener-api/src/wiener_api/routes/runs.py` (`input_facts: list[SheetFactView]` beside `input_columns`) and where the run form is built from `pipeline.yml`
- Modify: `frontend/src/build/Samplesheet.tsx` (typed cells: a select for enums and booleans with `auto` where allowed, a number input with bounds; `incomplete` skips optional fact columns), `frontend/src/build/Sources.tsx` (no glob option when there are fact columns), `frontend/src/build/Settings.tsx` (fallback `STOP` wording, per-sample tool rules)
- `make client`
- Test: `frontend/src/build/Samplesheet.test.tsx`, `Settings.test.tsx`; `tests/wiener/…` (the run-form route test, `grep -rln "input_columns" tests`)

**Interfaces:**
- Consumes: `SheetFact` (Task 6), `AtRunFallback.STOP` (Task 5), `SampleRule` (Task 7).
- Produces: `SheetFactView {column, kind, values, minimum, maximum, required, auto, why}`.

- [x] **Step 1: Write the failing tests:**
  - `Samplesheet.test.tsx`, "a fact column offers its values": with `facts=[{column:"strandedness", kind:"enum", values:[forward,reverse,unstranded], required:true}]`, the cell is a select with exactly those three. `incomplete` reports a row missing it.
  - "an auto column may be left blank": `incomplete` does not report a blank `read_length` with `auto: true`.
  - "the fallback stop is said": `Settings.test.tsx` renders "If no row applies, the run stops and names the sample".
  - Wiener route test: the run form of a pipeline with `sheet_facts` has `input_form == "samplesheet"` and `input_facts` matching.
- [x] **Step 2: Run** `cd frontend && npx vitest run` and the route test. Expected: FAIL.
- [x] **Step 3: Implement.** Words follow the documentation style guide: "from the samplesheet", "measured in the run where left blank".
- [x] **Step 4: Run** `npx vitest run`, `npx tsc -b` and `make test`, separately. Expected: pass. Browser checks wait for the end of the push (operator, 11-10).
- [x] **Step 5: Commit** `feat: the run sheet asks for per-sample facts; the step card says where they come from (#466)`.

### Task 9: Docs, the demo, and the record

**Files:**
- Docs:
  - `docs/reference/registry/rule-schema.md`: a lookup over several facts; coverage and `hit: unique` checked over cases; the fallback order and `stop`; it varies.
  - The measurement schema: scope comes from the type.
  - The contract schema: `grain`, `many`, `fact.`.
  - `docs/reference/pipeline-schema.md`: `grain`, `sheet_facts`, `sample_rules`, `AtRun.facts`.
  - The how-to for samplesheets (`grep -rln samplesheet docs/how-to`).
- `CHANGELOG.md` (comeni-core, mendel-resolver, mendel-compiler, mendel-api, wiener, frontend), the journal `docs/notes/journal/2026-11-11-per-sample.md`, `docs/notes/now.md`
- Test: `tests/emit/test_strandedness_per_sample.py` (new, slow)

- [x] **Step 1: Write the failing slow test** `test_each_sample_gets_its_strandedness`. Build the shipped rnaseq goal with `varies: [strandedness]` and run it under Docker on nf-core's test reads as two samples, `forward` and `reverse`. Assert each featureCounts task's `.command.sh` has `-s 1` for the first and `-s 2` for the second.
- [x] **Step 2: Run it.** Expected: PASS if Tasks 1–8 hold. A failure is a defect in them: fix it there, with a test.
- [x] **Step 3: Write the docs, the CHANGELOG and the journal.** Tick this plan and record its deviations.
- [x] **Step 4: Run** `make check`, `make guards`, `make doc-sizes` and `make verify`, separately. Expected: pass.
- [x] **Step 5: Commit** `docs: per-sample facts, stage 1 (#466)`.

## Deviations

Every deviation and ruling is in the task ledger (kept in the plan's workspace until the final
review), summarised here:

- Grain has only `study` and `sample`; the other grains arrive with their stages.
- Every contract digest moved once (`cardinality` was always written).
- A measurement's scope is derived from what it describes; `read_length` gained
  `describes: fastq.reads`.
- "It varies" is a fact origin (`varies`); the conversation offers it on `paired`, since
  strandedness is not asked.
- No MD0333/MD0334 as planned for Task 4: the case enumeration already existed and moved to
  `mendel_resolver.cases`. MD0333 was later reassigned, by the operator's decision (11-11), to
  refusing a `unique` rule whose rows can overlap on a per-sample fact.
- The fallback question has its own subject, `<step>.if_no_row.<setting>`.
- A measured-only fact gets no optional `auto` column in a samplesheet pipeline.
- MD0336 refuses the load instead of dropping the contract; MD0337 refuses a value every sample
  breaks.
- A model's answer counts as an explicit value for per-sample rules (operator to confirm).
- Answering "stop" from the app is not built (deferred, #489).
- Full checks and slow runs ran once at the end of the part (operator, 11-11).
