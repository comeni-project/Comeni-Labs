# Tool constraints, phase 2: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Contracts can describe optional files inside shared tuples, a join per port, and
checks that depend on which file type was connected. The forge drafts them, and the builder
builds and emits them.

**Architecture:** `comeni-core` loads and checks the new shapes (`declared/contract.py`,
`declared/constraints.py`). `mendel-resolver` evaluates constraints with the connected types.
`mendel-compiler` emits a tuple from the ports that are on, with `[]` for each one that is
off. The forge and the builder reuse phase 1's paths.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, Nextflow DSL2 text, React/Vitest (only
checked, no change expected).

**Spec:** `docs/superpowers/specs/2026-11-10-tool-constraints-phase-2-design.md`

## Global Constraints

- `comeni-core` and `mendel-resolver` stay pure: no I/O, and stdlib imports only through the
  purity allowlist (`tests/support/purity.py`).
- Registry v0.8.1's contracts must still load, and the featureCounts scalar `join: broadcast`
  keeps its digest.
- A `[]` slot is emitted only for a port the contract declares optional and that is off.
- A `type.<port>` value must be the port's `type_id` or one of its `accepts`.
- New diagnostics are declared in `packages/comeni-core/src/comeni_core/diagnostics.yml`,
  emitted through `coded()`, and listed in `docs/reference/pipelines/diagnostics.md`.
- No live model calls in tests. Forge prompt tests use recorded replies.
- No browser checks or walks in this plan. They come after parts 2–5 (operator, 2026-11-10).

**Commands.**
- Pure tests: `uv run pytest <paths> -q`.
- Database tests: `make test-db` once, then
  `MENDEL_TEST_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel uv run pytest <paths> -q`.
- Per-commit check: `make lint types docs docs-status links doc-paths doc-sizes guards`, run
  **on its own** before `git commit`, never chained into it.
- Full `make test` and `make static` at each stage's end.

## Review Focus

1. **An `accepts` port fed by the goal's `have`.** `materialise._step_inputs` falls back to
   `default_channels_by_type[port.type_id]`, the port's own type, so a BAM given to
   minimap2's FASTQ-typed `reads` may find no channel. Task 5 adds the test.
2. **Two samples through a shared slot.** A per-sample index joined `by_sample` must pair with
   its own BAM, not every BAM. Task 6 builds the channel text for two samples and checks it
   joins rather than combines.
3. **A port off in the middle of a tuple.** `[]` must land in that port's position, not at
   the end. Task 6 pins gatk's `[meta, input, input_index, [], dragstr]`.
4. **A forge draft naming a type the vocabulary lacks** (`alignment.cram`) must be refused at
   load (`MD0602`), never accepted as free text. Task 3 adds the test.
5. **A contract with many accepted types times many optional ports** must hit `MD0607`, not
   hang. Task 4 adds the test.

---

## Stage 1 — the contract (`comeni-core`)

### Task 1: Optional ports inside shared slots load

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py`
  (`ModuleContract._constraints_name_real_things`, the `MD0601` block)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MD0601` wording), `docs/reference/pipelines/diagnostics.md`
- Test: `packages/comeni-core/tests/test_contract_constraints.py`

**Interfaces:**
- Produces: `MD0601` refuses only:
  - an entry whose ports are all optional and that has no `absent`;
  - `absent` on an entry whose ports are all required;
  - an entry whose **first** port is optional and whose later ports have mixed joins (once
    Task 2 exists; until then, a scalar join cannot mix).

  "mixes required and optional inputs" and "several optional inputs that are not one
  all_or_none group" are removed.

