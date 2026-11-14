# Rule proposals: the model proposes, the engine checks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** from people's repeated tier-4 answers, a model proposes rule rows. The engine checks
them against the evidence, the loader and a replay over past pipelines, and a person approves.
The next build then settles that question by the rule.

**Architecture:**
- **Pure parts.** `mendel_resolver.proposals` holds the evidence (`Case`), the engine's judge and
  the replay.
- **The model call.** It is a declared egress payload (`rule_proposal`) with a prompt and a reply
  model, called the way the forge calls its model.
- **The adapters.** These live in `mendel-api`:
  - the source, which reads kept pipelines;
  - storage, the `rule_proposal` table;
  - a background job;
  - the sink, which writes the installation's own registry layer. That layer is stacked above the
    release wherever the installation reads the registry to build.
- **The page.** A Learned rules tab.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy and Alembic, FastAPI, ARQ, React and vitest.

**Spec:** `docs/superpowers/specs/2026-11-13-rule-proposals-design.md`

## Global Constraints

- **Branch.** Work on `feat/constraints-phase-1-stages-5-6`. Never push.
- **Git.** Use `git -C`; never chain git after `cd`; no `git stash`.
- **Checks.** Run them separately before committing, with targeted tests per task. Full checks run
  once at the end, alone, with nothing else on the 5442 test DB.
- **Test database.** Use the Make targets, or the `MENDEL_TEST_DATABASE_URL` and
  `WIENER_TEST_DATABASE_URL` env vars on 5442. Run `make test-db` after adding a migration.
- **Thresholds.** `MIN_CASES = 3`, a module constant named as the first AI-responsibility knob.
- **Evidence** is only a decision that meets all of these:
  - `tier == 4`;
  - `human_override` is set;
  - `len(candidates) >= 2`;
  - `kind` is `producer` or `param`.
- **Facts.** Only study-wide scalar facts from `pipeline.facts.measurements`.
- **Purity.** No I/O in `mendel_resolver.proposals`.
- **What reaches the model.** Only the declared `rule_proposal` payload: no sample names, keys,
  references or file names.
- **Tests never call a live model.** They use a fake client with recorded replies, as in
  `test_forging_ai.py`.
- **The model.** Use the forge's setting: `model_access("forge", "analysis")`, prompt id
  `rules.propose.v1`.
- **The installation layer.** It is `settings.own_layer` (default `<workspace_root>/layer`), and is
  stacked only when its `registry.yml` exists. Learned tables go in `rules/learned/<slug>.yml`,
  where the slug is the target key with `:` and `.` replaced by `-`.
- **Commit trailer:** `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A model row that would overturn a recorded person answer is refused,** and the case is named
   (Task 2).
2. **A model row that no case reaches is refused.** The model may not invent support (Task 2).
3. **An existing table's rows stay first.** The appended rows never override a row that already
   fires (Tasks 2 and 3).
4. **Withdrawing a rule brings the question back.** The registry digest covers the installation
   layer, so no build cache serves the old answer (Task 4).
5. **A rejected proposal is not asked for again** until the target's evidence digest changes
   (Task 6).

---

### Task 1: Cases from a pipeline (pure)

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/proposals.py`
- Test: `packages/mendel-resolver/tests/test_proposals.py`

**Interfaces:**
- Produces:
  - `Case(BaseModel, frozen)` with these fields:
    - `target: DecisionTarget`;
    - `facts: dict[str, ParamValue]`;
    - `answer: ParamValue`;
    - `reason: str` (`override_reason`, or `""`);
    - `pipeline: str`;
    - `decision: str` (the decision key);
    - `by_person: bool`;
    - `tier: int`.
  - `Case.target_key` returns `target.key()`.
  - `Case.evidence` is true when `by_person` and `tier == 4`.
  - `cases_of(pipeline: Pipeline, registry: Registry, pipeline_id: str) -> list[Case]` returns
    every producer and param decision with two or more candidates and a resolvable target. It is
    sorted by `(target_key, pipeline, decision)`. Model answers and tier-3 decisions are kept,
    because the replay needs them.
    - **A producer decision** maps to `{effect: implementation, of: role}`, where the role is the
      single role every candidate's contract lists. Otherwise it is skipped.
    - **A param decision** `<node>.<param>` maps to `{effect: param, of: role, name: param,
      when_implementation: [contract]}`. The contract is the step's `module.contract_id`, and it
      must have a single role.
  - `evidence(cases) -> dict[str, list[Case]]` groups the evidence cases of each target that has
    at least `MIN_CASES` of them.
  - `evidence_digest(cases) -> str` is the sha256 of the sorted JSON.

