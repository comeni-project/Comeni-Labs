# Measurers and run-time decisions: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the operator
> chose inline execution, with a fresh reviewer after each task). Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** One `measurer` declaration that runs on the server and in the pipeline. Facts that
record their coverage. Settings decided at run time from facts measured in the pipeline. Estimates
confirmed in the run, with any disagreement shown.

**Architecture:** `comeni-inspect`'s core becomes stdlib-only, so the same measure code runs in
the sandbox and in a pipeline step. Each pipeline measurer is turned into a synthetic contract
`comeni/measure/<id>` that produces `measurement.<id>`, so the router routes measurement like any
other step. A run-time decision adds that want, re-routes, and records `at_run` on the setting. The
emitter joins the fact into `meta` and writes the setting as a Groovy closure over it. Wiener reads
the published facts at completion.

**Tech Stack:** Python 3.12, pydantic, Nextflow DSL2/Groovy, FastAPI and SQLAlchemy (Alembic),
React with TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-10-measurers-design.md`

## Global Constraints

- `comeni-core`, `mendel-resolver`, `mendel-compiler`, `wiener-core` and `comeni-inspect`'s core
  do no network I/O. The pipeline runner reads only the files it is handed.
- The same goal and recorded decisions reproduce the same pipeline. Sort every unordered
  collection before it is serialized.
- Measure and parser code imports only `ALLOWED` in `tests/guards/test_inspector_pieces.py`.
- The runner image is pinned by digest. Staged measurer code is digested in `pipeline.yml`.
- No backward compatibility: `declares: measure`, `registry/profilers/`, `profile.yml` and
  `mendel profile` are removed, not aliased.
- Diagnostics are declared in `packages/comeni-core/src/comeni_core/diagnostics.yml` and emitted
  through `coded()`. Use the next free `MD03xx` and `MD06xx` codes, and check that file first.
- Registry changes go on a branch of `../comeni-registry` (the writable checkout). The
  `registry/` submodule pointer moves to that commit. Pushing either needs the operator.
- Tests: no bare pytest. The DB suites run through `make test`, one at a time, and reviewers run
  pure tests only.
- Every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Groovy and Python disagree on an edge value.** Examples: `round` at .5, `log2` of a power
   of two, a boundary that is `>=` against `>`. The agreement test (Task 7) runs the table check's
   cases through both.
2. **Re-routing for a measurement changes the original graph.** Adding a want must leave every
   existing node, edge and decision as it was (Task 6, `test_rerouting_keeps_the_graph`).
3. **An undetermined measurement at run time** (an empty genome, too few reads). The fallback
   value is used and recorded as the fallback, never a crash (Tasks 1 and 7).
4. **A run-time fact on a per-sample channel.** The join is by `meta`, so each sample gets its
   own value. A run-scoped genome joined with a per-sample measurement must not pair wrongly
   (Task 7, `test_join_is_by_meta`).
5. **A Nextflow `MEASURED` file forged in the results directory.** Wiener reads only the closed
   payload, with its own checks, and ignores names it did not expect (Task 9).

---

### Task 1: A stdlib inspection core, coverage, and the pipeline runner

**Files:**
- Modify: `packages/comeni-inspect/src/comeni_inspect/run.py`, `wire.py`, `harness.py`,
  `PROTOCOL.md`
- Create: `packages/comeni-inspect/src/comeni_inspect/core.py`, `measure_cli.py`
- Test: `packages/comeni-inspect/tests/test_core_stdlib.py`, `test_measure_cli.py`

**Interfaces:**
- Produces:
  - `core.Ref(id, version, path, decided)`, a frozen dataclass;
  - `core.inspect_streams(fmt: Ref, codec: Ref | None, measures: list[Ref], files: list[tuple[str, BinaryIO]], cap: int | None) -> dict`;
  - `core.parse_output(parser: Ref, stream: BinaryIO) -> dict`.

  Both return a plain report dict, the same shape as `wire.Report.model_dump(exclude_none=True)`.
  - `wire.Fact.coverage: Literal["head", "all"] | None`.
  - CLI `python -m comeni_inspect.measure_cli --format DIR --measure DIR... --codec DIR? FILE...`
    or `--parser DIR FILE`, which writes a report JSON to stdout.

- [x] **Step 1: Write the failing tests.**
  - `test_core_imports_only_stdlib`: run `python -I -c "import comeni_inspect.core"` in a
    subprocess with `sys.modules` checked. Assert that `pydantic` was not imported.
  - `test_coverage_all_when_uncapped`: inspect `single_150` with a cap larger than the file.
    Assert that `facts["read_length"]["coverage"] == "all"`.
  - `test_coverage_head_when_capped`: use a cap of 8 KiB. Assert that the coverage is `head`.
  - `test_cli_matches_server`: the CLI over `single_150` (with no cap) gives the same
    `read_length` value and evidence as `run.inspect` with a cap above the file size. Only
    `coverage` and `capped` may differ.
  - `test_parser_mode`: a parser piece in a `tmp_path` folder (`def parse(stream, decided)`
    returning `Value(29903, {...})`) gives `facts["genome_length"]["value"] == 29903`, with
    coverage `all`.
  - `test_parser_that_raises_is_unreadable`: the report has `unreadable` set and the exit
    status is 0.
- [x] **Step 2: Run** `uv run pytest packages/comeni-inspect -q`.
  Expected: the new tests FAIL with an ImportError on `core`.
- [x] **Step 3: Move the logic.** `_inspect` and its helpers move into `core.py`, working on
  `Ref` and plain dicts. `run.inspect` adapts `wire.Request` to `core` and validates the result
  into `wire.Report`. `cap=None` means unbounded (`Capped` is skipped). Coverage is `"head"` if
  any limit capped, and `"all"` otherwise. `outcome.py` and `records.py` are already stdlib.
- [x] **Step 4: Write `measure_cli.py`.** It is stdlib only: `argparse`, a piece directory's
  declaration read through a tiny YAML-free path, and `decided` passed as `--decided JSON`. The
  emitter passes everything on the command line, so the runner never parses YAML. It must
  never raise: any failure becomes an `unreadable` report.
- [x] **Step 5: Regenerate the golden reports.** Every report gains `coverage`. Use the
  `harness.run_case` one-liner from `registry/inspectors/README.md`, then read the diff: only
  `"coverage"` lines should be added.
- [x] **Step 6: Run** `uv run pytest packages/comeni-inspect registry/inspectors tests/registry/test_inspection_conformance.py -q`.
  Expected: PASS.
- [x] **Step 7: Commit:** `feat(inspect): a stdlib core, coverage, and a pipeline runner (#465)`.
  The golden reports are a registry change: carry them into Task 2's registry branch rather than
  committing them in the submodule. Here, commit the engine side only, and run the conformance
  test against the regenerated files in the working tree.

### Task 2: The `measurer` declaration, and the registry moved to `measurers/`

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/inspection.py` (`MeasurePiece` →
  `Measurer`), `declared/layered.py` (`_KIND_OF`, `DeclaredKind.MEASURERS`), `diagnostics.yml`
- Modify the callers: `mendel_api/services/inspect.py`, `services/measurers.py`,
  `services/gaps.py`, `stages/gathering.py`, `tests/registry/test_measurement_vocabulary.py`,
  `tests/guards/test_inspector_pieces.py` (piece paths)
- Registry branch `measurers` in `../comeni-registry`:
  - `git mv inspectors measurers`;
  - each `measure.yml` → `measurer.yml` with `declares: measurer`, `by: code`,
    `runs: [server, pipeline]`;
  - `registry.yml` layout `measurer: [measurers/measures/]`, `codec: [measurers/codecs/]`,
    `format: [measurers/formats/]`;
  - the README moved and reworded;
  - Task 1's goldens.
- Test: `packages/comeni-core/tests/declared/test_measurer.py`

**Interfaces:**
- Produces `Measurer` with these fields:
  - `id`, `version`, `measures`, `entry`, `needs`, `impl`;
  - `by: Literal["code", "tool"]`;
  - `record: Literal["sequence"] | None`;
  - `decided`;
  - `uses: ContractId | None`, `output: PortName | None`;
  - `runs: list[Literal["server", "pipeline"]]`, with at least one entry.

  `InspectionCatalogue.measurers: dict[str, Measurer]` replaces `.measures`.
  `Measurer.runs_on(where) -> bool`.
- The refusal codes are new, and checked by the catalogue against the registry:
  - `by: tool` with `server` in `runs`;
  - `by: code` without `record`;
  - `by: tool` with a `record`, or without `uses`/`output`;
  - `uses` not a contract in the stack, or `output` not one of its ports.

- [x] **Step 1: Write the failing tests.** One per refusal above, each asserting its code. Add
  `test_code_measurer_loads` (the registry's `read_length` loads with
  `runs == ["server", "pipeline"]`).
- [x] **Step 2: Run** `uv run pytest packages/comeni-core/tests/declared/test_measurer.py -q`.
  Expected: FAIL (`Measurer` does not exist).
- [x] **Step 3: Implement.** Rename everywhere; use `grep -rn "MeasurePiece\|\.measures\b\|DeclaredKind.MEASURES"` and leave no hit. `declares: measure` becomes an unknown kind (MD0011). The `uses`/`output` checks run where the catalogue is validated against the registry (`inspection.py` near line 193, which already checks `measures` against measurement ids). Pass the registry in if needed.
- [x] **Step 4: Move the registry.** Make the changes on the `measurers` branch of
  `../comeni-registry` (use `git -C`), commit there, then move the submodule to it:
  `git -C registry fetch ../../comeni-registry measurers && git -C registry checkout FETCH_HEAD`.
- [x] **Step 5: Run** `uv run pytest packages/comeni-core packages/comeni-inspect registry/measurers tests/registry tests/guards -q`.
  Expected: PASS.
- [x] **Step 6: Commit** the engine side and the submodule pointer:
  `feat(core): one measurer declaration (#465)`.

### Task 3: Profilers and `mendel profile` removed

**Files:**
- Delete: on the registry branch, `profilers/`, and the `contract: [... profilers/]` layout entry.
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/resolve_verbs.py` (drop the
  `profile` verb, `_profiling_goal` and the `profile.yml` writing), and the CLI parser where
  `profile` is registered.
- Modify: `mendel_api/services/measurers.py` (the index lists measurers only, with their
  `runs`, and `kind` goes); `mendel_api/services/registry.py:115` (its comment);
  `mendel_api/routes/authoring.py:348` (the `runs` literal becomes `server | pipeline`).
- Modify: the docs that name `mendel profile` (`grep -rln "mendel profile\|profile.yml" docs`).
- Test: the existing `mendel profile` tests are deleted. Write `tests/api/test_measurer_index.py`.

**Interfaces:**
- Produces `Measurer` in the index: `measurement`, `by` (`fastq@1.1.0 + read_length@1.0.0`, or
  `genome_length_fai@1.0.0 (nf-core/samtools/faidx@…)`), `runs: list[str]`, `trusted`.

- [x] **Step 1: Write the failing test.** `test_index_lists_runs`: with the registry,
  `read_length`'s entry has `runs == ["server", "pipeline"]`, and no entry has a `kind`.
- [x] **Step 2: Run it.** Expected: FAIL.
- [x] **Step 3: Implement the deletions and the index change.** Then run
  `grep -rn "profiling_goal\|profile\.yml\|\"profile\"" packages` and leave only unrelated hits
  (Nextflow `-profile` is unrelated).
- [x] **Step 4: Run** `uv run pytest tests/api/test_measurer_index.py packages/mendel-compiler -q`,
  then `make test` once. Expected: PASS.
- [x] **Step 5: Commit** (engine, and the registry branch with the submodule pointer):
  `refactor: profilers and mendel profile removed; measurers replace them (#465)`.

### Task 4: Coverage on facts, and `coverage: all` on decisions

**Files:**
- Modify:
  - `comeni_core/goal/profile.py` (`Measured.coverage`);
  - `goal/premise.py` (`PremiseRecord.coverage`, and the prose);
  - `mendel_resolver/premises.py` (carry it);
  - `mendel_resolver/rules/format.py` (`Decision.coverage: Literal["all"] | None`);
  - `rules/table.py` (premises filtered per decision);
  - `mendel_api/decision_models.py` with a new Alembic migration (an `observation.coverage`
    column, nullable);
  - `services/decisions.py` and `services/inspect.py` (store it and pass it on).
- Test: `packages/mendel-resolver/tests/rules/test_coverage.py`,
  `packages/comeni-core/tests/goal/test_premise_prose.py`, and
  `packages/mendel-api/tests/test_inspect_coverage.py` (DB).

**Interfaces:**
- Produces:
  - `Measured.coverage: Literal["head", "all"] | None = None`. It is only valid when the fact is
    measured (validator), and is excluded from the dump when `None`.
  - `PremiseRecord.coverage`, same type.
  - `PremiseRecord.prose()`: `"read_length is 150, measured on the first 4 MB by fastq@1.1.0 + read_length@1.0.0"` for `head`. For `all` the prose is unchanged.
  - `Decision.coverage`, dumped only when set.
  - `RuleTable._matching` treats a `head` premise as absent for a decision with
    `coverage: "all"`.

  The premises dict holds values. A parallel `premise_coverage: dict[str, str]` is passed on
  `ParamContext` and to `build_premises`'s result. Rule on the exact carrier when you read
  `premises.py`, and ledger it.

- [x] **Step 1: Write the failing tests.**
  - `test_head_premise_does_not_satisfy_coverage_all`: a decision with `coverage: all` and a
    row on `read_length >= 70`, a `head` premise of 150 → `value_for` is `None`.
  - `test_all_premise_satisfies`: the same with coverage `all` → it pins.
  - `test_asserted_premise_satisfies`: no coverage → it pins. An asserted fact is a person's
    word, so the rule treats it as complete. Ledger this as a ruling.
  - `test_prose_head`.
  - `test_coverage_stored` (DB): inspecting an uploaded capped file stores `head`, and the
    goal's `Measured` carries it.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement**, including the migration
  (`uv run alembic -c packages/mendel-api/alembic.ini revision -m "observation coverage"`, or
  follow the repo's migration command in `packages/mendel-api`).
- [x] **Step 4: Run** the pure tests, then `make test` once. Expected: PASS.
- [x] **Step 5: Commit:** `feat: facts record their coverage; decisions may require all of the data (#465)`.

### Task 5: Pipeline measurers as synthetic contracts, with a generated module

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/measure_steps.py`
- Modify: `mendel_resolver/layers.py` (add the synthetic contracts to the stack's registry after
  load); `mendel_compiler/emit.py` and `staging.py` (stage the runner and pieces, and write the
  generated module); `mendel_compiler/templates/measure.nf.j2` (new);
  `comeni_core/artifact/pipeline.py` (`Pipeline.measurers: list[StagedMeasurer]`, each with its
  digest)
- Test: `packages/mendel-resolver/tests/test_measure_steps.py`,
  `packages/mendel-compiler/tests/test_emit_measure.py`

**Interfaces:**
- Produces:
  - `measure_steps.contracts_for(catalogue, registry) -> list[ModuleContract]`, sorted by id.
    There are two shapes:
    - **One per format**, for its `by: code` measurers with `pipeline` in `runs`:
      - `id = f"comeni/measure/{fmt.id}@{fmt.version}"`, `process = f"MEASURE_{FMT}"`;
      - consumes `data` of the format's first `reads` type;
      - produces one port per measurer, `<measures>` of type `measurement.<measures>`.

      One step then reads the file once for every fact (Task 8).
    - **One per `by: tool` measurer:**
      - `id = f"comeni/measure/{m.id}@{m.version}"`, `process = f"MEASURE_{M_ID}"`;
      - consumes `data` of the tool's `output` port type;
      - produces `<measures>`.

    Both have `roles = ["measurement"]`, a scope following the consumed type, and no params. The
    `measurement` role is declared in vocabulary on the registry branch.
  - `StagedMeasurer(id, version, files: list[str], digest: str)`.
  - The template writes this process:

    ```nextflow
    process MEASURE_X {
      container '<IMAGE@digest>'
      input: tuple val(meta), path(data); path(runner)
      output: tuple val(meta), path("*.json"), emit: report   // every produced port binds to this one report
      script: "python3 -I runner/measure_cli.py <args> ${data} > ${meta.id}.json"
    }
    ```

    It publishes `measurements/<measures>/` through the existing `publishDir` path.
  - `RUNNER_IMAGE`, a constant in `emit.py`: `python:3.12-slim@sha256:…`. Get the digest with
    `docker buildx imagetools inspect python:3.12-slim`, and record the date in the comment.

- [x] **Step 1: Write the failing tests.**
  - `test_code_measurer_contract`: the `fastq` format → `comeni/measure/fastq@1.1.0`, consuming
    `fastq.reads` and producing `measurement.read_length`, `measurement.paired` and
    `measurement.quality_encoding`.
  - `test_tool_measurer_contract`: an overlay measurer using a fixture contract's `fai` port
    consumes that port's type.
  - `test_router_reaches_measurement`: with the synthetic contracts in, `route()` on want
    `measurement.read_length` with have `fastq.reads` gives one step.
  - `test_emit_stages_runner`: the emitted directory has `measurers/fastq/…` and the
    runner. `pipeline.yml` records their digest, and emitting twice is byte-identical.
  - `test_emit_measure_process`: `main.nf` contains `MEASURE_FASTQ` with the pinned image.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.** The staged runner is `comeni_inspect/{core,outcome,records,stream,measure_cli}.py`, copied from the installed package, plus the measurer folder and its format/codec. Their digest is over the sorted (path, sha256) pairs (`digest_of_directory`). `conformance.py` must accept the generated module: its ports match by construction. Add the measurer to conformance's "generated" path rather than skipping it.
- [x] **Step 4: Run** `uv run pytest packages/mendel-resolver packages/mendel-compiler -q`.
  Expected: PASS. The golden examples are unchanged because nothing wants a measurement yet.
- [x] **Step 5: Commit:** `feat: pipeline measurers route as generated steps (#465)`.

### Task 6: Run-time decisions in the resolver

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/at_run.py`
- Modify:
  - `resolve.py`, where `resolve()` gains a second route when facts are needed at run time;
  - `_resolve_param`, which gains a run-time branch between tier 3 and tier 2;
  - `comeni_core/plan/ir.py` (`ResolvedValue.at_run`);
  - `comeni_core/artifact/pipeline.py` (`Setting.at_run: AtRun | None`,
    `Channel.meta_at_run: list[MetaAtRun]`);
  - `artifact/materialise.py`;
  - `diagnostics.yml`.
- Test: `packages/mendel-resolver/tests/test_at_run.py`

**Interfaces:**
- Produces:
  - `AtRun`:
    - `fact: MeasurementId`, `measurer: str`;
    - `rule: str`, the decision key;
    - `rows: list[AtRunRow]`;
    - `fallback: ParamValue`, `fallback_why: Line`.
  - `AtRunRow`:
    - `when: str`, the row's condition on the run-time fact only, in the rule file's syntax
      (`">= 70"`, `reverse`), or `""` for a catch-all;
    - `then: ParamValue | None`;
    - `transform: list[TransformStep]`, for a `{fact:}` over a derived fact: its source fact and
      chain, flattened; empty for a literal.
  - `MetaAtRun(measurement, meta_key, from_node: NodeId)`.
  - `at_run.facts_needed(plan, registry, rules, premises, measurers) -> list[MeasurementId]`, sorted.
  - `at_run.decide(param, context) -> ResolvedValue | None`.
- When a decision is run-time:
  - it reads a fact `f` with no premise (and no `head` premise under `coverage: all`);
  - a pipeline measurer for `f` exists;
  - `f`'s measurement declares `describes: T` and `meta_key`;
  - `T` is an entry channel of the goal (`have`);
  - and the node is downstream of that channel along edges.

  The spec said "direct input or same-sample lineage". The plan narrows this to
  entry-channel-rooted lineage, which covers both. Ledger it.
- Refusals (new MD codes): rows reading two run-time facts; an `implementation` or `presence`
  decision whose fact is run-time-only. A fact that cannot reach the node is not refused: the
  decision falls to tier 2 or 4 as today, and the reason says why.
- Known facts are substituted into the rows. A row whose other conditions are false is dropped.
  A row whose `when` keeps no condition on `f` (a catch-all over the rest) keeps `when: ""`.
  Rows keep their original order and `hit` stays `first`. A `unique` decision with a possible
  overlap on `f` is refused as run-time (no one is there to ask) and falls to tier 4. Ledger it.
- `fallback`: the value `_resolve_param` gives with the run-time rows skipped (tier 2 default, or
  tier 4's answer), with its reason. The setting's `why`:
  - tier `DATA_PROFILED`, source `RESOLVER`;
  - reason `"decided at run time by {rule} from {fact} measured by {measurer}"`;
  - premise: the fact with origin `UNMEASURED` and `by` set to the measurer;
  - value: the fallback.

- [x] **Step 1: Write the failing tests.** Use an overlay: STAR genomegenerate with
  `sa_index_nbases`, the part 3 STAR rule, `genome_length` with `describes: genome.fasta` and
  `meta_key`, a fixture faidx contract, and a `genome_length_fai` measurer.
  - `test_unknown_genome_length_decides_at_run`: the setting has `at_run.fact == "genome_length"`
    and one row with the transform `[log2, divide 2, subtract 1, at_most 14, round]`. The IR has
    a faidx node and a `comeni/measure/genome_length_fai` node, and the channel for
    `genome.fasta` has `meta_at_run`.
  - `test_stated_genome_length_decides_at_build`: there is no measure node, and the value is 6
    as in part 3.
  - `test_rerouting_keeps_the_graph`: every node, edge and decision of the build without
    `at_run` is in the build with it, unchanged.
  - `test_two_run_time_facts_refused`: assert the code.
  - `test_unreachable_fact_falls_back`: `T` not an entry channel → tier 2, and the reason names
    why.
  - `test_unique_overlap_not_at_run`.
  - `test_same_goal_same_ir`: build twice, and the dumps are equal.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.** `resolve()` calls `route` once. If `facts_needed` is non-empty, it
  calls `route` again with `goal.want + [measurement.<f>…]`, then asserts the first plan's steps
  are a subset of the second's (by contract and inputs). The measurement output is a side want:
  check that `route` does not treat it as a final output that later code requires. Exclude it
  from `intent.want` in `pipeline.yml`.
- [x] **Step 4: Run** `uv run pytest packages/mendel-resolver packages/comeni-core -q`.
  Expected: PASS, and the golden examples are unchanged.
- [x] **Step 5: Commit:** `feat(resolver): settings decided at run time from a pipeline measurement (#217)`.

### Task 7: Emitting the run-time lookup

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_ext_scope`, the workflow's
  channel wiring), `templates/main.nf.j2`
- Create: `packages/mendel-compiler/src/mendel_compiler/groovy_lookup.py`
- Test: `packages/mendel-compiler/tests/test_groovy_lookup.py`,
  `tests/execution/test_at_run_agreement.py` (slow, needs Nextflow)

**Interfaces:**
- Produces:
  - `groovy_lookup.closure(at_run: AtRun, meta_key: str, template: NfTemplate | None) -> str`,
    a Groovy expression over `meta.<key>`, ending in the fallback;
  - `groovy_lookup.transform(steps, var) -> str`.

  The mapping:
  - `log2` → `(Math.log(x) / Math.log(2))`;
  - `round` → `Math.rint(x)`;
  - `at_most` → `Math.min(x, by)`, `at_least` → `Math.max(x, by)`;
  - add, subtract, multiply and divide → infix with `as double`;
  - an integer fact without `round` → `(x as long)`, truncation as the resolver's.

  Literals pass `substitutable()` or raise MD0201.
- The workflow wiring:
  - `ch_<channel>_measured = MEASURE_<ID>.out.report.map { meta, f -> [meta, new groovy.json.JsonSlurper().parse(f).facts?.get('<fact>')?.value] }`;
  - consumers of the described channel take
    `ch_<channel>.join(ch_<channel>_measured).map { meta, data, v -> [meta + [<key>: v], data] }`;
  - the measurer branch itself takes the raw channel;
  - a `null` value (undetermined) reaches the closure, which then gives the fallback.
- The run-time value is recorded: the closure is pure, so the workflow also writes
  `measurements/decided/<step>.<setting>.csv` through `collectFile`, holding `meta.id` and the
  value, computed with the same closure text. Sort before writing (`sort: true`).

- [x] **Step 1: Write the failing tests.**
  - `test_closure_rows_enum`: strandedness rows → `meta.strandedness == 'reverse' ? 2 : …` with
    the fallback last.
  - `test_closure_transform_star`: the exact text for the STAR chain.
  - `test_literal_not_substitutable_refused`: MD0201.
  - `test_emitted_star_pipeline`: an emitted overlay build contains the join, the closure in
    `withName: STAR_GENOMEGENERATE { ext.args = { "--genomeSAindexNbases ${…}" } }`, and the
    decided `collectFile`.
  - `test_join_is_by_meta`: the join is keyed on `meta` (first element), never `combine`, for a
    per-sample channel.
  - Slow `test_at_run_agreement`: generate one Nextflow script that evaluates each closure over
    every case from the table check's case generator. Use `rules/validate.py`'s case builder;
    export it if private. Include `null`, 29903, 3.1e9, exact powers of two and .5 points. Run
    `nextflow run`, parse the printed results, and compare them with the resolver's
    `RuleTable.value_for` (or the fallback) on the same cases. Assert the two are equal.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the pure tests, `uv run pytest tests/execution/test_at_run_agreement.py -q`
  (with Nextflow), and `make static`. Expected: PASS, and the Nextflow lint is clean on the
  emitted overlay pipeline.
- [x] **Step 5: Commit:** `feat(compiler): run-time settings emitted as a lookup over meta (#217)`.

### Task 8: Estimates confirmed in the pipeline

**Files:**
- Modify: `mendel_resolver/at_run.py` (`facts_to_confirm`), `resolve.py`, `pipeline.py`
  (`Pipeline.confirms: list[Confirm]`)
- Test: `packages/mendel-resolver/tests/test_confirm.py`

**Interfaces:**
- Produces:
  - `at_run.facts_to_confirm(ir_premises_used, premise_coverage, measurers, have) -> list[MeasurementId]`:
    premises with `head` coverage that a selection, presence or setting read, where a
    `by: code` pipeline measurer exists and its input type is in `have`.
  - `Confirm(measurement, estimate: ParamValue, from_node: NodeId, used_by: list[str])`, where
    `used_by` holds sorted keys like `selection:align` and `setting:quant.strandedness`.

- [x] **Step 1: Write the failing tests.**
  - `test_head_read_length_confirmed`: a goal with `read_length` 150 at `head` coverage → a
    `MEASURE_FASTQ` node, with a `Confirm` naming the aligner selection.
  - `test_asserted_not_confirmed`: a said fact → no node.
  - `test_all_not_confirmed`: coverage `all` → no node.
  - `test_one_step_per_input`: two head facts on `fastq.reads` (`read_length`, `paired`) → one
    `MEASURE_FASTQ` node (Task 5's per-format contract), with both of its ports wired.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement**, through the same second route as Task 6.
- [x] **Step 4: Run** the pure tests, then `make test` once. Expected: PASS. The golden examples
  change only if their goals carry `head` facts. They state `said` facts, so they should not
  change: check this.
- [x] **Step 5: Commit:** `feat(resolver): estimates are confirmed on all the data in the run (#465)`.

### Task 9: Wiener reads the run's measurements

**Files:**
- Modify: `packages/wiener-core/src/wiener_core/events.py` (`EventKind.MEASURED`,
  `Measurement` payload, outside `FROM_NEXTFLOW`), `state.py` (fold), `wiener-api` completion
  handling (find where `COMPLETED` is admitted, then read `results/measurements/`),
  `services/projection.py`
- Test: `packages/wiener-core/tests/test_measured_fold.py`,
  `packages/wiener-api/tests/test_measured_ingest.py` (DB),
  `packages/wiener-api/tests/test_projection_disagreement.py`

**Interfaces:**
- Produces:
  - `RunEvent.measured: Measured | None`, where `Measured` (Wiener's own model) is
    `measurement: str`, `sample: LabString`, `value: int | float | bool | str | None`,
    `undetermined: str | None`, `coverage: "all"`, `by: list[str]`,
    `decided: DecidedValue | None` (step, setting, value).
  - Fold: `RunState.measured: list[Measured]`, sorted by `(measurement, sample)`.
  - Projection: `RunProjection.measured: list[MeasuredView]`, where each view has
    `status: confirmed | disagrees | at_run | undetermined`, `estimate`, and `used_by` from
    `pipeline.yml`'s `confirms`/`at_run`.
- Reading the results is closed:
  - only files at `measurements/<id>/<name>.json` and `measurements/decided/<step>.<setting>.csv`;
  - `<id>` must be a measurement in the artifact's `confirms` or `at_run`;
  - payloads over 64 KiB, or that fail validation, are skipped with a logged reason.

- [x] **Step 1: Write the failing tests.**
  - The fold keeps and sorts facts.
  - A Nextflow-authored `MEASURED` is refused (not `FROM_NEXTFLOW`).
  - Ingest reads a fixture results directory. An unexpected id is ignored, and a 100 KiB file
    is skipped.
  - In the projection, 150 against 150 is `confirmed`, and 150 against 100 is `disagrees`, with
    `used_by == ["selection:align"]`.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the pure tests, then `make test` once. Expected: PASS.
- [x] **Step 5: Commit:** `feat(wiener): the run's measurements, confirmed or disagreeing (#465)`.

### Task 10: The step card and the run page

**Files:**
- Modify: the API schemas that expose `Setting` and the run projection (regenerate with
  `make client`); the frontend step card's setting row (find it with
  `grep -rln "for_value\|axis_reason" frontend/src/components`); the run view (`frontend/src/…/Run*`)
- Test: vitest beside each component.

- [x] **Step 1: Write the failing vitest tests.**
  - `StepSetting`, with `at_run`, shows "Decided at run time", the rule, the measurer, the
    outcome rows (or the transform as `log2 → ÷ 2 → − 1 → at most 14 → round`) and the fallback.
  - The run page's "Measured in this run" lists each fact with its status. A `disagrees` row
    shows the estimate, the measured value and the linked settings or selections.
- [x] **Step 2: Run** `cd frontend && npx vitest run <files>`. Expected: FAIL.
- [x] **Step 3: Implement**, using the existing components' patterns and the voice guide's
  words.
- [x] **Step 4: Run** `npx vitest run && npx tsc -b`. Expected: PASS.
- [x] **Step 5: Commit:** `feat(frontend): run-time settings and measured facts shown (#217, #465)`.

### Task 11: The registry demo (samtools faidx, the fai parser, STAR)

**Files** (the registry branch `measurers`):
- `tools/nf-core/samtools/faidx/` (imported with `comeni-vendor` or the forge's import path,
  pinned; its contract describes the optional `fai` input and `get_sizes`);
- `measurers/measures/genome_length_fai/measurer.yml` and `piece/fai.py`, with tests on a
  fixture `.fai`;
- `vocabulary/measurements/genome_length.yml` (drop `assertion_only`, add `describes: genome.fasta` and `meta_key: genome_length`);
- STAR genomegenerate's `sa_index_nbases` param and the part 3 rule file, deferred from part 3;
- `vocabulary/roles/measurement.yml`.

Engine test: `packages/mendel-compiler/tests/test_star_index_at_run.py`, and slow
`tests/execution/test_star_index_at_run_gate.py`.

- [x] **Step 1: Write the failing tests.**
  - `test_star_index_at_run`: a goal shaped like `examples/rnaseq.yml` without `genome_length`,
    built against the registry. It has `SAMTOOLS_FAIDX`, `MEASURE_GENOME_LENGTH_FAI`, the join
    and the closure.
  - Slow gate: run on `workspace/` test data, or a vendored SARS-CoV-2 fixture of 29,903 bp,
    as far as STAR genomegenerate. Assert that `.command.sh` contains
    `--genomeSAindexNbases 6` and that `results/measurements/genome_length/*.json` has 29903.
  - `fai.py`'s tests: the sum of column 2; an empty file is undetermined; a malformed line is
    undetermined, and the test says which line.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.** Do the registry commits on the branch, then move the submodule.
- [x] **Step 4: Run** the pure tests, the gate test, `make static` and `make verify`. Expected:
  PASS.
- [x] **Step 5: Commit:** `feat: STAR's index sized from the genome measured in the run (#217, #465)`.

### Task 12: Documentation and records

**Files:**
- `docs/reference/registry/measurer-schema.md` (new; replaces the measure section of the
  inspector docs);
- `rule-schema.md` (`coverage`, and "Decided at run time");
- `docs/explanation/` (where facts come from: one table of measurer × runner);
- `CHANGELOG.md` (by package);
- the journal `docs/notes/journal/2026-11-10-measurers.md`, and `now.md`.

Close #465 and #217 with their commits.

- [x] **Step 1:** Write the pages, then run `make check` (doc sizes and links). Expected: PASS.
- [x] **Step 2:** Tick this plan and record its deviations.
- [x] **Step 3: Commit:** `docs: measurers and run-time decisions (#465, #217)`.

## Deviations

- **Task 1.** Codecs take a byte stream (`open(stream)`), not bytes, so the pipeline never holds a
  whole file in memory. `FileHead.whole` was added, because the browser sends only the first 4 MB
  and an uncapped head is not the whole file. Coverage is `all` only when every file was read to
  its end: a cut gzip, a stop at a malformed record or a pair's unread tail is `head` (review). A
  parser's report is keyed by the measurer id. Deferred: an uncompressed whole file cut mid-record
  still reads `all`, because the format ends quietly on a partial record.
- **Task 2.** MD0326 (shape) refuses at load. MD0327 (tool or port missing) drops the measurer, as
  MD0317 does, after the registry is assembled. The registry branch lives in the worktree
  `../comeni-registry-measurers`. `runs` is canonical (sorted, once each).
- **Task 3.** The index tests stayed in `packages/mendel-api/tests/authoring/samples/test_measurers.py`.
  `tests/emit/test_profiling.py` and `make profile` went with the verb. `fires_on: profile` was
  dropped from every diagnostic.
- **Task 4.** Coverage rides on `Evidence` (a `Coverage` enum) and on the session `Fact` /
  `InspectedFact`, not on a new observation column; the stored shapes moved by identity
  upgraders (`d4a7c2e9b815_measured_coverage`). An asserted premise satisfies `coverage: all`. A
  derived fact inherits `head`. The prose reads "measured on part of the data". The browser sends
  `sizes`. `unapplied_implementation` honours `coverage: all`, so a miss is asked (review).
  Ruling: a `head` fact read only by `coverage: all` implementation or presence decisions is not
  reopened as a gap; that decision misses and is asked at tier 4, and a param decision is decided
  at run time from Task 6.
- **Task 5.** Generated contracts join only the routing registry (`Layers.routing`), never the
  loaded one, so the docs, conformance and the registry browser list what a layer declares. No
  `Pipeline.measurers` field: the contract's provenance names its pieces, the layer digest pins
  them, and the stamp records each staged file. The runner is a Nextflow module binary, run
  through `python3 -I` so a zip that drops the mode bit cannot break it (review). Facts publish
  to `{outdir}/<process>/<sample>.measured.json`. The pure compiler finds the runner through
  `importlib.metadata`, never importing the impure inspector.
- **Task 6.** Implementation and presence decisions waiting on a measurable fact are not refused;
  they stay questions. A `hit: unique` decision is never run-time. A run-time fact joins `meta`
  under its own id, so only `describes` is needed. A person's answer is never displaced; the
  measuring step is read off the graph (review).
- **Task 7.** The join fails on a mismatch instead of dropping a sample with exit 0, and numbers
  compare as doubles (review). The agreement test lives in `tests/emit/`. MD0330.
- **Task 8.** Confirmations come from the premises recorded on selections and settings; a route
  moved only by them leaves the build as it was.
- **Task 9.** Measurements are Wiener's own events in the record, and the view is derived on
  read; the run table gained no columns. A malformed report can never lose the run's end, and
  `collect` read a generator twice and dropped every decided value (both found by review).
- **Task 10.** The API renders the lookup's rows as lines. The token test reads `#217` as a
  colour, so frontend files write "issue 217". Browser check deferred to the end of parts 2–5.
- **Task 11.** Discovery of run-time settings asks nobody, so the real resolver is asked once.
  An omittable setting's fallback is the tool's own value, not a question. faidx's `.fai` is
  declared always written: the router cannot switch an optional input off to meet
  `{given.fai: absent}`. A fact only settings read and the pipeline can measure is not asked as a
  gap. `ir_of` decides run-time settings for kept drafts. The conversation offers faidx and the
  measuring step as steps of their own.
- **Task 12.** #465 and #217 stay open until the branch merges; deferred minors are in one
  checklist issue.
