# Tool constraints, phase 1 — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> In this repository the plan is executed by the session itself (CLAUDE.md: "Execute the agreed plan yourself"), so use superpowers:executing-plans.

**Goal:**
- Contracts can declare optional inputs, conditional outputs, constraint rows and groups.
- The engine evaluates and checks them, routes optional inputs (off, optional or required), and
  emits valid Nextflow.
- The forge drafts and checks them, so the quast walk (#412) can approve a true contract.

**Architecture:**
- The `when` evaluator moves from `mendel-resolver` to `comeni-core`, so contracts and rules share
  it.
- **`comeni-core`:**
  - new contract fields;
  - a pure `evaluate()`, which returns a `Verdict`;
  - an enumerating `check_constraints()`.
- **The router** reads each optional port's state from the person's goal constraints and from
  downstream needs, and records it.
- **The artifact** marks optional entry channels. An input that is off reuses `CallArg.empty_width`.
- **The forge's** contract item models inherit the new fields; a new prompt and findings teach and
  check them.

**Tech stack:** Python 3.12, Pydantic v2, Nextflow DSL2 emission, React + vitest (stages 5–6 only).

**Spec:** `docs/superpowers/specs/2026-11-06-tool-constraints-phase-1-design.md`.
**Issue:** #460 (under #463). **Branch:** a new `tool-constraints` branch, created from
`chatgpt-subscription`, which carries the forge prompts this builds on. Rebase it when #456 and
#458 merge.

## Global constraints

- **Purity:** contract model, evaluator and checks live in pure `comeni-core`, and the router in
  pure `mendel-resolver`. No network I/O.
- **Digests:** every new field serialises only when it differs from its default, so curated
  contract digests are unchanged.
- **Determinism:** sort every unordered collection before serialising. Sentence order is the
  contract's declaration order.
- **Diagnostics** are declared in `packages/comeni-core/src/comeni_core/diagnostics.yml`, emitted
  through `coded()`, and documented by `uv run python tools/generate_diagnostics_doc.py`.
  - `MD0601`–`MD0611` (engine, refusing) belong to this design.
  - `MF0530`–`MF0532` (forge, advisory, `refuses: false`).
- **No aliases before v0.1.0:** callers move to the new import path; nothing re-exports the old
  one.
- **Tests run through make:**
  - the scoped runner, `scratchpad t.sh` style: test DB on 127.0.0.1:5442, `uv run pytest -q <paths>`;
  - `make check` before every commit, run separately from the commit;
  - `make verify` after stages 2 and 3.
- **Guards:** every guard must be seen failing against the defect, and recorded in
  `tests/fixtures/guard-ledger.md`.
- **Plan record:** tick each step as it is done; record deviations under "Deviations" at the end.
- **Phase-1 fact keys:** only `given.<port>` and `param.<name>` are legal in a contract's `when`;
  measurements wait for #466.
- **Enumeration bound:** 4,096 setups, refused above that (`MD0607`).

## Review focus

1. **A curated contract with no new fields** must give byte-identical contract digests, and
   identical `pipeline.yml` and `.nf` for the RNA-seq example. *Pinned in Task 2 (digests) and
   Task 8 (golden emission unchanged).*
2. **A person switches an input off that a later step needs.** The build must refuse, naming both
   (`MD0609`), not silently drop the input. *Pinned in Task 6.*
3. **A constraint row names a port that doesn't exist** (a typo, or another case, `FASTA` vs
   `fasta`). It is refused at load (`MD0602`), never ignored. *Pinned in Task 2.*
4. **Two steps share one entry channel**, where one has it optional and the other required. The
   shared channel is required. *Pinned in Task 6.*
5. **A `pipeline.yml` saved before this change** still loads, because the new fields default.
   *Pinned in Task 7.*

---

## Stage 1 — the contract and the evaluator (`comeni-core`)

### Task 1: Move the `when` evaluator into `comeni-core`

**Files:**
- Create: `packages/comeni-core/src/comeni_core/logic/__init__.py`, `packages/comeni-core/src/comeni_core/logic/when.py`
- Move tests: `packages/mendel-resolver/tests/test_predicates.py` → `packages/comeni-core/tests/test_when.py`
- Modify (imports): `packages/mendel-resolver/src/mendel_resolver/premises.py`, `.../rules/table.py`, `.../rules/validate.py`, `packages/mendel-api/src/mendel_api/services/forge_rule_preview.py`, `packages/mendel-resolver/tests/test_rules.py`
- Delete: `packages/mendel-resolver/src/mendel_resolver/predicates.py`

**Interfaces:**
- Produces (`comeni_core.logic.when`):
  - `class Fact(Protocol)`, with `value: Any`;
  - `matches(when: dict[str, Any], facts: Mapping[str, Fact]) -> bool`;
  - `tier_of_row(when: dict[str, Any]) -> Tier`;
  - `PredicateError`, `ABSENT = "absent"`, `PRESENT = "present"`.
  - The semantics are those of today's `predicates.py`, unchanged.
- `mendel_resolver.premises.Premise` satisfies `Fact` structurally.