- [x] **Step 1: Write the failing tests.** Load a fixture pipeline built from the RNA-seq example,
  then edit `decisions` and `facts`.
  - `test_a_persons_tool_choice_is_evidence`: star and hisat2 fill `alignment`, with a human
    override and `read_length: 150`. Expect target key `implementation:alignment`, the facts and
    the answer.
  - `test_a_models_answer_is_a_case_but_not_evidence`. Also: one candidate gives no case.
  - `test_candidates_sharing_no_single_role_are_skipped`.
  - `test_a_setting_answer_names_its_tool`.
  - `test_per_sample_facts_are_left_out`.
  - `test_evidence_needs_three_answers_and_its_digest_is_stable_under_order`.
- [x] **Step 2: Run** `uv run pytest packages/mendel-resolver/tests/test_proposals.py -q`.
  Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run.** Expected: PASS.
- [x] **Step 5: Commit** `feat: cases and evidence from people's answers (#462)`.

### Task 2: The engine's judge (pure)

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/proposals.py`
- Test: `packages/mendel-resolver/tests/test_proposals.py`

**Interfaces:**
- Consumes: `Case`, and `Decision`/`DecisionRow`/`DecisionTarget` from
  `mendel_resolver.rules.format`.
- Produces:
  - `table_with(target: DecisionTarget, existing: Decision | None, rows: list[DecisionRow],
    cite: str) -> Decision`. It returns the existing rows followed by the new ones, or a new table
    with `because: "learned from people's answers"`. The engine sets every new row's `cite`.
  - `cite_for(cases) -> str` returns `"kept pipelines <sorted unique ids>, decision <key>"`.
  - `judge(table: Decision, new: list[DecisionRow], cases: list[Case]) -> list[str]` returns
    problems, empty when sound:
    - **Contradiction:** for each evidence case, the first row of `table` that matches its facts
      must give its answer. Otherwise: `"<pipeline> <decision>: a person chose <answer>; the table
      would choose <x>"`. No matching row at all is not a contradiction.
    - **Unsupported:** a new row that matches no evidence case gives `"row <n> matches none of
      the answers it was drafted from"`.
    - **Shadowed:** a new row whose cases are all settled by an earlier row gives `"row <n> never
      fires: an earlier row settles every case it matches"`.
  - The row's own validity (`DecisionRow.model_validate`) is checked where the reply arrives
    (Task 5). The loader check is Task 6.

- [x] **Step 1: Write the failing tests.**
  - `test_a_row_agreeing_with_every_answer_is_sound`;
  - `test_a_row_overturning_a_person_is_refused_and_names_the_case` (Review Focus 1);
  - `test_an_invented_row_is_refused` (Review Focus 2);
  - `test_existing_rows_stay_first` (Review Focus 3): the table for `implementation:alignment`
    from `registry/rules/alignment.yml` keeps its two rows first. A new row the registry's
    `read_length` rows already cover is "never fires";
  - `test_a_threshold_row_is_judged_by_its_comparison`: `when: {read_length: ">= 100"}`.
- [x] **Step 2: Run.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run.** Expected: PASS.
- [x] **Step 5: Commit** `feat: the engine judges a proposed rule against its evidence (#462)`.

