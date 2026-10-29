# Forge MVP 3b — forging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A person turns an nf-core module the registry does not hold into an approved draft
layer that loads and conforms, piece by piece, with the AI or by hand, and with a chat beside
it.

**Architecture:** The forging flow is declared on `comeni-flow` (plan 3a) and its rules — who
may issue which command, revisions, re-opening — are pure code in `mendel_forge/forging/`. Item
values are the registry's own models (`InputPort`, `Param`, …), so validation is the registry's
validation. `mendel-api` stores adaptations with append-only revisions, runs AI work on the AI
queue through a declared egress boundary, and assembles the draft layer with `comeni-vendor`,
`layers.load` and `conformance.check`. The frontend adds the Forging tab and the adaptation
page, drawn first on the canvas.

**Tech Stack:** as MVP 1, plus `comeni-flow`; `comeni-ai` (LiteLLM) for model calls.

**Spec:** `docs/superpowers/specs/2026-10-30-forge-3-forging-design.md`. Requires
[plan 3a](2026-10-30-forge-3a-shared-engine.md) merged.

## Global Constraints

- The AI's commands are proposals: `draft`, `revise`, `add`, `propose_removal`. Only a person
  issues decisions: `answer`, `write`, `approve`, `change`, `reject`, `remove`. An approval from
  the AI is refused (`MF0505`).
- Revisions are append-only; nothing overwrites a revision.
- A model reply is validated before anything is stored; an invalid reply is never a proposal.
- Model calls only through the egress boundary `forge_drafting` (flow `FORGE`), only from the AI
  worker, with recorded responses in tests (no live model).
- Nothing is written into the registry or the `registry/` submodule; drafts live under
  `MENDEL_FORGE_CACHE/drafts/<adaptation id>`.
- Disabled actions say *Tests come in MVP 4*, *Pull requests come in MVP 5*, *Releases come in
  MVP 6* (GitHub numbering).
- New codes from `MF0505` (catalogue uses `MF0500`–`MF0504`).

## Review Focus

1. **The AI asked to approve, or replying with `approve`** inside a chat command list: refused,
   nothing changes. Test in Task 2 and Task 6.
2. **Two people (or two tabs) acting on one item at once**: the second command, issued against
   a revision that is no longer current, is refused rather than silently applied. Test in
   Task 5.
3. **A model reply naming a type that exists only in another adaptation's unassembled draft**:
   refused like any unknown id. Test in Task 4.
4. **Abandoning an adaptation another depends on**: the dependant is marked and its affected
   items re-open; nothing is deleted from it. Test in Task 8.
5. **Assembly when the module's licence text is not in the base registry's `LICENSES/`**:
   `comeni_vendor.ops.add` refuses; assembly copies the licence text in from the module's
   declared SPDX id or fails with a coded, shown reason. Test in Task 7.

---

### Task 1: draw the forging panels on the canvas, and agree them

Board 3 draws the parameters piece and a chat. The spec adds interactions it does not draw.

**Files:** the canvas *Forge MVP pages* (`https://claude.ai/artifact/8T3V69ZSUr9wLydNUHrKhS`),
new artboards beside `Forge.dc.html`, each a variant of board 3 in its identity:
- `ForgeStart.dc.html` — a piece not started: **Draft with the AI** / **Write it myself**.
- `ForgeQuestions.dc.html` — the Questions piece: typed questions with options and reasons,
  "something new", and the AI's confident choices shown for approval.
- `ForgeReject.dc.html` — an item rejected: the chat opened on that item, asking what is wrong;
  the person writing a value or asking the AI.
- `ForgeChat.dc.html` — the chat with AI proposals in it: a revised value, an added rule, a
  proposed removal, each as a card with Approve / Change / Reject; a message attached to an item.
- `ForgeAssembled.dc.html` — all approved: the draft's files and the result (loads and
  conforms / what failed and which piece it re-opened).
- `ForgeList.dc.html` — the Forging tab: open adaptations, progress, phase, *drafting…*.
- `Forge390.dc.html` — the page at 390 px (pieces as a stepper, chat below).