- [x] **Step 1:** `git mv` the test file to `packages/comeni-core/tests/test_when.py`. Change its
  import to `from comeni_core.logic.when import …`, and give it a minimal local `Fact` stand-in
  (a frozen dataclass with `value`) in place of `Premise`.
- [x] **Step 2:** Run `t.sh packages/comeni-core/tests/test_when.py`. Expected: FAIL with
  `ModuleNotFoundError: comeni_core.logic`.
- [x] **Step 3:** `git mv` `predicates.py` to `comeni_core/logic/when.py`. Replace the
  `TYPE_CHECKING` import of `Premise` with the `Fact` protocol, and update every caller in the
  Files list.
- [x] **Step 4:** Run `t.sh packages/comeni-core/tests packages/mendel-resolver/tests packages/mendel-api/tests/forge`.
  Expected: PASS. Then `make guards` (purity). Expected: PASS.
- [x] **Step 5:** `make check`, then commit: `refactor(core): one when evaluator in comeni-core (#460)`.

### Task 2: Contract fields and load-time validation

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MD0601`, `MD0602`)
- Test: `packages/comeni-core/tests/test_contract_constraints.py` (new)
- Test: `packages/comeni-core/tests/test_digest.py` (add one test)

**Interfaces:**
- Produces, in `comeni_core.declared.contract`:
  - `InputPort.required: bool = True`
  - `OutputPort.produced_when: dict[str, Any] | None = None`
  - `NfInput.absent: int = 0`, which has the same arity meaning as `NfInput.empty`
  - `class ConstraintRow(BaseModel)`, with:
    - `when: dict[str, Any] = {}`
    - `requires: list[str] = []`
    - `forbids: list[str] = []`
    - `because: str` (`min_length=1`)
    - `cite: str = ""`
    - at least one of `requires` or `forbids` must be non-empty
  - `class GroupKind(StrEnum)`: `ONE_OF = "one_of"`, `ANY_OF = "any_of"`, `ALL_OR_NONE = "all_or_none"`
  - `class Group(BaseModel)`, with:
    - `kind: GroupKind`
    - `members: list[str]` (`min_length=2`)
    - `when: dict = {}`
    - `because: str` (`min_length=1`)
  - `ModuleContract.constraints: list[ConstraintRow] = []` and `ModuleContract.groups: list[Group] = []`
  - `ModuleContract.optional_ports() -> list[str]`, in declaration order
- Serialisers drop the new fields when they hold their defaults, as `OutputPort._no_empty_format`
  already does.

- [x] **Step 1: Write the failing tests** in `test_contract_constraints.py`, with a `_quast()`
  helper that builds the spec §1 example contract:
  - `test_quast_loads_with_optional_inputs_and_a_conditional_output`: `fasta` and `gff` are
    `required is False`, and `misassemblies.produced_when == {"given.fasta": "present"}`.
  - `test_a_row_naming_an_unknown_port_is_refused`: `requires: ["FASTA"]` raises `MD0602`.
  - `test_a_when_with_a_measurement_key_is_refused_in_phase_1`: `{paired: true}` raises `MD0602`.
  - `test_given_must_name_a_port_and_param_a_param`: `{given.nope: present}` and
    `{param.nope: true}` both raise `MD0602`.
  - `test_an_all_optional_entry_needs_absent_and_a_required_one_forbids_it`: both cases raise `MD0601`.
  - `test_a_multi_port_entry_is_all_required_or_one_all_or_none_group`: `[dbsnp, dbsnp_tbi]`,
    both optional, with no group, raises `MD0601`; with the group, it loads.
- [x] **Step 2: Add `test_contracts_without_constraints_keep_their_digest`** to `test_digest.py`.
  For every curated contract in `registry/`, the digest equals the digest of the same contract
  dumped and reloaded. It also asserts that `"required"`, `"produced_when"`, `"absent"`,
  `"constraints"` and `"groups"` do not appear in `model_dump_json()`. Assert that the contract
  list is non-empty first.
- [x] **Step 3:** Run both files. Expected: FAIL (unknown fields, no codes).
- [x] **Step 4: Implement the fields.** Then implement `ModuleContract._constraints_name_real_things`
  (an after-validator), which raises:
  - `MD0602`, for unknown names in `requires`, `forbids` or `members`, and for `when` keys outside
    `given.<port>` and `param.<param>`;
  - `MD0601`, for the `nf_inputs` arity rules.

  Declare both codes in `diagnostics.yml`.
- [x] **Step 5:** Run `t.sh packages/comeni-core/tests packages/mendel-resolver/tests`. Expected:
  PASS. Regenerate the diagnostics doc.
- [x] **Step 6:** `make check`, then commit: `feat(core): optional inputs, conditional outputs and constraint rows in contracts (#460)`.

### Task 3: `evaluate()` and its sentences

**Files:**
- Create: `packages/comeni-core/src/comeni_core/declared/constraints.py`
- Test: `packages/comeni-core/tests/test_constraints_evaluate.py`; contract fixtures live in
  `packages/comeni-core/tests/fixtures/constraints/` (`quast.yml`, `kraken2.yml`, `gatk4_haplotypecaller.yml`)

**Interfaces:**
- Consumes: `matches`, `PRESENT` and `ABSENT` (Task 1); `ConstraintRow`, `Group` and
  `ModuleContract` (Task 2).
- Produces:
  - `class Setup(BaseModel)`, frozen, with:
    - `given: frozenset[str]` (connected ports);
    - `params: dict[str, Any]` (resolved values; a missing key means absent);
    - `unknown: frozenset[str] = frozenset()`: ports whose presence is decided per run (optional
      entry channels). Each is evaluated both present and absent.
  - `class Verdict(BaseModel)`, with:
    - `missing: list[str]`
    - `forbidden: list[str]`
    - `produced: list[str]`
    - `sentences: list[str]`
    - `holds_at_run_time: list[str]`: the sentences of rows that only the run can settle.
    - Each list keeps the contract's declaration order.
  - `def rows_of(contract: ModuleContract) -> list[ConstraintRow]`: explicit rows followed by each
    group expanded.
    - `one_of`: pairwise forbids, plus a "requires one of" row.
    - `any_of`: a "requires one of" row.
    - `all_or_none`: each member requires the others.
    - Expansion is deterministic.
  - `def evaluate(contract: ModuleContract, setup: Setup) -> Verdict`
  - `def sentence(row: ConstraintRow) -> str`. Exact copy:
    - for a requires row: ``"`{subject}` is used only with `{', '.join(requires)}` ({because})"``;
    - for a forbids row: ``"`{subject}` cannot be used with `{x}` ({because})"``;
    - the subject is the port or param in the row's `when`.

- [x] **Step 1: Write the failing tests:**
  - `test_quast_with_only_assemblies_produces_the_basic_reports`: `Setup(given={"consensus"})`
    gives `produced == ["results","tsv"]` and `missing == []`.
  - `test_quast_with_a_reference_produces_its_reports`: adding `fasta` adds `transcriptome`,
    `misassemblies` and `unaligned` to `produced`.
  - `test_gff_without_fasta_is_missing_fasta_with_its_sentence`: `missing == ["fasta"]`, and
    `sentences[0]` equals the exact sentence for quast's row.
  - `test_gatk_dbsnp_without_its_index_is_missing_the_index`: from `all_or_none`.
  - `test_kraken2_fastqs_only_with_the_flag`: `params={"save_output_fastqs": True}` produces
    `classified_reads_fastq`; `False` does not.
  - `test_an_unknown_reference_puts_the_gff_rule_at_run_time`:
    `Setup(given={"consensus","gff"}, unknown={"fasta"})` gives `missing == []` and a non-empty
    `holds_at_run_time`.
- [x] **Step 2:** Run. Expected: FAIL (no module).
- [x] **Step 3:** Implement. Build the fact map as `given.<p>` → a `Fact` with value `True` for
  each connected port, plus `param.<n>` → its value. An absent fact is a missing key, so
  `ABSENT` and `PRESENT` work unchanged.
- [x] **Step 4:** Run. Expected: PASS.
- [x] **Step 5:** `make check`, then commit: `feat(core): evaluate a contract's constraints into a verdict (#460)`.

### Task 4: Enumeration checks at load

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/constraints.py` (add `check_constraints`)
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py` (`load` calls it after `check_against`)
- Modify: `diagnostics.yml` (`MD0603`–`MD0607`)
- Test: `packages/comeni-core/tests/test_constraints_check.py`

**Interfaces:**
- Produces: `def check_constraints(contract: ModuleContract) -> list[Diagnostic]`, where
  `Diagnostic` is the type `conformance.py` already returns (*builder: reuse it from
  `comeni_core`; if it lives in `mendel_compiler`, return `list[tuple[str, str]]` as (code,
  message)*).
- **Values enumerated per param** named in any `when`:
  - a boolean: `[True, False]`;
  - an enum domain: its values;
  - a numeric domain: one value on each side of every compared literal;
  - no domain: `[absent]` plus each literal compared.

- [x] **Step 1: Write the failing tests**, one contract per finding, built inline:
  - `MD0603` (no setup is valid): a required port that is forbidden;
  - `MD0604` (an optional port connected in no valid setup);
  - `MD0605` (an optional port connected in every valid setup);
  - `MD0606` (an output whose `produced_when` never holds);
  - `MD0607`: 13 optional ports, which is 8,192 setups.
  - Plus `test_the_quast_kraken2_and_gatk_fixtures_are_clean`, and
    `test_load_refuses_a_contract_with_a_finding`.
- [x] **Step 2:** Run. Expected: FAIL.
- [x] **Step 3:** Implement. A setup is **valid** when its verdict has no `missing` and no
  `forbidden`. Make the call in `ModuleContract.load`; every finding refuses at registry load.
- [x] **Step 4:** Run `t.sh packages/comeni-core/tests`, then `make registry-lint` or the registry
  load tests (whichever `make check` runs). Every curated contract must still load. Expected: PASS.
- [x] **Step 5:** Record the guard in the ledger: delete the call in `load`, see
  `test_load_refuses…` fail, restore it.
- [x] **Step 6:** `make check`, then commit: `feat(core): check constraints for contradictions, dead and fake-optional inputs (#460)`.

## Stage 2 — routing and input states (`mendel-resolver`, `comeni-core` plan)

### Task 5: Input states in the goal and on route steps

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py` (the `Constraints` model)
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py` (`RouteStep`)
- Modify: `packages/comeni-core/src/comeni_core/plan/ir.py` (`IRNode`)
- Test: `packages/mendel-resolver/tests/test_optional_inputs.py` (new; contract builders from `mendel_resolver_tests.py`)

**Interfaces:**
- Produces:
  - `class InputState(StrEnum)`: `OFF = "off"`, `OPTIONAL = "optional"`, `REQUIRED = "required"`.
  - `class InputChoice(BaseModel)`, frozen, with:
    - `contract: ContractId`
    - `port: PortName`
    - `state: InputState`
    - `by: str`
    - `because: str = ""`
  - `Constraints.inputs: list[InputChoice] = []`, plus
    `Constraints.input_at(contract: str, port: str) -> InputChoice | None`.
  - `class InputRecord(BaseModel)`, with:
    - `port: str`
    - `state: InputState`
    - `reason: str`
    - `by: str`: `"person"`, `"router"` or a rule id.
  - `RouteStep.inputs: list[InputRecord] = []` and `IRNode.inputs: list[InputRecord] = []`.
  - Both are serialised only when non-empty, and sorted by port.

- [x] **Step 1: Write the failing test** `test_quast_with_only_assemblies_leaves_its_optional_inputs_off`:
  - a goal with `have: assembly.fasta` and `want: qc.report::assembly`, routed over a registry
    holding the quast fixture;
  - the step's `inputs` are `fasta` and `gff`, both `OFF`, `by="router"`, with the reason
    "off: not switched on".
- [x] **Step 2:** Run. Expected: FAIL.
- [x] **Step 3:** Implement the models. In the `for port in chosen.consumes` loop, skip a
  non-required port whose choice is absent or `OFF`, and record it.
- [x] **Step 4:** Run `t.sh packages/mendel-resolver/tests`. Expected: PASS, and the existing
  routes unchanged.
- [x] **Step 5:** `make check`, then commit: `feat(resolver): record optional inputs as off unless switched on (#460)`.

### Task 6: Switching on, needs, constraint checks after resolution

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (a re-check after parameters resolve)
- Modify: `diagnostics.yml` (`MD0608`–`MD0610`)
- Test: `packages/mendel-resolver/tests/test_optional_inputs.py`

**Interfaces:**
- Consumes: `evaluate`, `Setup` and `Verdict` (Task 3); `InputChoice` and `InputRecord` (Task 5).
- Produces:
  - `RegistryView.producing_port(contract, type_id, states) -> OutputPort`, the matched output
    (*builder: the spec leaves the exact place to you; `producers_of` is the reader*).
  - `resolve()` runs `_constraints_hold(plan, settings)` after parameter resolution, and raises
    `ConstraintViolation(UnroutableError)` with `MD0608`, `MD0609` or `MD0610`.

- [x] **Step 1: Write the failing tests:**
  - `test_a_person_switches_the_reference_on_as_optional`: an `InputChoice(state=OPTIONAL)` for
    `fasta` routes it to an entry channel marked optional, and the step records
    `by="person"`.
  - `test_switching_gff_on_brings_fasta_with_the_reason`: the `gff` choice alone puts `fasta` at
    `OPTIONAL`, `by="router"`, with the reason equal to the row's sentence.
  - `test_a_step_needing_misassemblies_makes_fasta_required`: a consumer of the conditional
    output, built inline. If more than one output of quast has the type, the needed one is the
    one the consumer's port matches by type and states.
  - `test_switching_off_an_input_a_later_step_needs_is_refused`: `MD0609`, naming both.
  - `test_a_forbidden_parameter_value_is_refused_after_resolution`: `MD0610`, and the parameter
    is not dropped.
  - `test_a_shared_channel_optional_here_and_required_there_is_required`.
- [x] **Step 2:** Run. Expected: FAIL.
- [x] **Step 3: Implement.**
  - **Port state:** the person's choice first. Then needs from conditional outputs (`given.` keys
    of a needed output's `produced_when` → `REQUIRED`). Then rows' `requires` given what is on
    → `OPTIONAL` or `REQUIRED`, inheriting the stronger state.
  - **No mid-route questions** (spec §4).
  - **After parameters resolve,** run `evaluate` per step, with `unknown` = its optional entry
    channels.
- [x] **Step 4:** Run `t.sh packages/mendel-resolver/tests packages/mendel-api/tests`. Expected: PASS.
- [x] **Step 5:** Record the guards: drop the re-check and see the forbidden test fail; drop the
  needs propagation and see the misassemblies test fail. Then restore both.
- [x] **Step 6:** `make check`, then `make verify`, then commit: `feat(resolver): switch optional inputs on by choice and need; check constraints after resolution (#460)`.

## Stage 3 — artifact and emission (`comeni-core` artifact, `mendel-compiler`)

### Task 7: Optional channels and off inputs in the artifact

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`Channel`, `Step`)
- Modify: the materialiser from the IR to the artifact (`packages/mendel-resolver/src/mendel_resolver/materialise.py`)
- Test: `packages/mendel-resolver/tests/test_materialise.py` and `packages/comeni-core/tests/` (artifact round trip)