### Task 3: The replay (pure)

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/proposals.py`
- Test: `packages/mendel-resolver/tests/test_proposals.py`

**Interfaces:**
- Produces:
  - `Replayed(BaseModel, frozen)` with `pipeline`, `decision`, `recorded`, `would`, `agrees: bool`
    and `by_person: bool`.
  - `replay(table: Decision, new: list[DecisionRow], cases: list[Case]) -> list[Replayed]`. It
    lists every case of the target, of any tier or author, whose first matching row is a new
    row. It is sorted with disagreements first, then by pipeline and decision.
- [x] **Step 1: Write the failing tests.**
  - `test_replay_lists_what_the_rows_would_settle`;
  - `test_replay_shows_a_models_answer_it_would_change_first`;
  - `test_replay_skips_cases_an_existing_row_settles`.
- [x] **Step 2: Run.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run.** Expected: PASS.
- [x] **Step 5: Commit** `feat: replaying a proposal over past pipelines (#462)`.

### Task 4: The installation's own layer

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/settings.py`: `own_layer: Path | None = None`, and
  `registry_roots() -> list[Path]`.
- Modify: `packages/mendel-api/src/mendel_api/services/registry.py`. `signature`, `digest`,
  `stack` and `_load` cover every root, keyed on the roots tuple, and the digest is
  `blueprint.registry_digest(roots)`. Add `own_layer() -> Path` and `ensure_own_layer() -> Path`,
  which writes `registry.yml` (`name: installation`, `requires_format: 2`).
- Modify: these `active_registry()` readers that build or digest. Each moves to
  `registry_roots()`:
  - `services/build.py` (`_built`, `of`, `orchestrate.build(..., registry_roots=...)`);
  - `services/blueprint.py` (`resolve` default);
  - `services/authoring_preview.py:42`;
  - `stages/building/walk.py:180`.
- Leave on `active_registry()`: forging and forge tests (they publish to comeni-registry),
  inspect's piece paths, reports and the release label.
- Test: `packages/mendel-api/tests/test_own_layer.py`

- [x] **Step 1: Write the failing tests.**
  - `test_no_own_layer_reads_the_release_alone`.
  - `test_an_own_layer_stacks_above_the_release`. A learned alignment table, the registry's rows
    plus `when: {}` → hisat2, means:
    - `registry.stack()` records the displacement;
    - the RNA-seq goal with no `read_length` chooses hisat2;
    - the pipeline's registry provenance names both layers.
  - `test_withdrawing_moves_the_digest` (Review Focus 4).
- [x] **Step 2: Run** via the test DB. Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the new tests, plus `packages/mendel-api/tests -q -k "registry or build or
  blueprint or preview"`. Expected: PASS.
- [x] **Step 5: Commit** `feat: the installation's own registry layer, above the release (#462)`.

### Task 5: The model point

**Files:**
- Create: `packages/comeni-core/src/comeni_core/egress/rules.py`, holding:
  - `RuleProposalRequest(EgressPayload)`, with `target: Line`, `existing: list[RowText]`, `facts:
    list[FactKind]`, `answers: list[str]` and `cases: list[CaseText]`;
  - `CaseText`, with `facts: dict[str, ScalarValue]`, `answer: str` and `reason: Line`.
- Modify: `packages/comeni-core/src/comeni_core/egress/boundaries.py`: add `"rule_proposal":
  Boundary(RuleProposalRequest, BoundaryFlow.FORGE)`. Add the egress guard declarations,
  `FREE_TEXT_FIELDS` and the like, as the guards require for a new payload.
- Create: `packages/mendel-api/src/mendel_api/rules/prompts/rules.propose.v1.md` and
  `packages/mendel-api/src/mendel_api/rules/replies.py`, holding:
  - `ProposalReply`, with `rows: list[dict]` and `why: str`;
  - `rows: []` with `why` means "no rule".
- Create: `packages/mendel-api/src/mendel_api/services/rules_ai.py`. It holds
  `propose(target, existing, cases, facts, answers, client=None) -> tuple[list[DecisionRow],
  str, str | None, list[str]]`, returning the rows, `why`, the invocation id and the problems.
  - **The call.** One call, then a retry with problems, as in `forging_ai.draft_piece`. Each call
    is recorded as an `ai_invocation` with agent `forge`, purpose `analysis` and prompt id
    `rules.propose.v1`.
  - **Checks where the reply arrives:**
    - each row is a valid `DecisionRow`;
    - the facts it tests are among those given;
    - its `then` is among the legal answers;
    - `judge` finds nothing.
- Test: `packages/mendel-api/tests/test_rules_ai.py`, plus egress guard coverage, which comes
  automatically from `BOUNDARIES`.

**The prompt says:**
- what a rule row is;
- that existing rows stay first;
- that new rows only cover where they missed;
- to propose the fewest, simplest rows the answers support, using a threshold (`">= 100"`) for a
  number only when the answers bear it out;
- to use the people's reasons for `because`;
- to propose no row (`rows: []`) when the answers have no pattern;
- that the engine sets `cite` and will refuse a row that contradicts any answer.

The request is rendered into the prompt as sorted JSON-ish text.

- [x] **Step 1: Write the failing tests** with a fake client:
  - `test_a_recorded_reply_becomes_rows_and_an_invocation`;
  - `test_a_row_contradicting_a_person_goes_back_once_then_fails` (spec "done when");
  - `test_a_then_outside_the_legal_answers_is_refused`;
  - `test_no_model_configured_says_so`;
  - `test_the_payload_holds_no_sample_names`: a case built from a pipeline whose samplesheet has
    sample names; none of them appear in the rendered prompt.
- [x] **Step 2: Run.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the tests and `uv run pytest tests/guards -q`. Expected: PASS.
- [x] **Step 5: Commit** `feat: the rule_proposal model point, checked where it arrives (#462)`.

### Task 6: Proposals: source, storage, job, check, sink and routes

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py`: `RuleProposal` with these columns:
  - `id`;
  - `target_key` (String 200, indexed);
  - `target` (Json);
  - `rows` (Json);
  - `why` (Text);
  - `evidence_digest` (String 71);
  - `invocation` (String 32, nullable);
  - `status` (`proposed`, `approved`, `rejected`, `withdrawn`, `superseded` or `refused`);
  - `problems` (Json);
  - `decided_by` and `decided_at` (both nullable);
  - `created_at`.
- Create: an Alembic migration `rule_proposal`.
- Create: `packages/mendel-api/src/mendel_api/services/proposals.py` and
  `packages/mendel-api/src/mendel_api/routes/proposals.py` (registered in `main.py`). Add a job,
  `propose_rules`, to the AI worker's functions.
- Test: `packages/mendel-api/tests/test_rule_proposals.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
  - **The source:** `kept() -> list[tuple[str, Pipeline]]`. It covers every `PipelineDraft` with
    `kept_at`, read from `settings.draft_root/<id>/pipeline.yml`. An unreadable file is skipped
    and logged. Results are cached on the sorted `(id, kept_digest)` tuple. `cases()` is the
    concatenation of `cases_of` over them.
  - **The run:** `run(client=None) -> int`. For each target in `evidence(cases())` whose latest
    proposal's `evidence_digest` differs (or that has none):
    - it marks an open `proposed` row `superseded`;
    - it calls `rules_ai.propose`;
    - it stores a `proposed` row, or a `refused` one with problems, or nothing when the model said
      no rule.

    It returns how many targets it asked about. `start()` enqueues the job `propose_rules`, and
    MI0301 refuses when no model is configured.
  - **The check:** `check(row) -> list[str]`. It copies the own layer (if any) to a temp dir,
    writes the table, runs `layers.load([active, temp])`, and returns `[str(error)]` on
    `ValueError` or `KeyError`.
  - **The view:** `read() -> ProposalsView`, containing:
    - `proposals` (status `proposed`): target in words, rows, `why`, the model and invocation,
      evidence cases, `check`, `replay`;
    - `refused` (the latest per target);
    - `in_use`, from the own layer's `rules/learned/*.yml` with their approving rows;
    - `running: bool`;
    - `model: bool`.
  - **The sink:** `approve(id, by)` refuses with MI0300 when the row is not `proposed`, the
    evidence digest has moved, or the check fails. It then:
    - calls `ensure_own_layer()`;
    - writes the file: `declares: rule`, `version: 1`, `decisions: [table]`, under a comment
      header with approved-by, at, the invocation, and the evidence pipeline ids;
    - marks the row `approved`.
  - `reject(id, by)` marks it `rejected`.
  - `withdraw(slug, by)` deletes the file and marks the approving row `withdrawn`.
  - **Routes:**
    - `GET /api/rules/proposals` (`readRuleProposals`);
    - `POST /api/rules/proposals/run` (`proposeRules`);
    - `POST /api/rules/proposals/{id}/approve` and `/reject`;
    - `POST /api/rules/learned/{slug}/withdraw`.
  - **Diagnostics:** MI0300 "a rule proposal cannot be approved as it stands" and MI0301 "no model
    is set to propose rules", both in `diagnostics.yml`.

- [x] **Step 1: Write the failing tests.** The fixture writes three kept drafts (DB rows plus
  `pipeline.yml` files) from the RNA-seq example. Each has a person's tier-4 `producer:align` →
  star, with candidates star and hisat2, and no `read_length`. The model is a fake client that
  replies with one row, `when: {}`, `then: star`.
  - `test_running_proposes_one_rule_with_evidence_check_and_replay`;
  - `test_approving_writes_the_learned_table_and_the_next_build_uses_it`: the next build's align
    decision is tier 3 and cites `kept pipelines`; the file comment names the invocation;
  - `test_running_again_with_no_new_answers_asks_nothing`;
  - `test_a_rejected_proposal_is_not_asked_again_until_evidence_changes` (Review Focus 5);
  - `test_a_new_answer_supersedes_an_open_proposal`;
  - `test_withdrawing_brings_the_question_back`;
  - `test_a_stale_or_failing_proposal_cannot_be_approved` (MI0300);
  - `test_no_model_refuses_to_start` (MI0301);
  - `test_two_hundred_kept_pipelines_read_quickly`: `read()` under 2 s.
- [x] **Step 2: Run** via the test DB, after `make test-db`. Expected: FAIL.
- [x] **Step 3: Implement.** Then run `make client`.
- [x] **Step 4: Run** the tests and `uv run pytest tests/guards -q`. Expected: PASS.
- [x] **Step 5: Commit** `feat: rule proposals: source, storage, job, check and sink (#462)`.

### Task 7: The Learned rules page

**Files:**
- Create: `frontend/src/registry/LearnedRules.tsx`, `useLearnedRules.ts` and
  `LearnedRules.test.tsx`
- Modify: `frontend/src/registry/RegistryTabs.tsx` (a "Learned rules" tab at
  `/registry/learned`) and `frontend/src/app/router.tsx`

**The page:**
- **The header:** a **Propose** button, which shows "asking…" while running and is disabled with
  "No model is set (Settings → Models → Adapting tools)" when none is set.
- **One card per proposal:**
  - the target in words;
  - each row as "When read length ≥ 100 → STAR", with the model's `because` marked "the model's
    reason";
  - the evidence, as pipeline ids with the answer and the person's reason;
  - the check: "Checks pass" or the finding;
  - the replay: changed answers first, then "would settle N past decisions the same way";
  - **Approve** (disabled when the check fails) and **Reject**.
- **"Not proposed"**, listing refused targets with their problems.
- **"In use"**, with **Withdraw**.
- **Empty state:** "No proposals yet. When people answer the same question in three kept
  pipelines, choose Propose."

- [x] **Step 1: Write the failing tests** with a mocked client:
  - a proposal renders its row, the model's reason, evidence, check and replay;
  - Approve posts;
  - a failing check disables Approve;
  - no model disables Propose;
  - the empty state shows;
  - Withdraw posts.
- [x] **Step 2: Run** `npx vitest run src/registry/LearnedRules.test.tsx`. Expected: FAIL.
- [x] **Step 3: Implement,** following `Releases.tsx`'s structure and tokens.
- [x] **Step 4: Run** the tests and `npx tsc -b`. Expected: PASS.
- [x] **Step 5: Commit** `feat: the Learned rules page (#462)`.

### Task 8: Docs and finish

- [x] **Step 1: Write the docs.**
  - A how-to: `docs/how-to/registry/learned-rules.md`, linked from `docs/how-to/index.md`;
  - the CHANGELOG, under comeni-core, mendel-resolver and mendel-api;
  - the journal note;
  - `docs/notes/now.md`, which must stay ≤150 lines;
  - the diagnostics doc, regenerated.
- [x] **Step 2: Run the full checks**, each separately and alone on the DB: `make check`,
  `make guards`, `make slow`, `npx vitest run`, `npx tsc -b`. Expected: all pass.
- [x] **Step 3: Commit** `docs: learned rules (#462)` and tick this plan.
- [x] **Step 4: Run the final review.** A fresh reviewer on the most capable model reviews the
  branch range. Fix Critical and Important findings test-first, and add Minors to #489.

## Deviations

- **Diagnostics.** MI0300 and MI0301 were taken by settings, so a new band was opened:
  MI0500-MI0599. MI0500 means it cannot be approved, and MI0501 means no model.
- **`registry_roots()` and `own_layer()`** are module functions in `settings.py`, beside
  `active_registry()`. The stack digest is `registry.combine()`, and `blueprint.registry_digest`
  delegates to it.
- **A learned row is narrowed** (`table_with(cases=)`). It gains `fact: absent` for each fact
  the existing rows test that none of its answers had. The loader's MD0323 models no unknown
  fact, and would otherwise read the row as dead.
- **No mapping may cross a door.** So a case's facts are `list[FactValue]`, and the existing
  rows are JSON `Text`. Three new free-text fields were added. Only integer, number, boolean and
  enum facts are sent.
- **The evidence digest** uses comeni-core's `digest_of_bytes`, because `mendel-resolver` may not
  import `hashlib` or `json`.
- **"No rule" is stored** as status `no_rule`, so it is not asked again until the evidence moves.
  It is listed under *Not proposed*.
- **`running`** is `jobs.running(JOB_ID)`, set by the route.
- **The browser check** is deferred to the push's end-of-push browser pass.
- **The "done when" tier.** The tier-3 case needs a fact-bearing row (`paired: true`). A `when:
  {}` row is tier 2 by `tier_of_row`.
- **Final review:** seven Important findings were fixed test-first (cb14a430):
  - a malformed row is refused;
  - no `cite` reaches the model;
  - a setting's rule covers one tool;
  - `hit: unique` tables are left alone;
  - approval is judged again against the table in force;
  - the own layer is local (`INSTALLATION`) and leaves the stack when empty;
  - derived facts are not narrowed.

  The Minors are on issue 489.