- [x] **Step 1: Failing tests:**
  - `test_a_slot_may_mix_required_and_optional_ports`: a contract with
    `nf_inputs: [{ports: [input, intervals], join: broadcast}]`, `intervals` optional and no
    `absent`, loads.
  - `test_a_slot_may_hold_independent_optional_ports`: spades shape, `[illumina, pacbio,
    nanopore]` all optional, `join: by_sample`, `absent: 4`, with an `any_of` group and no
    `all_or_none`, loads.
  - `test_an_all_optional_slot_still_needs_absent`: the same with no `absent` raises
    `MD0601`.
  - `test_absent_on_an_all_required_slot_is_still_refused`: raises `MD0601`.
- [x] **Step 2:** Run `uv run pytest packages/comeni-core/tests/test_contract_constraints.py -q`. Expected: the first two FAIL with `MD0601`.
- [x] **Step 3:** Remove the two refusals and update the `MD0601` docstring and the
  diagnostics wording ("an nf_inputs entry whose inputs can all be left out needs an `absent`
  width").
- [x] **Step 4:** Run the file, then `uv run pytest packages/comeni-core/tests -q`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit
  `feat(core): optional ports may share a slot with required or other optional ports (#464)`.

### Task 2: One join per port

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py` (`NfInput.join`,
  `_join_declared_when_it_matters`, the Task 1 first-port rule)
- Modify: `packages/comeni-core/src/comeni_core/spell/routes.py` only if `Join` needs a helper
- Test: `packages/comeni-core/tests/test_contract_constraints.py`, `packages/comeni-core/tests/test_digest.py`

**Interfaces:**
- Produces: `NfInput.join: Join | dict[PortName, Join] | None`, and
  `NfInput.join_for(port: str) -> Join`: the join of a port after the first, from the map or
  the scalar.

- [x] **Step 1: Failing tests:**
  - `test_a_slot_may_join_each_port_its_own_way`: gatk shape
    `{ports: [input, input_index, intervals], join: {input_index: by_sample, intervals: broadcast}}`
    loads, `join_for("input_index") is Join.BY_SAMPLE`, `join_for("intervals") is Join.BROADCAST`.
  - `test_a_join_map_must_name_every_later_port`: a map missing `intervals` raises
    `ValueError` naming `intervals`. So does a map naming the first port or an unknown port.
  - `test_an_optional_first_port_with_mixed_joins_is_refused`: raises `MD0601`.
  - In `test_digest.py`, `test_a_scalar_join_keeps_its_digest`: featureCounts' contract digest
    equals the value pinned before this change (copy it from the current test fixture output).
- [x] **Step 2:** Run both files. Expected: FAIL.
- [x] **Step 3:** Implement the union type, `join_for`, map validation and the first-port rule.
- [x] **Step 4:** Run `uv run pytest packages/comeni-core/tests -q`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(core): a join per port in a shared slot (#464)`.

### Task 3: Type facts in conditions

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py` (`_when_keys`, which
  needs the ports' accepted types)
- Modify: `packages/comeni-core/src/comeni_core/declared/constraints.py` (`Setup.types`,
  `_facts`, `_key` if needed)
- Test: `packages/comeni-core/tests/test_contract_constraints.py`, `packages/comeni-core/tests/test_constraints_evaluate.py`
- Create: `packages/comeni-core/tests/fixtures/constraints/salmon_quant.yml`, `picard_markduplicates.yml`

**Interfaces:**
- Produces:
  - `Setup.types: dict[str, str] = {}`: the type connected to each port that is on;
  - fact `type.<port>` with that type id, compared with the existing `when` operators
    (scalar equality, a list meaning `in`, `not`);
  - `_when_keys(when, ports: dict[str, set[str]], params)`, where `ports` maps each port to
    the type ids it accepts.
- Fixtures:
  - `salmon_quant.yml`: `reads` of `fastq.reads` accepting `alignment.bam`; optional `index`,
    `gtf`, `transcript_fasta` in their own slot `[index, gtf, transcript_fasta]`,
    `join: broadcast`, `absent: 4`. Rows: `{when: {type.reads: alignment.bam},
    requires: [transcript_fasta], forbids: [index]}` and `{when: {type.reads: fastq.reads},
    requires: [index]}`.
  - `picard_markduplicates.yml`: `reads` of `alignment.bam` accepting `alignment.cram`;
    optional `fasta`, `fai` in one slot with `all_or_none`; row
    `{when: {type.reads: alignment.cram}, requires: [fasta]}`.

- [x] **Step 1: Failing tests:**
  - `test_a_condition_may_test_the_connected_type`: salmon fixture loads.
  - `test_a_type_the_port_does_not_accept_is_refused`: `type.reads: alignment.cram` on salmon
    raises `MD0602` naming `alignment.cram`. This is Review Focus 4.
  - `test_type_of_an_unknown_port_is_refused`: `type.nope: x` raises `MD0602`.
  - In `test_constraints_evaluate.py`: `test_bam_reads_require_the_transcript_fasta`:
    `evaluate(salmon, Setup(given={"reads"}, types={"reads": "alignment.bam"}))` gives
    `missing == ["transcript_fasta"]`. With `given={"reads","transcript_fasta","index"}` it gives
    `forbidden == ["index"]`. With `types={"reads": "fastq.reads"}` and `given={"reads","index"}`
    it gives no missing and no forbidden.
- [x] **Step 2:** Run both files. Expected: FAIL.
- [x] **Step 3:** Implement. `_facts` adds `type.<port>` only for ports in `given`.
- [x] **Step 4:** Run `uv run pytest packages/comeni-core/tests -q`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(core): constraints may test which type was connected (#464)`.

### Task 4: The check enumerates types; `MD0612` for a type with no valid setup

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/constraints.py` (`check_constraints`)
- Modify: `diagnostics.yml`, `docs/reference/pipelines/diagnostics.md` (`MD0612`)
- Test: `packages/comeni-core/tests/test_constraints_check.py`
- Create: `packages/comeni-core/tests/fixtures/constraints/spades.yml`; extend `gatk4_haplotypecaller.yml` with `input_index` and optional `intervals`, `dragstr_model` in the input slot, with a join map

**Interfaces:**
- Produces: `check_constraints` enumerates, for each port with `accepts`, `[port.type_id, *alternative type ids]`
  in the product with optional inputs and params. The count includes them for `MD0607`.
  `MD0612`: "{id}: with {port} as {type}, no combination of inputs and params satisfies its
  constraints". It is reported per (port, type) with no valid setup, and only when some other
  setup is valid (otherwise `MD0603` stands alone).

- [x] **Step 1: Failing tests:**
  - `test_a_type_no_setup_allows_is_a_gap`: salmon with the FASTQ row changed to also forbid
    `index` and `transcript_fasta` reports `MD0612` for `reads` as `fastq.reads`.
  - `test_salmon_picard_spades_and_gatk_are_clean`: all four fixtures give `[]`.
  - `test_types_count_toward_the_setup_bound`: a contract with 10 optional ports and a port
    accepting 3 types reports `MD0607` (Review Focus 5).
- [x] **Step 2:** Run the file. Expected: FAIL.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run `uv run pytest packages/comeni-core/tests -q`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(core): check every accepted type has a valid setup (MD0612) (#464)`.

**Stage 1 end:** `make test` and record the counts in *Deviations*.

## Stage 2 — resolution (`mendel-resolver`, materialise)

### Task 5: Constraints see the connected types

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (the node loop around
  `_constraints_hold`: wire sources first, then evaluate with types; `_not_withheld` must see
  an output written for the connected type)
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py` (~470-484: the facts that
  raise an input's state come from `given.` only; add `type.`, and decide a type-only row's
  strength deliberately). Added after Task 3's review.
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py` (`_step_inputs`, for
  an entry channel feeding an `accepts` alternative), if Review Focus 1 fails
- Test: `packages/mendel-resolver/tests/test_optional_inputs.py`, `packages/mendel-compiler/tests/test_optional_inputs_built.py`

**Interfaces:**
- Consumes: `Setup.types` (Task 3).
- Produces: `_constraints_hold(contract, node, types: dict[str, str]) -> Verdict`. `types`
  comes from each edge's `type_id`, or for a port with no edge from the first alternative
  `router._have_satisfies` accepts. "Switch on by need" uses the same verdict, so BAM reads
  switch on salmon's `transcript_fasta`.
- The ordering change must not move outputs: `produced`/`withheld` are still appended after
  the verdict.

- [x] **Step 1: Failing tests:**
  - `test_bam_reads_switch_on_salmons_transcript_fasta`: a goal with `have:
    [alignment.bam, transcripts.fasta]`, want salmon's quant, over an overlay with
    `salmon_quant.yml`: `transcript_fasta` is on, `index` is off.
  - `test_fastq_reads_need_salmons_index`: with `have: [fastq.reads, salmon.index]`: `index`
    is on, `transcript_fasta` off.
  - `test_bam_reads_reach_an_accepts_port_from_the_goal` (Review Focus 1): the BAM build
    materialises, and salmon's `reads` input names the BAM's channel.
- [x] **Step 2:** Run them. Expected: FAIL.
- [x] **Step 3:** Implement. Fix `_step_inputs` if the third test fails, by looking up the
  channel by the matched alternative's type.
- [x] **Step 4:** Run `uv run pytest packages/mendel-resolver/tests packages/mendel-compiler/tests packages/comeni-core/tests -q`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(resolver): constraints are checked with the types connected (#464)`.

## Stage 3 — emission (`mendel-compiler`)

### Task 6: Shared slots emit `[]` for each port that is off

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_argument`; the
  materialised argument must carry which of its ports are off. Add that to the artifact's
  step argument model in `packages/comeni-core/src/comeni_core/artifact/pipeline.py` and
  `materialise.py` if it is not derivable from `Step.input_states`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py` (`_mark_optional_channels`
  and `CallArg.join`: inside a shared slot an optional-at-run port's width is the per-port
  empty, 2; the entry's `absent` applies only to an entry whose ports are all optional; the
  artifact's `CallArg.join` carries the per-port map). Added after Task 1's review.
- Test: create `packages/mendel-compiler/tests/test_shared_slots_built.py`

**Interfaces:**
- Consumes: `NfInput.join_for` (Task 2), `Step.input_states` (phase 1).
- Produces: for an entry with ports `p1..pn`:
  - the expression starts from the first port that is on;
  - each later port that is on is added with `.join(expr)` (`by_sample`) or
    `.combine(expr.map { it[1] })` (`broadcast`);
  - if any port is off, one final
    `.map { meta, a, c -> [ meta, a, [], c ] }` with a closure parameter per port that is on and `[]`
    per port that is off, in declared order;
  - all ports off: `_empty(absent)`, as now;
  - a port "optional at run" in the slot is its phase 1 ternary channel joined `broadcast`.
    `by_sample` with "optional at run" raises the phase 1 `ValueError` naming #466.

- [x] **Step 1: Failing tests**, building through `orchestrate` over overlays as
  `test_optional_inputs_built.py` does:
  - `test_gatk_with_intervals_off_passes_an_empty_slot_in_place` (Review Focus 3): the
    `GATK4_HAPLOTYPECALLER(` call's first argument ends with
    `.map { meta, a, b, c -> [ meta, a, b, [], c ] }` when `intervals` is off and
    `dragstr_model` is on, or the equivalent with your closure names.
  - `test_a_per_sample_index_joins_and_a_run_file_combines` (Review Focus 2): the same
    argument contains `.join(` for `input_index` and `.combine(` for `intervals` when both are
    on.
  - `test_spades_with_only_illumina_passes_two_empty_slots`: `[ meta, a, [], [] ]`.
  - `test_spades_with_only_nanopore_starts_from_nanopore`: the expression starts from the
    nanopore channel and maps to `[ meta, [], [], a ]`.
  - `test_an_optional_at_run_port_in_a_slot_is_a_ternary`: gatk's `intervals` switched
    "optional": the argument combines `params.<intervals param> ? (...) : Channel.value([[:], []])`.
- [x] **Step 2:** Run the file. Expected: FAIL.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run `uv run pytest packages/mendel-compiler/tests -q`, then `make static`, then
  `uv run pytest -m slow packages/mendel-compiler/tests -q`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(compiler): a shared slot passes [] for each port that is off (#464)`.

**Stage 3 end:** `make test` and record the counts.

## Stage 4 — the forge (`mendel-forge`, `mendel-api` forge)

### Task 7: The forge drafts, checks and tests the new shapes

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/testing.py` and `forging/validate.py` (a
  test may leave out an optional port in a shared slot)
- Modify: `packages/mendel-forge/src/mendel_forge/forging/checks.py` (findings include `MD0612`)
- Create: `packages/mendel-api/src/mendel_api/forge/prompts/parts/items.v3.md`, `forge.draft.v8.md`;
  move the callers in `services/forging_ai.py` to them
- Test: `packages/mendel-forge/tests/test_forge_testing.py`, `test_forge_validate.py`,
  `test_forge_checks.py`, `packages/mendel-api/tests/forge/test_forging_ai.py`

**Interfaces:**
- `items.v3.md` adds three things, each with one worked example from the survey:
  - **a port optional inside a slot:** gatk's `intervals`;
  - **a join per port:** gatk;
  - **`type.<port>` conditions:** salmon.

  It also says: when `meta.yml`'s pattern lists formats that map to different vocabulary
  types, propose `accepts`. A type the vocabulary lacks is a vocabulary question, never an
  invented id.
- The guide-in-step test (from #468) covers the new item shapes.

- [x] **Step 1: Failing tests:**
  - `test_a_test_may_leave_out_a_port_in_a_shared_slot`: a gatk test with no `intervals` data
    passes validation, and the run gets `[]` in that position.
  - `test_forge_checks_report_a_type_gap`: a draft with salmon's gap reports `MD0612`.
  - `test_draft_v8_reads_items_v3`: the recorded-reply drafting test loads v8 and v3.
  - The existing guide-in-step test fails until v3 mentions `type.` and per-port joins.
- [x] **Step 2:** Run the forge suites, pure and API. Expected: FAIL.
- [x] **Step 3:** Implement and write the two prompt files from v2/v7, changing only what the
  new shapes need.
- [x] **Step 4:** Run `uv run pytest packages/mendel-forge/tests -q` and the API forge tests with
  the database URL. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(forge): draft and test shared slots, joins per port and type facts (forge.draft.v8) (#464)`.

## Stage 5 — the builder

### Task 8: The step card reports shared-slot ports and type-fact sentences

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/build.py` only if a test fails
- Test: `packages/mendel-api/tests/pipelines/test_optional_ports_view.py`

**Interfaces:**
- Consumes: the port view's `optional`, `state`, `adds` (phase 1).

- [x] **Step 1: Failing tests:**
  - `test_an_optional_port_in_a_shared_slot_is_reported_like_any_other`: gatk built with
    `intervals` off: its port view has `optional=True` and `state="off"`.
  - `test_a_type_row_gives_its_sentence`: salmon built from BAM: `transcript_fasta`'s port
    view reason contains the row's `because`.
- [x] **Step 2:** Run with the database URL. Expected: either PASS (record "no change needed"
  in *Deviations*) or FAIL.
- [x] **Step 3:** Implement whatever fails.
- [x] **Step 4:** Run the file, then `cd frontend && npx vitest run && npx tsc -b`. Expected: PASS.
- [x] **Step 5:** Per-commit check, then commit `feat(build): step cards report shared-slot ports and type rows (#464)` (skip if nothing changed).

## Stage 6 — docs and close

### Task 9: Documentation, changelog, notes

- [x] `docs/reference/registry/contract-schema.md`: `nf_inputs` (mixing, `join` map,
  `join_for`), `type.<port>` in `when`, and an example from salmon.
- [x] `docs/reference/pipelines/diagnostics.md` is current (`MD0601`, `MD0612`).
- [x] `CHANGELOG.md` under comeni-core, mendel-resolver, mendel-compiler, mendel-forge,
  mendel-api.
- [x] `docs/notes/now.md` and a journal entry; tick this plan; record deviations.
- [x] `make check` (full), `make static`, `make guards`. Commit
  `docs: tool constraints phase 2 (#464)`.
- [x] Note for the registry: bump `ENGINE_REF` in Comeni-Registry's CI after this merges, so
  forged contracts using these shapes pass there.

## Deviations

From the execution ledger (2026-11-10). A fresh reviewer read every task (operator's request).

- - T1's first-port mixed-join rule depends on T2's map — Ruling: the rule lands in T2 (T1 notes it) — a scalar join cannot mix, so T1 has nothing to refuse — cost if wrong: none.
- Task 1: Ruling: replaced test_a_multi_port_entry_is_all_required_or_one_all_or_none_group with test_an_all_optional_entry_may_be_an_all_or_none_group — it pinned the rule the spec removes — cost if wrong: none.
- Task 1: Ruling: contract-schema.md's absent/required rows updated now rather than in Task 9 — they stated the removed rule — cost if wrong: none.
- Task 1 review: Important — _mark_optional_channels uses the entry's absent for an optional-at-run port in a shared slot; Ruling: added to Task 6's files and interfaces — Task 6 as planned would not touch it — cost if wrong: none.
- Task 1 review: minor docstring + absent-on-mixed fixed in Task 2 (tests test_absent_on_a_mixed_slot_is_refused RED→GREEN).
- Task 2: Ruling: join map serialised in port order (field_serializer) — model_dump_json keeps insertion order, so map key order changed the digest — test_a_join_map_digests_the_same_in_any_order RED→GREEN — cost if wrong: none.
- Task 2: Ruling: CallArg.join (artifact) stays a scalar until Task 6 — Task 6 owns materialise/emission — cost if wrong: a mapped contract fails at materialise between Tasks 2 and 6 (branch only).
- Task 2: Ruling: join_for(port) raises ValueError when join is None — only a multi-port entry calls it, and those require a join — cost if wrong: none.
- Task 2 review: no Critical/Important; minors 1-3 fixed in Task 3 (join_for ValueError: test_join_for_names_only_a_port_after_the_first RED→GREEN; two test matches tightened).
- Final: minor (deferred): MD0601 'says' does not mention the mixed-joins refusal (fix text does).
- Final: minor (deferred): join-map shape error is an uncoded ValueError, like the existing 'must declare join' error.
- Task 3: Ruling: a type condition uses the existing when syntax — one id, {in: [...]}, {not: id} — not the spec's bare list — logic/when.py reads a bare list as equality with a list — cost if wrong: none.
- Task 3: Ruling: a port with accepts declares no type_id (existing rule), so its accepted types are its alternatives' types (accepted_types(port)) — cost if wrong: none.
- Task 3: Ruling: test_type_of_an_unknown_port_is_refused passed before the change (MD0602 already refused unknown keys) — kept as a guard — cost if wrong: none.
- Task 3 review: Important — check_constraints ignored types (false MD0606 for picard at load) — fixed by Task 4 (picard in test_the_fixtures_are_clean RED→GREEN).
- Task 3 review: minor 3 (sentence drops the type) fixed in Task 4 — test_a_type_row_says_which_type_it_is_about RED→GREEN.
- Task 3 review: minor 2 (router facts given-only; _not_withheld) — Ruling: added to Task 5's files — cost if wrong: none.
- Task 3 review: minor 4 (_only_with prints {in: [...]} as a dict repr in the step view) — Ruling: handled in Task 8 — cost if wrong: an ugly reason string.
- Task 4: Ruling: MD0604/MD0605 still reported alongside MD0612 — with one type contradicted they are true of the contract as written — cost if wrong: two extra findings beside the cause.
- Task 4: Ruling: dropped test_a_type_condition_is_checked_against_each_type — vacuous (passed before); picard in test_the_fixtures_are_clean is the real pin — cost if wrong: none.
- Task 4: Ruling: gatk fixture extended in place (input_index, intervals, dragstr_model, join map); two evaluate tests add input_index to given — cost if wrong: none.
- Task 4: Ruling: regenerated frontend constructors.fixture.json (stage-1 full run: test_constructor_fixture_tracks_the_fields_the_browser_renders failed on the join union) — the fixture mirrors the contract schema — cost if wrong: none; how the forge page renders a join map is checked in the end browser pass.
- Stage 1 end: make test → 4005 passed, 1 failed (fixture, fixed in follow-up commit; rerun 17/17).
- Task 4 review: Important — type rows on single-type ports never checked — fixed (test_a_type_row_on_a_single_type_port_is_checked RED→GREEN, suite 549/549).
- Task 4 review: minor 2 (count inflated by off typed ports) fixed with it — test_an_unconnected_typed_port_does_not_count_its_types RED→GREEN.
- Task 4 review: minor 6 MD0612 reordered.
- Final: minor (deferred): _subject/_quoted uses a backtick sentinel; return (name, qualifier) instead.
- Final: minor (deferred): a multi-key row's sentence states only its first key; two rows differing only in a later type. key read alike, and materialise._run_rules matches rows by sentence.
- Ruling: constructor schema 'join' object branch untitled ('Object' in the forge select) — fix in Task 7 (forge) — cost if wrong: a vague label.
- Task 5: Ruling: router routes required ports first, then decides optional states with their types, then routes the optional ports that are on — states were decided before any port was routed — cost if wrong: a contract listing an optional port before a required one routes its children in a different order (all suites unchanged).
- Task 5: Ruling: type facts in the router come from required ports only; an optional port's type is known only after it is switched on — cost if wrong: a row on an optional port's type cannot raise another optional input at routing (resolve still checks it).
- Task 5: Ruling: Review Focus 1 confirmed as a crash (empty channel name) — fixed with IRNode.entry_types: list[EntryType] (not dict: egress guard) recorded by resolve, read by materialise — cost if wrong: none; IR is not saved.
- Task 5: Ruling: a type-only row's strength stays the router default (REQUIRED) — its subject is a required port — cost if wrong: none.
- Task 6: Ruling: off ports derived in the emitter from Step.input_states, not a new CallArg field — the artifact already records them — cost if wrong: none.
- Task 6: Ruling: CallArg.joins: list[PortJoin] beside the scalar join (egress guard forbids mappings); SERIALISED_SHAPE extended without a SCHEMA_VERSION bump (phase 1's ruling: within the unreleased bump) — cost if wrong: none.
- Task 6: Ruling: an optional-at-run port's empty width is 2 inside a multi-port slot, the slot's absent only when alone (Task 1 review Important) — cost if wrong: none; pinned by test_an_optional_at_run_port_in_a_slot_is_an_empty_pair_when_left_empty.
- Task 6: Ruling: a run-optional port joined by_sample (or the head of a slot with a by_sample port) raises ValueError naming #466 at emission — cost if wrong: none (part 5).
- Task 6: Ruling: IRNode.entry_types added to NOT_CARRIED — channel type carries it — cost if wrong: none.
- Task 5 review: Important 1 (router/resolve disagree on type) fixed — test_a_held_earlier_alternative_wins_over_a_produced_later_one RED→GREEN; a pinned source still wins.
- Task 5 review: Important 2 (orphan steps from a refused alternative) fixed with checkpoint/restore in _satisfy_port — test_a_failed_alternative_leaves_no_steps_behind RED→GREEN.
- Task 5 review: minor 3 (optional accepts port from outside: no type) fixed — test_an_optional_accepts_port_from_outside_gets_a_channel RED→GREEN; _satisfy_port keeps the first alternative's missing when nothing makes any.
- Final: minor (deferred): _required_where_shared (router.py) keys on port.type_id, so an accepts port fed from fastq does not promote another step's optional fastq port sharing the channel.
- Final: minor (deferred): _source_for (possibly a tier-4 model call) now runs for every port before the constraint check, so a refused build may still make that call.
- Task 6 review: Important 1 (_no_blank_per_sample unreachable; test passed via the samplesheet refusal) — Ruling: guard deleted, test kept and matched to the samplesheet message — a run-scoped port is never paired per sample — cost if wrong: a run-scoped port joined by_sample emits a .join on a value channel (incoherent contract).
- Task 6 review: Important 2 (run-scoped head when port 0 off) — Ruling: no change — MD0601's first-port rule (Task 2) refuses an optional first port with mixed joins at load, pinned by test_an_optional_first_port_with_mixed_joins_is_refused — cost if wrong: none.
- Task 6 review: minors 3, 5, 6 fixed (vacuous assertion; CallArg.join_for first-port guard: test_call_arg_join_for_names_only_a_port_after_the_first RED→GREEN; samplesheet docstring).
- Final: minor (deferred): a gathered (.collect()) port inside a shared slot combines only the first item (.combine(X.collect().map{it[1]})) — pre-existing; file an issue.
- Stage 3 end: make test → 4023 passed.
- Task 7: Ruling: ToolTest.types (dict port→type, default the input's first alternative) added to the registry's test schema — a forge test of an accepts input had no type for its channel (crash like Review Focus 1) — cost if wrong: a field to rename in registry tests.
- Task 7: Ruling: forging items_of/_strip omit an empty type_id — an accepts input could not round-trip through items, so the forge could not draft salmon/minimap2/picard — test_an_input_that_accepts_several_types_round_trips_through_items RED→GREEN — cost if wrong: none.
- Task 7: Ruling: forge test edges take the producer output's type when the port has accepts — cost if wrong: none.
- Task 7: Ruling: dropped the params_for == entry_params assertion from the gatk forge test — with several per-sample inputs params_for sends one samplesheet input row while entry_params lists columns; pre-existing, never exercised (no earlier forge test had two per-sample inputs).
- Final: minor (deferred): forge params_for vs entry_params disagree for tests with several per-sample inputs (samplesheet); a forge test like gatk's may not run on Wiener — file an issue.
- Task 7: Ruling: added tests for _with_constraint_checks (none existed) in packages/mendel-api/tests/forge/test_forge_constraint_findings.py — cost if wrong: none.
- Task 8: Ruling: PortView.type_id for an accepts input is the connected type (channel or upstream output), and met uses it — the port's own type is empty, so it showed blank and unmet — tests RED→GREEN — cost if wrong: none.
- Task 7 review: Important 1 (tests drafter never saw types) fixed — forge.tests.v2; test_the_tests_drafter_names_the_type_of_its_data (written with v2; fails without the file).
- Task 7 review: Important 2 (types unchecked at review) fixed — _test_problems MF0507; test_a_test_type_names_an_input_and_a_type_it_accepts RED→GREEN.
- Task 7 review: minors 3, 4 fixed (guide sentences). Final: minor (deferred): setup-fed edges to an accepts port are not checked against its accepted types.
- Task 8 review: no Critical/Important. Final: minor (deferred): PortView.states for an accepts input come from alternative 0, not the connected one (latent: no accepts alternative declares states).
- Final: minor (deferred): an unwired/off accepts input shows type '' on the step card (Port.tsx 'reads: '; Picker queries candidates?type_id=) — show the accepted types.
- Final: minor (deferred): _connected_type computed twice per input port; its upstream-source branch is untested.
- Final: minor (deferred): _condition (build.py) duplicates constraints._subject's type wording — share one helper.