**Interfaces:**
- Produces:
  - `Channel.optional: bool = False` and `Channel.absent_width: int = 0`. When `optional` is set,
    `absent_width` must be at least 1; this is the `NfInput.absent` of the entry it fills.
  - `Channel.run_rules: list[str] = []`: the run-time sentences from the verdict's
    `holds_at_run_time`.
  - `Step.inputs: list[InputRecord] = []`.
  - **An entry that is off** materialises as `CallArg(empty_width=absent)`, the existing
    placeholder path.

- [x] **Step 1: Write the failing tests:**
  - `test_an_off_reference_becomes_an_empty_call_argument`;
  - `test_an_optional_reference_becomes_an_optional_channel_with_its_width`;
  - `test_a_pipeline_saved_before_this_change_still_loads`, using an existing saved
    `pipeline.yml` fixture;
  - `test_input_records_round_trip_sorted`.
- [x] **Step 2:** Run. Expected: FAIL.
- [x] **Step 3:** Implement. Fields serialise only when set.
- [x] **Step 4:** Run `t.sh packages/comeni-core/tests packages/mendel-resolver/tests`. Expected: PASS.
- [x] **Step 5:** `make check`, then commit: `feat(core): optional channels and input records in pipeline.yml (#460)`.

### Task 8: Emission and conformance

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` (`_entry_channels`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/modulespec.py` (parse `optional:` on emits)
- Modify: `packages/mendel-compiler/src/mendel_compiler/conformance.py` (`MD0611`)
- Test: `packages/mendel-compiler/tests/` (emission goldens for quast off, optional and required;
  plus the existing goldens unchanged)