- [ ] **Step 1:** Read the canvas index and `Forge.dc.html`; draw the artboards above with the
  same header, sub-tabs, tokens and fonts; publish to the canvas.
- [ ] **Step 2: Stop and ask the operator to look.** Record their changes; redraw once.
- [ ] **Step 3:** Note the agreed boards in the spec's §7 (one line each) and commit.

### Task 2: the forging model and its rules (pure)

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/forging/__init__.py`, `model.py`,
  `rules.py`, `protocol.py`
- Test: `packages/mendel-forge/tests/test_forge_forging_rules.py`

**Interfaces:**
- Produces, in `forging/model.py`:
  - `Piece(StrEnum)`: `QUESTIONS, CONTRACT, PARAMETERS, VOCABULARY, RULES` (in order);
    `PIECES: tuple[Piece, ...]`.
  - `Actor(StrEnum)`: `AI, PERSON, REGISTRY` (`REGISTRY`: a re-forge's starting values,
    taken from the registry's current contract; proposals like the AI's, never decisions).
  - `Move(StrEnum)`: AI — `DRAFT, REVISE, ADD, PROPOSE_REMOVAL`; person — `ANSWER, WRITE,
    APPROVE, CHANGE, REJECT, REMOVE`. `AI_MOVES`, `PERSON_MOVES: frozenset[Move]`.
  - `Status(StrEnum)`: `PROPOSED, APPROVED, REJECTED, REMOVED, REOPENED`.
  - `Revision(item: str, n: int, move: Move, actor: Actor, value: JsonValue | None,
    because: str | None, invocation: str | None, by: str | None)` — `item` is a key such as
    `contract:port:reads`, `parameters:param:min_contig`, `rules:rule:alignment`.
  - `Item(key: str, piece: Piece, revisions: list[Revision], status: Status)`;
    `Item.current -> Revision`.
  - `Adaptation(items: dict[str, Item], depends_on: list[str])` — the pure state the rules act
    on.
  - `Command(move: Move, actor: Actor, item: str, expected: int | None, value: JsonValue |
    None, because: str | None, by: str | None)` — `expected` is the revision number the
    command was issued against (Review Focus 2).
- Produces, in `forging/rules.py`:
  - `apply(state: Adaptation, command: Command) -> Adaptation` (returns a new state; raises
    `Refused` with `MF0505` for an AI decision, `MF0506` for a move not legal in the item's
    status or against a stale `expected`).
  - `DEPENDS: dict[Piece, frozenset[Piece]]` — `CONTRACT → {PARAMETERS, VOCABULARY, RULES}`,
    `VOCABULARY → {RULES}`, `QUESTIONS → {CONTRACT}`; `reopen(state, piece) -> Adaptation`
    marks approved items of dependent pieces `REOPENED`, values kept.
  - `next_piece(state) -> Piece | None` — the first piece not fully approved (strict order).
  - `ready_to_assemble(state) -> bool`.
- Produces, in `forging/protocol.py`: `FORGING: comeni_flow.protocol.Protocol[Phase, Event]`
  with `Phase(StrEnum)`: `ASKING, DRAFTING, REVIEWING, ASSEMBLING, ASSEMBLED, FAILED`, events
  moving between them, `refusal_code="MF0506"`; its diagram generated beside the builder's
  (`tools/generate_protocol_doc.py` renders both).

- [ ] **Step 1: Failing tests**: `test_the_ai_cannot_approve` (MF0505);
  `test_the_ai_can_propose_a_removal_and_only_approval_removes`;
  `test_a_person_written_item_counts_without_a_second_approval`;
  `test_reject_blocks_the_piece_until_changed_or_revised_and_approved`;
  `test_a_stale_command_is_refused` (`expected=1` after revision 2 exists → MF0506);
  `test_changing_an_approved_port_reopens_parameters_and_keeps_values`;
  `test_pieces_go_in_order` (`next_piece` is CONTRACT until QUESTIONS approved);
  `test_the_forging_protocol_is_valid_and_draws` (`to_mermaid(FORGING)` names each phase).
- [ ] **Step 2–4:** run (FAIL), implement, run (PASS); declare `MF0505`, `MF0506` (emitted_by
  forge) in `diagnostics.yml`; regenerate the diagnostics and protocol docs.
- [ ] **Step 5: Commit** (`feat(forge): the forging rules — proposals, decisions, revisions (#364)`).

### Task 3: item values are the registry's models

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/forging/values.py`
- Test: `packages/mendel-forge/tests/test_forge_values.py`

**Interfaces:**
- Produces: `value_model(key: str) -> type[BaseModel]` — `contract:port:*` → `InputPort` or
  `OutputPort` (by a `direction` field), `contract:process` → `ProcessDraft(nf_process,
  nf_include, roles, container, priority, priority_because)`, `contract:nf_inputs` →
  `list[NfInput]`, `parameters:param:*` → `Param`, `parameters:ext_args` → `ContractExtArgs`,
  `vocabulary:type:*` → the vocabulary type declaration model, `vocabulary:measurement:*` → the
  measurement model, `rules:rule:*` → `Decision` (`mendel_resolver.rules.format`),
  `questions:*` → `Question(asks, options: list[Option(id, label, because)], allows_new)`.
  `contract_of(state: Adaptation) -> ModuleContract` assembles the approved contract items.

- [ ] **Step 1: Failing tests**: each key family validates a good value and refuses a bad one;
  `test_contract_of_star_align_items_equals_the_registry_contract` (items built from
  `registry/tools/nf-core/star/align/contract.yml` round-trip to an equal `ModuleContract`).
- [ ] **Step 2–4:** run, implement, run. **Step 5: Commit** (`feat(forge): item values are the
  registry's own models`).

### Task 4: validating a reply against the registry and the module

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/forging/validate.py`
- Test: `packages/mendel-forge/tests/test_forge_validate.py`

**Interfaces:**
- Produces: `Known(types, states, measurements, roles, contracts: frozenset[str], pending:
  frozenset[str])` built by `known(stack: Layers, pending: Layers | None, own: Adaptation)`;
  `check_items(items: dict[str, JsonValue], known: Known, module: ModuleSpec) -> list[Problem]`
  — each problem coded: `MF0507` an id that is not known, pending, or proposed in this
  adaptation; `MF0508` a port or input the module's `main.nf` does not have; `MF0509` a param
  routed to no input or ext key.

- [ ] **Step 1: Failing tests**: `test_an_unknown_type_is_MF0507`;
  `test_a_type_in_another_adaptations_unassembled_draft_is_unknown` (Review Focus 3);
  `test_a_pending_type_is_accepted_and_flagged`; `test_a_port_main_nf_lacks_is_MF0508`;
  `test_a_param_routed_nowhere_is_MF0509`; `test_star_aligns_registry_items_pass`.
- [ ] **Step 2–4**, declare `MF0507`–`MF0509`. **Step 5: Commit**.

### Task 5: tables and the API

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/models.py`; migration
  `…_forge_adaptations.py` (down revision: current head)
- Create: `packages/mendel-api/src/mendel_api/services/forging.py`,
  `packages/mendel-api/src/mendel_api/routes/forge.py` (extend)
- Test: `packages/mendel-api/tests/forge/test_forging_api.py`

**Interfaces:**
- Produces tables: `forge_adaptation` (id, source, path, version, base, phase, depends_on
  JSONB list, started_by, started_at, abandoned_at); `forge_revision` (adaptation, item, n,
  piece, move, actor, value JSONB, because, invocation, by, at; unique (adaptation, item, n));
  `forge_item` (adaptation, item, piece, status, current_n); `forge_message` (adaptation, seq,
  role, item null, content, invocation null, commands JSONB, at). JSON columns registered in
  `shapes.py` with goldens.
- Produces service: `start(source, path, by, reforge: str | None = None) -> AdaptationView`
  (`reforge` = the contract id of an imported tool: its items are seeded as `REGISTRY`
  proposals — *Update to X*, cut first if time runs short), `read(id) -> AdaptationView`,
  `act(id, Command) -> AdaptationView` (loads state, `rules.apply`, appends rows in one
  transaction), `say(id, text, item, by) -> MessageView` (queues `answer_forge_message`),
  `abandon(id, by)`.
- Routes: `POST /forge/adaptations`, `GET /forge/adaptations`, `GET /forge/adaptations/{id}`,
  `POST /forge/adaptations/{id}/commands`, `POST /forge/adaptations/{id}/messages`,
  `POST /forge/adaptations/{id}/assemble`, `DELETE /forge/adaptations/{id}`; `MF0510` no such
  adaptation (404). Operation ids registered in `test_openapi.py`.

- [ ] **Step 1: Failing tests** (`needs_db`): `test_start_creates_an_adaptation_for_the_module`;
  `test_a_reforge_starts_from_the_registry_contract_as_proposals`;
  `test_a_person_command_appends_a_revision`; `test_an_ai_approval_over_http_is_refused`
  (a command body with `actor: ai` → 422 MF0505; the API sets `actor` from the route, never
  the body — the test proves a body cannot claim to be the person or the AI);
  `test_two_commands_against_one_revision_the_second_is_refused` (Review Focus 2);
  `test_abandon_keeps_the_rows`.
- [ ] **Step 2–4**, `make client`. **Step 5: Commit**.

### Task 6: the AI — boundary, replies, jobs

**Files:**
- Create: `packages/comeni-core/src/comeni_core/egress/forge.py` (`ForgeRequest`); modify
  `boundaries.py` (`"forge_drafting": Boundary(ForgeRequest, BoundaryFlow.FORGE)`) and
  `tests/guards/test_egress.py` (the door list)
- Create: `packages/mendel-api/src/mendel_api/forge/prompts/forge.questions.v1.md`,
  `forge.draft.v1.md`, `forge.chat.v1.md`; `packages/mendel-api/src/mendel_api/forge/replies.py`
- Modify: `packages/mendel-api/src/mendel_api/services/forging.py` (jobs),
  `packages/mendel-api/src/mendel_api/ai_worker.py` (functions), `services/models.py`
  (purposes `("forge", "draft")`, `("forge", "chat")` → `MODEL_FORGE`; old forge purposes
  replaced)
- Test: `packages/mendel-api/tests/forge/test_forging_ai.py` with recorded responses under
  `packages/mendel-api/tests/forge/recorded/`

**Interfaces:**
- Produces: `ForgeRequest(EgressPayload)`: `module: ModuleFacts` (name, description, keywords,
  tools, channels, packages, `main_nf: Text`), `known: KnownIds`, `answers`, `approved:
  dict[str, JsonValue]`, `piece`, `messages: list[ForgeTurn]` — no lab data field.
- Produces reply models: `QuestionsReply(questions: list[Question], confident: dict[str,
  JsonValue])`, `DraftReply(items: dict[str, JsonValue], because: dict[str, str])`,
  `ChatReply(text: str, commands: list[AiCommand])` where `AiCommand.move ∈ AI_MOVES` only
  (an `approve` in a reply fails validation — Review Focus 1).
- Produces jobs: `draft_forge_piece(ctx, adaptation_id, piece)`, `answer_forge_message(ctx,
  adaptation_id, seq)`. Each: build `ForgeRequest`, call `Client.generate` with the reply model,
  `validate.check_items`; on problems, one retry with the problems in the prompt, then a
  `forge_message` from the engine stating them; on success, `rules.apply` the AI commands.

- [ ] **Step 1: Failing tests** (recorded): `test_drafting_the_contract_stores_proposals`;
  `test_an_invalid_reply_is_retried_once_then_shown_never_stored`;
  `test_a_chat_reply_with_an_approve_is_refused`; `test_a_chat_add_proposes_a_new_rule`;
  `test_the_payload_carries_no_sample_or_run_data` (egress guard).
- [ ] **Step 2–4.** **Step 5: Commit**.

### Task 7: the draft layer

**Files:**
- Create: `packages/mendel-forge/src/mendel_forge/forging/assemble.py`
- Modify: `services/forging.py` (`assemble(id) -> AssemblyView`)
- Test: `packages/mendel-forge/tests/test_forge_assemble.py`,
  `packages/mendel-api/tests/forge/test_forging_assembly.py`

**Interfaces:**
- Produces: `write_layer(state: Adaptation, base: Path, snapshot_commit: str, out: Path,
  below: list[Path]) -> list[Path]` (vendors the module with `comeni_vendor.ops.add` at the
  catalogue snapshot commit, writes `module.yml`, `contract.yml`, vocabulary files and edited
  shared files, copies the licence text when the base lacks it); `prove(base: Path, below:
  list[Path], draft: Path) -> Proof(loaded: bool, conforms: bool, problems: list[Problem],
  blames: Piece | None)`, using `layers.load([base, *below, draft])` and
  `conformance.check`; `MF0511` did not load, `MF0512` does not conform.

- [ ] **Step 1: Failing tests**: `test_star_align_items_assemble_into_a_layer_that_loads_and_conforms`
  (items from the registry's own star/align; module source from MVP 1's fixtures);
  `test_a_wrong_port_fails_conformance_and_blames_the_contract`;
  `test_a_missing_licence_is_copied_or_refused_with_a_reason` (Review Focus 5);
  `test_assembly_reopens_the_blamed_piece` (API).
- [ ] **Step 2–4**, declare `MF0511`, `MF0512`. **Step 5: Commit**.

### Task 8: pending vocabulary and dependencies

**Files:** `services/forging.py`, `forging/validate.py`
**Interfaces:** `pending_layers(for_id) -> list[Path]` (assembled adaptations this one may
see); `start` and drafting stack them; using a pending id records `depends_on`; `reopen` or
`abandon` of an earlier adaptation marks dependants (`MF0513` *depends on a draft that
changed*) and re-opens items that used its vocabulary.

- [ ] **Step 1: Failing tests**: `test_a_later_adaptation_sees_an_assembled_one_tagged_pending`;
  `test_an_unassembled_adaptation_is_invisible`;
  `test_abandoning_the_earlier_marks_and_reopens_the_later` (Review Focus 4).
- [ ] **Step 2–4.** **Step 5: Commit**.

### Task 9: the pages

**Files:** `frontend/src/registry/forging/` — `ForgingList.tsx`, `Adaptation.tsx`,
`Pieces.tsx`, `PieceItems.tsx`, `Chat.tsx`, `Assembled.tsx`, `useAdaptation.ts`,
`useForgeCommand.ts` (mutation hook in its own file); modify `Selected.tsx` (Forge action),
`RegistryTabs.tsx` (Forging tab live), `router.tsx` (`/registry/forging`,
`/registry/forging/:id`), the MVP wording in `RegistryTabs.tsx`, `Tool.tsx`, `states.tsx`.

- [ ] **Step 1: Failing tests** (Vitest): starting from the catalogue opens the adaptation;
  a piece offers *Draft with the AI* / *Write it myself*; approve/change/reject send the right
  command with `expected`; reject opens the chat on the item; an AI proposal card in the chat
  approves; *drafting…* while a job runs (polls); the assembled view lists files and the result.
- [ ] **Step 2–4.** **Step 5: Browser check** against Task 1's boards at 1440 and 390 px, light
  and dark; overflow measured (no page wider than the viewport). **Step 6: Commit**.

### Task 10: docs and the live forging

- [ ] How-to `docs/how-to/registry/forge-a-tool.md`; changelog; `now.md`; journal; the forging
  protocol's diagram page.
- [ ] **Live**: forge quast on the dev stack with gemma3:12b, then with an API model (Settings →
  forge purpose). Record for each: reached *loads and conforms* or not, revisions needed, AI
  failures. In the journal.
- [ ] `make check`, `make guards`; tick this plan with deviations. Commit.