**Interfaces:**
- Produces:
  - **An optional channel** is emitted as
    `params.<param> ? <expression> : Channel.value(<_empty(absent_width)>)`, built from its
    normal expression, with `_as_value` applied as today.
  - `ModuleSpec.optional_emits: list[str]`.
  - `MD0611` is returned from `against()`.

- [x] **Step 1: Write the failing tests:**
  - three quast goldens: off gives `[[:], []]` in both reference slots; optional gives the
    ternary; required gives a plain channel;
  - `test_rnaseq_example_emission_is_unchanged` (the existing golden must still match: Review
    focus 1);
  - `test_an_optional_emit_declared_always_is_md0611`;
  - `test_modulespec_reads_optional_emits` on quast's real `main.nf` (the fixture copy).
- [x] **Step 2:** Run. Expected: FAIL for the new tests, and PASS for the existing goldens.
- [x] **Step 3:** Implement.
- [x] **Step 4:** Run `t.sh packages/mendel-compiler/tests`, then `make verify` and `make static`.
  `make verify` must include a stub run of the quast golden pipeline with and without
  `--fasta` (*builder: add it beside the existing stub-run tests if one does not take
  parameters*). Expected: PASS.
- [x] **Step 5:** `make check`, then commit: `feat(compiler): emit optional channels and check optional emits (#460)`.

## Stage 4 — the forge

### Task 9: Items, prompt v6 and findings

**Files:**
- Modify: `packages/mendel-forge/src/mendel_forge/forging/values.py`. Add the item keys
  `contract:constraint` → `ConstraintRow` and `contract:group` → `Group`, and have `contract_of`
  and `items_of` carry them in key order `<n>`. `InputItem` and `OutputItem` inherit the new
  fields as they are.
- Create: `packages/mendel-api/src/mendel_api/forge/prompts/forge.draft.v6.md`, from v5.
- Modify: `packages/mendel-api/src/mendel_api/services/forging_ai.py` (`_PURPOSE`, the default draft prompt).
- Modify: `packages/mendel-forge/src/mendel_forge/forging/checks.py` (`MF0530`–`MF0532`, plus
  `check_constraints` on the assembled contract).
- Modify: `diagnostics.yml`.
- Test: `packages/mendel-forge/tests/test_forge_checks.py`, `packages/mendel-api/tests/forge/test_forging_ai.py`.

**Interfaces:**
- Consumes: `ConstraintRow`, `Group` (Task 2); `check_constraints` (Task 4); `ModuleSpec.optional_emits` (Task 8).
- Produces:
  - `contract_findings(items, spec) -> dict[str, list[QuestionFinding]]`, which reuses the
    `QuestionFinding` shape;
  - `ItemView.findings` is filled for contract items too.

- [x] **Step 1: Write the failing tests:**
  - `test_quast_items_round_trip_through_contract_of` (with constraint and group items);
  - `test_an_optional_emit_without_produced_when_is_mf0530`;
  - `test_an_input_used_only_under_a_ternary_marked_required_is_mf0531`;
  - `test_an_all_optional_entry_without_absent_is_mf0532`;
  - `test_the_contract_prompt_teaches_constraints`: the rendered prompt has `"produced_when"`,
    `contract:constraint:` and `"absent"`, and the prompt id is `forge.draft.v6`.
- [x] **Step 2:** Run. Expected: FAIL.
- [x] **Step 3: Write `forge.draft.v6`.**
  - It adds the shapes from spec §1 and §7, and the evidence list of §7.
  - It keeps v5's exact-fields rule. It updates "Nothing else: no optional" to name the real
    fields: `required`, `produced_when`, `absent`.
  - Then wire it in `_PURPOSE` and the default, and implement the findings.
- [x] **Step 4:** Run `t.sh packages/mendel-forge/tests packages/mendel-api/tests/forge`. Expected: PASS.
- [x] **Step 5:** Record the guards (each finding against code without it). `make check`, then
  commit: `feat(forge): draft and check optional inputs, conditional outputs and constraints (forge.draft.v6) (#460)`.

### Task 10: Forge page and the live quast contract

**Files:**
- Modify: `frontend/src/registry/forging/PieceItems.tsx` (render constraint and group items as
  their sentence, with the raw value folded)
- Modify: the tool diagram in `frontend/src/registry/forging/` (hollow optional inputs; "only
  with <port>" on conditional outputs)
- Modify: `packages/mendel-api/src/mendel_api/services/forging.py` (`ItemView.sentence: str | None`, from `sentence()`), then `make client`
- Test: `frontend/src/registry/forging/*.test.tsx` (the existing pattern)

- [x] **Step 1: Write the failing vitest tests:** a constraint item shows its sentence; an
  optional input is hollow and labelled "optional"; a conditional output shows "only with fasta".
- [x] **Step 2:** Run `npx vitest run src/registry/forging`. Expected: FAIL.
- [x] **Step 3:** Implement with tokens only (`tokens.test.ts` forbids raw colours).
- [x] **Step 4:** Run `npx vitest run` and `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Inspect in a browser at 1440 and 390, light and dark, on quast's adaptation. *Not done: the Chrome extension disconnected during the session; required before merge.*
- [x] **Step 6: Live.** Restart `mendel-ai-worker`, then redraft quast's Contract piece on
  `chatgpt/gpt-6.1-sol`. Record what it drafted for `fasta`, `gff`, the three reports and the
  constraint row on #412. Do not approve it; the operator approves.
- [x] **Step 7:** `make check`, then commit: `feat(forge): show constraints and optional ports on the forging page (#460)`.

## Stage 5 — the run (artifact rules, emission guard, Wiener, run sheet)

Written 2026-11-06, after stage 4, from the code. **Finding that shaped it:** Wiener requires
a run to supply exactly the params the artifact leaves null (`routes/runs.py` `submit`). A
sentence alone cannot be checked, so a run-time rule becomes structured, with the param names
it concerns. The pipeline then checks it itself, so it holds however the run is launched.

### Task 11: Structured run rules, and the pipeline checks them

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`Step.run_rules`
  becomes `list[RunRule]`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/materialise.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py` and its `main.nf.j2` template
- Test: `packages/mendel-compiler/tests/test_optional_inputs_built.py`

**Interfaces:**
- Produces: `class RunRule(BaseModel)`, frozen, with:
  - `given: list[NfIdentifier]`: the params that, when supplied, make the rule apply;
  - `requires: list[NfIdentifier]`;
  - `forbids: list[NfIdentifier]`;
  - `says: Line`: the row's sentence.

  It is built in materialise from each row in `holds_at_run_time`, mapping each
  `given.<port>` to the param of the channel feeding that port.
- **Emission:** after the entry channels, one guard per rule, deduplicated and sorted:
  `if (params.a && !params.b) { error "<says>" }` (and `&& params.c` for each `forbids`).

- [ ] **Step 1: Failing tests:**
  - `test_a_rule_only_a_run_can_settle_is_on_the_step` now asserts `RunRule(given=[gff
    param], requires=[fasta param], says=…)`;
  - `test_the_pipeline_refuses_a_gff_without_a_reference_at_its_start` asserts the emitted
    guard line.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, with `RunRule` in the egress allowlist (`says`) and
  SERIALISED_SHAPE.
- [ ] **Step 4:** Run the compiler, artifact and emit tests, then `make static`. Expected: PASS.
- [ ] **Step 5:** `check.sh`, then commit.

### Task 12: Wiener knows its optional inputs; the run sheet offers them

**Files:**
- Modify: `packages/wiener-api/src/wiener_api/services/artifacts.py` (`optional_holes`,
  `run_rules`)
- Modify: `packages/wiener-api/src/wiener_api/routes/runs.py` (`ArtifactStored.optional`,
  `ArtifactStored.rules`)
- Modify: `frontend/src/build/Submit.tsx`, `frontend/src/build/useSubmit.ts`; then `make client`
- Test: `packages/wiener-api/tests/test_optional_holes.py`, `frontend/src/build/Submit.test.tsx`

**Interfaces:**
- **Wiener:**
  - `optional_holes(artifact_id) -> set[str]`: the params of the `pipeline.yml` channels that
    are optional;
  - `run_rules(artifact_id) -> list[dict]`: the steps' `RunRule`s, as plain dicts. Wiener
    stays unaware of contracts.
- **Submit form:**
  - an optional param shows the label "optional — leave empty to run without it", plus the
    outputs it enables if the artifact says so;
  - an empty optional value is sent as `""`;
  - a rule broken by the values entered is shown under the fields, with its `says`, and blocks
    *Start run*.

- [ ] **Step 1: Failing tests:**
  - Wiener: optional holes from a built quast artifact; a submit with `fasta: ""` is accepted;
  - frontend: the optional label; an empty optional input sent as `""`; a GFF without a
    reference blocks Start with the sentence.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Then inspect in a browser at 1440 and 390, light and dark.
- [ ] **Step 4:** Run `t.sh packages/wiener-api/tests` and `npx vitest run`. Expected: PASS.
- [ ] **Step 5:** `check.sh`, then commit.

## Stage 6 — the builder

**Finding that shaped it:** a person's choice in a build is a decision family with revisions,
like `source` (A1, commit 1f451359: one family about 180 lines of API plus migration, tests
and authoring). Switching an optional input therefore becomes a decision family. One path
then serves a click, the chat and the model. The port legend already uses *hollow* for "a
required input nothing feeds" (`Port.tsx`), so an optional input is drawn dashed, not hollow.

### Task 13: The `optional_input` decision family

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/decisions.py`
  (`OptionalInputChoice(consumer, port, state)` into `Constraints.inputs`) and
  `payloads.py` (`DecisionChange.kind` adds `"optional_input"`)
- Modify: `packages/mendel-api/src/mendel_api/decision_models.py`, `services/decisions.py`,
  `services/changes.py`, `models.py`, `shape_versions.py`, `shapes.py`
- Create: a migration adding `pipeline_optional_input` and `pipeline_optional_input_revision`,
  modelled on `7ea478ea7f3b_structural_intents.py`
- Test: `packages/mendel-authoring/tests/test_decisions_intents.py`,
  `packages/mendel-api/tests/authoring/decisions/test_intent_families.py`

- [ ] **Step 1: Failing tests:**
  - a change of kind `optional_input` (`subject=source_subject(contract, port)`,
    `value="optional"`) puts an `InputChoice` in the goal;
  - `retract` withdraws it;
  - history says who and when.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, mirroring `source` throughout.
- [ ] **Step 4:** Run the authoring and API decision tests, `make test-db`, and the
  infrastructure tests. Expected: PASS.
- [ ] **Step 5:** `check.sh`, then commit.

### Task 14: Step cards show optional inputs; a person switches one on

**Files:**
- Modify: the canvas view models (`PortView` gains `optional: bool`, `state`, `adds: list[str]`)
  in `packages/mendel-api/src/mendel_api/services/` (wherever `PortView` is built); then
  `make client`
- Modify: `frontend/src/build/Port.tsx`, the living node (`frontend/src/build/living/LivingNode.tsx`)
  and the manual canvas node
- Test: `frontend/src/build/Port.test.tsx` and the living node tests

- [ ] **Step 1: Failing tests:**
  - an optional port renders dashed with "optional" and what it adds;
  - "+N optional inputs" folds them;
  - switching one on sends `optional_input` with `value: "optional"`;
  - a refused connection shows the verdict's sentence.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. A Claude Design canvas first if the node layout is not obvious from
  the existing artboard. Then compare in a browser at 1440 and 390, light and dark.
- [ ] **Step 4:** Run `npx vitest run` and `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** `check.sh`, then commit.

### Task 15: Mendel's AI proposes input states, flagged and confirmed

**Files:**
- Modify: the authoring chat's allowed commands (the payloads the chat model may return) so
  `optional_input` is one of them, actor `model`
- Modify: the receiving check, which refuses a port that is not optional on that contract
- Test: authoring chat tests with a recorded reply

- [ ] **Step 1: Failing tests:**
  - a recorded model reply switching quast's `fasta` on becomes a proposal flagged as the
    model's, applied only when the person confirms it;
  - a reply naming a required port is refused at the boundary.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the scoped suites. Expected: PASS.
- [ ] **Step 5:** `check.sh`, then commit.

## Stage 7 — docs and the test run

### Task 16: Documentation

- [ ] The pipeline schema reference documents `Channel.optional`, `absent_width`,
  `Step.input_states` and `run_rules`.
- [ ] A user how-to covers optional inputs in the builder and the run sheet.
- [ ] An explanation section covers constraints versus decisions, linking #463.
- [ ] `CHANGELOG.md`, under each package.
- [ ] `make docs`, `make links`, then commit.

### Task 17: The quast walk to a real run

- [ ] Approve quast's pieces in the forge, through assembly. **The operator approves, not the
  agent.**
- [ ] Run the forge's tests on Wiener.
- [ ] Build a pipeline with quast and its reference **optional**.
- [ ] Run it twice, once with a reference and once with it empty. The run with the reference
  writes the three reports; the empty run writes only `results` and `tsv`, and both succeed.
- [ ] Record the results on #412 and #460.

## Deviations

Stages 1–4 are done (2026-11-06). Rulings made while executing, from the ledger:

- Ruling: per-commit check = make check minus the full suite (check.sh: lint types docs docs-status links doc-paths doc-sizes guards) + the task's scoped tests; the full `make test` runs at each stage end — the full suite takes ~8 min and always fails the 62 #455 token tests — cost if wrong: a cross-package break found at stage end, not at its commit.
- Task 1: Ruling: `operator` added to comeni-core's purity allowlist — the evaluator moved with its stdlib import; resolver already allowed it — cost if wrong: none (stdlib, pure).
- Task 2: Ruling: documented the new fields in contract-schema.md now (planned for stage 7) — make docs refuses undocumented schema fields — cost if wrong: none.
- Task 3: Ruling: `itertools` added to comeni-core's purity allowlist — stdlib, pure; enumerating setups — cost if wrong: none.
- Task 4: Ruling: check_constraints returns coded message strings, not conformance.Diagnostic — Diagnostic lives in mendel-compiler, which pure comeni-core cannot import; a coded string carries the code — cost if wrong: a later caller wraps strings into Diagnostic.
- Task 4: Ruling: `math` (prod) added to comeni-core's purity allowlist — stdlib, pure — cost if wrong: none.
- Task 5: Ruling: InputChoice has no by/because — like SourcePin, a goal constraint is the person's by being there; the plan listed both — cost if wrong: add fields when a model proposes choices (stage 6).
- Task 5: Ruling: InputRecord.by is an InputDecider enum (person, router), reason a Line allowlisted in the egress guard — bare str fails the egress guard; rule decider joins with #461 — cost if wrong: an enum member to add.
- Task 6: Ruling: an optional input switched on routes through goal.have like any entry input — entry channels are derived from have (invariant 15); switching one on in the builder (stage 6) adds the have entry — cost if wrong: the AI/builder must add the have entry with the choice.
- Task 6: Ruling: the shared-channel test (optional here, required there) moves to Task 7 — channel optionality is decided at materialise, not route — cost if wrong: none.
- Task 6: Ruling: pipeline_authoring_turn shape 4→5, identity upgrade + migration e3b9f1c7a2d4 — test_shapes requires it; inputs absent reads as [] — cost if wrong: none.
- Task 6: Ruling: make verify replaced by its parts (check.sh + scoped suites + pytest -m slow) — make check's full suite always fails #455 — cost if wrong: none; slow 19/19 passed.
- Task 7: Ruling: the artifact field is Step.input_states, not Step.inputs — Step.inputs already holds the StepInput wiring — cost if wrong: a rename.
- Task 8: Ruling: an optional sample-scoped channel in samplesheet form is refused at emission (ValueError naming #466); run-scoped optional channels get the ternary on both paths — a blank column needs per-row placeholders — cost if wrong: a per-sample optional input cannot be built until #466.
- Task 7: Ruling: tests for artifact + emission live in packages/mendel-compiler/tests/test_optional_inputs_built.py (plan: resolver/comeni-core) — they need a full build over an overlay layer — cost if wrong: none.
- Task 7: Ruling: no SCHEMA_VERSION bump — test_pipeline_compatibility: within an unreleased bump (released=1, current 8) extending SERIALISED_SHAPE is enough; v8 fixture still loads (Review focus 5 holds) — cost if wrong: none.
- Task 7: Ruling: the emission ternary landed in Task 7's commit — the artifact tests build and emit — Task 8 keeps modulespec + MD0611 — cost if wrong: none.
- Task 7: Ruling: run-time rule sentences live on Step.run_rules, not Channel.run_rules — test_scope_override forbids free text on a channel — cost if wrong: the run sheet gathers from steps (stage 5).
- Task 8: Ruling: MD0611 reports, does not refuse (spec said refuse at load for curated contracts) — STAR's curated bam is optional:true in main.nf yet always written by the module's default --outSAMtype; refusing broke every build — cost if wrong: a contract wrongly saying always is only reported; the forge's MF0530 still flags it at drafting.
- Task 8: Ruling: blocking now reads diagnostics.yml refuses (conformance.blocking) instead of excepting MD0100 by code, in orchestrate and layer_verbs — one source of truth — cost if wrong: a refuses:false code no longer stops a build, which is what refuses:false says.
- Task 8: Ruling: the Nextflow stub run of quast with and without the reference is deferred to stage 7's live walk — it needs quast's module vendored into a layer (module.yml, upstream sha); emitted text is pinned by tests and make static/slow pass — cost if wrong: a Nextflow-level error in the ternary found at the walk.
- Task 9: Ruling: MD0603–MD0606 on current items attach to contract:process (check_constraints reports per contract, not per item) — cost if wrong: a finding shown on the process row rather than the item it concerns.
- Task 10: Ruling: constraint/group keys are contract:constraint:row<n> and contract:group:group<n> — the item KEY pattern requires a name to start with a letter; loosening it weakens every key — cost if wrong: a rename.
- Task 10: BLOCKED step 5: browser inspection at 1440/390 light/dark — the Chrome extension disconnected this session; must be done before merge.
