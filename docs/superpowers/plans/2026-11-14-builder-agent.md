# The Builder Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the builder's scripted flow with an agent that builds the pipeline through typed engine tools, talks in an ordinary chat while it works, and is reachable by other agents over MCP.

**Architecture:** One tool layer in `mendel-api` (`mendel_api/agent/`) wraps the engine's operations: reads, `DecisionChange` writes through `services.changes.apply`, resolve, compile, and a question to the person. An agent loop on the AI worker calls the model with those tools until it replies or asks; its messages and tool calls are the session's turns. An MCP server mounted in the API serves the same tools behind a token. The phase machine, goal card, gap and step walks and their cards are deleted.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy + Alembic, arq, LiteLLM 1.105 (`comeni-ai`), the Python MCP SDK (`mcp`), React + TypeScript + TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-11-14-builder-agent-design.md`

## Global Constraints

- Build on a new branch from `main` after PR #491 merges: `feat/builder-agent`.
- The agent writes no pipeline code; the compiler wires modules and emits Nextflow.
- Every agent write goes through `services.changes.apply` with `actor="model"`; every MCP write likewise, with `who` = the client's name.
- Tests never call a live model. The agent loop is tested with a scripted fake transport.
- Pure packages (`comeni-core`, `mendel-resolver`, `mendel-compiler`, `mendel-authoring`) do no network I/O.
- An AI choice is tier 4 with source `model`; it stays flagged for review. Review never blocks compile, Run, keep or publish.
- Rule learning (#462) uses only answers a person gave or reviewed.
- The MCP endpoint requires `Authorization: Bearer $MENDEL_MCP_TOKEN` in every environment; the production overlay refuses to start without the token.
- Level 0 allows the new `builder_agent` egress door and the `agent` crossing; guard loosenings for it are recorded in `tests/fixtures/guard-ledger.md`.
- A contract's `does:` is context for the agent, never shown in the chat as written.
- No backward compatibility before v0.1.0: delete retired code and stored shapes; migrate stored rows.
- Run checks separately before each commit; `make check` and `make guards` once per task group, alone on the test database (port 5442). Never bare `pytest` with the dev database up.
- Frontend source must not contain `#` followed by hex digits (write "issue 462").
- Generated API clients are rebuilt with `make client`, never edited by hand.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The model calls a tool with arguments the engine refuses** (an undeclared type, a value a measurement refuses): the turn continues, with the coded refusal returned to the model as the tool's result, never an exception that fails the turn. Pinned in Task 6.
2. **The person edits the canvas while a turn runs:** the agent's next write against the old decision revision is refused as stale, the agent re-reads and the person's edit stands. Pinned in Task 7.
3. **The model loops** (calls tools forever or repeats one call): the turn stops at the step limit with a message saying so, and the session stays usable. Pinned in Task 8.
4. **The provider fails mid-turn** (timeout, refusal, malformed tool call): the turn is marked failed with its code, the chat says so and offers Retry, and nothing stays "working". Pinned in Task 8.
5. **An MCP request without the token, or with the wrong one:** refused with 401 before any tool runs. Pinned in Task 10.

---

### Task 1: Branch, and check tool calling on the subscription route

**Files:**
- Create: `docs/notes/agent-tool-calling-check.md`

**Interfaces:**
- Produces: a ruling recorded in the ledger and this note — `NATIVE` (LiteLLM `tools=` works through `chatgpt/`) or `JSON_ACTIONS` (fallback). Task 2 reads it.

- [ ] **Step 1:** After PR #491 merges, `git -C <repo> switch main && git -C <repo> pull && git -C <repo> switch -c feat/builder-agent`. Commit the spec and this plan on it.
- [ ] **Step 2:** On the dev stack, from the `ai-worker` container, call `litellm.completion(model=<the builder's configured chatgpt/ model>, messages=[{"role":"user","content":"What is 2+2? Use the add tool."}], tools=[{"type":"function","function":{"name":"add","parameters":{"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}}}])` once.
  Expected: `response.choices[0].message.tool_calls[0].function.name == "add"`.
- [ ] **Step 3:** Write the result (the response shape, model name, and `NATIVE` or `JSON_ACTIONS`) into `docs/notes/agent-tool-calling-check.md` and commit it.

---

### Task 2: A conversation with tools in `comeni-ai`

**Files:**
- Create: `packages/comeni-ai/src/comeni_ai/agent.py`
- Create: `packages/comeni-ai/tests/test_agent.py`
- Modify: `packages/comeni-ai/src/comeni_ai/client.py` (the LiteLLM transport gains `converse`)

**Interfaces:**
- Consumes: Task 1's ruling.
- Produces:
  - `ToolSpec(name: str, description: str, parameters: dict)` (frozen pydantic model; `parameters` is a JSON schema).
  - `ToolCall(id: str, name: str, arguments: dict)`.
  - `AgentReply(text: str, calls: list[ToolCall], usage: Usage | None)`.
  - `AgentMessage = dict` in the OpenAI chat shape (`role`: `system`|`user`|`assistant`|`tool`).
  - `class AgentTransport(Protocol): def converse(self, access: ModelAccess, messages: list[dict], tools: list[ToolSpec]) -> AgentReply`.
  - `LiteLLMTransport.converse(...)` (native `tools=`, or the JSON action protocol per Task 1, chosen inside the transport; callers do not know which).
  - `ScriptedAgentTransport(replies: list[AgentReply])` for tests: returns the replies in order, records each `messages` it was sent in `.sent`, raises `AssertionError("the script ran out")` when called past the end.

- [ ] **Step 1: Write the failing tests** in `test_agent.py`:
  - `test_a_scripted_transport_answers_in_order_and_keeps_what_it_was_sent` — two replies, two calls; `.sent[1]` is the second call's messages; a third call raises "the script ran out".
  - `test_a_native_tool_call_is_read_into_a_tool_call` — feed `LiteLLMTransport._reply_of(<a litellm-shaped response dict with one tool call>)`; assert `AgentReply.calls == [ToolCall(id="c1", name="add", arguments={"a": 2, "b": 2})]`.
  - `test_malformed_tool_arguments_are_a_coded_refusal` — arguments `"{not json"`; assert `AgentReply.calls[0].arguments == {}` and `reply.text` is empty and a `refused: MA0005 …`-style marker is set on the reply (`AgentReply.refusal: str | None`).
- [ ] **Step 2:** `uv run pytest packages/comeni-ai/tests/test_agent.py -q` — FAIL (module missing).
- [ ] **Step 3:** Implement `agent.py` and `LiteLLMTransport.converse` + `_reply_of`. Add `refusal: str | None = None` to `AgentReply`.
- [ ] **Step 4:** Run the tests — PASS.
- [ ] **Step 5:** Commit: `feat: a conversation with tools in comeni-ai, with a scripted transport for tests`.

---

### Task 3: The AI's authorship reaches the pipeline

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/goal/asked.py` (`ProducerPin`, `ParamOverride`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`Why`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py` (`_by_person`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (the parameter override at about line 742)
- Modify: `packages/mendel-api/src/mendel_api/services/decisions.py` (`goal()` carries `actor_kind` and the reason into the pins and overrides)
- Test: `packages/mendel-resolver/tests/test_model_choices.py`, `packages/mendel-api/tests/authoring/decisions/test_model_authorship.py`

**Interfaces:**
- Produces:
  - `ProducerPin.by: Literal["person", "model"] = "person"`, `ProducerPin.because: Line = ""`; same two fields on `ParamOverride`. Both excluded from serialisation when default.
  - `Overrode(rule: str, value: ParamValue, cite: Line = "")` and `Why.overrode: Overrode | None = None` (excluded when `None`).
  - A model pin resolves to `Why(tier=AMBIGUOUS, source=ValueSource.MODEL, reason="the AI chose {contract} over {engine}, the engine's pick: {engine reason}; because {because}")`; a model parameter to `Why(tier=AMBIGUOUS, source=MODEL, reason="the AI set {value}; because {because}", overrode=Overrode(rule=<decision key>, value=<rule value>, cite=<citation>))` when a rule had decided it.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_model_pin_is_the_ais_choice_and_stays_flagged` — goal with `ProducerPin(site=<alignment site>, contract=HISAT2, by="model", because="less memory")`; resolve; the step's `why.source == ValueSource.MODEL`, `why.tier == Tier.AMBIGUOUS`, `"the AI chose" in why.reason and "less memory" in why.reason`; `needs_review()` includes the step.
  - `test_a_model_setting_over_a_rule_keeps_the_rules_value_beside_it` — a rule sets `star_align.sjdbOverhang` to 149; a `ParamOverride(name="sjdbOverhang", value=100, by="model", because="test")`; the setting's `why.overrode.value == 149` and `why.source == MODEL`.
  - `test_a_persons_pin_reads_as_before` — no `by`; the serialised goal has no `by`/`because` keys and the reason starts "you chose".
  - `test_the_decision_records_actor_reaches_the_goal` (API, test DB) — `changes.apply(draft, DecisionChange(kind="pin", ..., actor="model", ...), who="builder-agent")`; `decisions.goal(draft).constraints.producers[0].by == "model"`.
- [ ] **Step 2:** Run them — FAIL.
- [ ] **Step 3:** Implement. Carry the decision record's reason into `because` (the change's `heard` text where the agent gave one; Task 7 supplies it).
- [ ] **Step 4:** Run the four tests, then `uv run pytest -q packages/mendel-resolver packages/comeni-core packages/mendel-compiler -m "not slow"` and the shape goldens (`packages/mendel-api/tests/golden`). If a stored shape changed, bump its version with a migration and an upgrader test, as `b7e3c1d9f046_accepted_types_on_ports.py` did.
- [ ] **Step 5:** Commit: `feat: an AI choice is recorded as the AI's, tier 4, with the rule it overrode beside it`.

---

### Task 4: `does:` on a contract

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/declared/contract.py`
- Modify: `packages/mendel-forge/src/mendel_forge/` drafting prompt for contracts (the forge drafts `does:`)
- Test: `packages/comeni-core/tests/test_contract_does.py`
- Docs: `docs/reference/` contract format page (the one documenting `ModuleContract` fields)

**Interfaces:**
- Produces: `ModuleContract.does: Line | None = None` (one line, ≤ 200 characters, excluded when `None`).

- [ ] **Step 1: Write the failing tests:** `test_a_contract_may_say_what_this_step_does` (loads with `does: Index a FASTA reference so tools can read regions of it`, `contract.does` equals it); `test_does_is_one_line` (a value containing a newline is refused with an MD code, reusing the code `Line` already raises).
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement; add `does:` to the forge's contract drafting instruction. **Step 4:** Run, plus `uv run mendel lint --registry registry` — PASS. **Step 5:** Commit: `feat: a contract may say in one line what its step does, for the agent`.

---

### Task 5: The `builder_agent` door and the `agent` crossing

**Files:**
- Create: `packages/comeni-core/src/comeni_core/egress/agent.py`
- Modify: `packages/comeni-core/src/comeni_core/egress/boundaries.py`
- Modify: `packages/mendel-api/src/mendel_api/services/protection.py`
- Modify: `tests/guards/test_egress.py`, `tests/support/egress.py`, `tests/fixtures/guard-ledger.md`, `docs/explanation/invariants.md`
- Test: `tests/guards/test_egress.py`

**Interfaces:**
- Produces:
  - `AgentToolResult(tool: str, ok: bool, result: AgentView | None, refusal: Line | None)` and `AgentView`, a discriminated union of the tool layer's view models (Task 6 defines the members; this task declares the union with one placeholder member `TextView(text: str)` that Task 6 replaces).
  - `BOUNDARIES["builder_agent"] = Boundary(AgentToolResult, BoundaryFlow.PIPELINE)`.
  - `Crossing.AGENT = "agent"` allowed at `level_0`.

- [ ] **Step 1: Write the failing guard tests:** `test_the_builder_agent_door_is_declared` (in `egress.PAYLOADS`); `test_the_agent_door_is_loosened_only_at_level_0` (the free-text/sample allowances apply to `AgentToolResult` and to no other door); `test_the_agent_crossing_is_allowed_at_level_0_only`.
- [ ] **Step 2:** Run `make guards` — FAIL. **Step 3:** Implement; add the loosening as a named exception in `tests/support/egress.py` scoped to this door, and a ledger entry giving the operator's decision (2026-11-14, level 0) and what fails without it. **Step 4:** `make guards` — PASS; prove the scope by temporarily applying the exception to `goal_extraction` and seeing the guard fail (record in the ledger). **Step 5:** Commit: `feat: the builder agent's tool results leave through one declared door, loosened at level 0`.

---

### Task 6: The tool layer: reads

**Files:**
- Create: `packages/mendel-api/src/mendel_api/agent/__init__.py`, `agent/tools.py` (the registry), `agent/views.py` (the view models), `agent/read.py`
- Test: `packages/mendel-api/tests/agent/test_read_tools.py`

**Interfaces:**
- Consumes: `AgentView` union (Task 5) — replace its placeholder with the views here.
- Produces:
  - `Tool(name: str, description: str, input: type[BaseModel], run: Callable[[ToolContext, BaseModel], AgentView], writes: bool)`; `TOOLS: dict[str, Tool]`; `def spec_of(tool: Tool) -> ToolSpec`.
  - `ToolContext(draft_id: str, session_id: str | None, who: str, expected_revision: int)`.
  - `def call(ctx: ToolContext, name: str, arguments: dict) -> AgentToolResult` — validates `arguments` against `tool.input`; a validation error or a coded `ValueError` becomes `AgentToolResult(ok=False, refusal=<message>)`; never raises for those.
  - Read tools (each returns a view with ids **and** names in words): `read_goal`, `read_pipeline` (steps, wiring, open values, AI choices not reviewed), `read_step(node)` (contract, `does:`, tool description, every setting with reason, tier, citation, rules that fired), `find_tools(type_id)` (who makes / reads a type), `read_rules(role)` (rows, conditions, citations), `read_facts` (facts and samples; sample names allowed at level 0), `what_is_needed` (the gap walk, `services.gaps.gaps`, as a list).

- [ ] **Step 1: Write the failing tests** (test DB; build a session from `examples/rnaseq.yml` through `decisions.import_goal`):
  - `test_every_tool_has_a_schema_the_model_can_read` — each `spec_of(t).parameters` is a JSON object schema; names are unique.
  - `test_read_step_says_what_decided_each_setting` — `read_step("star_align")` has `sjdbOverhang` with `tier == 3`, a non-empty citation, and the contract's `does` (or `None`).
  - `test_a_refused_argument_is_a_result_not_an_exception` (Review Focus 1) — `call(ctx, "read_step", {"node": "no_such_step"})` returns `ok=False` with a refusal naming the step.
  - `test_reads_name_types_in_words` — `read_pipeline` gives `"gene annotation (GTF)"` beside `annotation.gtf`.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement. **Step 4:** Run — PASS. **Step 5:** Commit: `feat: the builder agent's read tools`.

---

### Task 7: The tool layer: changes, build, compile, ask

**Files:**
- Create: `packages/mendel-api/src/mendel_api/agent/change.py`, `agent/build.py`, `agent/ask.py`
- Test: `packages/mendel-api/tests/agent/test_change_tools.py`

**Interfaces:**
- Consumes: `Tool`, `ToolContext`, `call` (Task 6); model authorship (Task 3).
- Produces:
  - Change tools, each building a `DecisionChange(actor="model", heard=<because>)` and calling `changes.apply(ctx.draft_id, change, who=ctx.who)` after checking `ctx.expected_revision` against the draft's decision revision (a mismatch returns `ok=False, refusal="MI0201: the pipeline changed since you read it; read it again"`): `want(type_id, states, because)`, `have(type_id, present, because)`, `set_fact(subject, value, because)`, `choose_tool(type_id, states, contract, because)`, `exclude_tool(...)`, `switch_role(role, on, because)`, `switch_input(contract, port, state, because)`, `set_value(name, value, because)`, `keep_whole(contract, whole, because)`, `undo(kind, subject)`.
  - `resolve()` → view: steps added/removed/changed, values still open, every rule that fired (decision key, result, reason, citation); it also projects the canvas (the existing `project(db, row, fresh)` path), so the canvas follows the agent.
  - `compile()` → view: `main_nf`, `nextflow_config`, or the coded refusal.
  - `ask(question, shape)` where `shape` is one of `options(list[str])`, `number(unit)`, `yes_no`, `upload(type_id)`, `text` → view `Asked(id)`; marks the turn as waiting for the person.
  - Every successful write bumps `ctx.expected_revision` to the new revision.

- [ ] **Step 1: Write the failing tests:**
  - `test_a_tool_choice_is_written_as_the_ais` — `choose_tool` for alignment = HISAT2; `decisions.read(draft)` shows the pin with `actor_kind == "model"`; after `resolve()`, the step's `why.source == "model"`.
  - `test_a_stale_write_is_refused_and_the_persons_edit_stands` (Review Focus 2) — read, then a person's `changes.apply(... actor="person")`, then the agent's `set_value` with the old revision: `ok=False`, refusal starts `MI0201`; the person's value is the one in `decisions.read`.
  - `test_resolve_reports_the_rules_that_fired` — after `want counts.matrix` and the facts, `resolve()` lists the alignment rule with its citation.
  - `test_compile_returns_the_nextflow` — `"workflow {" in compile().main_nf`.
  - `test_an_undeclared_type_is_refused_with_its_code` — `want("no.such.type")` → `ok=False`, `"MI0204" in refusal`.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement. **Step 4:** Run — PASS. **Step 5:** Commit: `feat: the builder agent's change, build, compile and ask tools`.

---

### Task 8: The agent loop on the AI worker

**Files:**
- Create: `packages/mendel-api/src/mendel_api/agent/loop.py`, `agent/prompt.md` (the system prompt), `agent/thread.py` (turn blocks)
- Modify: `packages/mendel-api/src/mendel_api/ai_worker.py` (add the job; update the docstring: the worker runs the agent's engine tools in-process)
- Modify: `packages/mendel-api/src/mendel_api/settings.py` (`agent_max_steps: int = 24`, `agent_max_tokens: int = 200_000`)
- Test: `packages/mendel-api/tests/agent/test_loop.py`

**Interfaces:**
- Consumes: `AgentTransport`, `ScriptedAgentTransport`, `ToolSpec` (Task 2); `TOOLS`, `call` (Tasks 6–7).
- Produces:
  - Turn blocks (stored in `PipelineAuthoringTurn.blocks`, discriminated by `kind`): `message(text)`, `tool(name, label, ok, summary)` (`label` is a short sentence: "Read the alignment rule"), `question(id, text, shape)`, `limit(reason)`, `failure(code, text)`.
  - `async def run_builder_turn(ctx: dict, session_id: str, seq: int) -> str` — the arq job. Writes the assistant turn's blocks as it goes (each tool call appended and committed before the next model call, so the page's poll shows progress); ends when the model replies without calls, calls `ask`, or a limit is hit; records one `ai_invocation` per model call with `agent="builder"`, `purpose="agent"`.
  - `def transport_for(access) -> AgentTransport` — the seam tests monkeypatch.

- [ ] **Step 1: Write the failing tests** (scripted transport; test DB):
  - `test_a_turn_calls_tools_then_replies` — script: a `read_pipeline` call, then text "Here is what I built". The turn's blocks are `[tool(read_pipeline, ok=True), message("Here is what I built")]`; state `answered`; one `ai_invocation` per model call (2).
  - `test_a_tool_refusal_goes_back_to_the_model` (Review Focus 1) — script: `want("no.such.type")`, then text. The second call's messages include a tool message containing `MI0204`; the turn is `answered`.
  - `test_the_turn_stops_at_the_step_limit` (Review Focus 3) — `agent_max_steps=3`, a script of four tool calls; the last block is `limit(...)`, state `answered`, and a new person message starts a new turn normally.
  - `test_a_provider_failure_fails_the_turn_with_its_code` (Review Focus 4) — the transport raises the client's timeout; the turn is `failed` with a `failure` block carrying the code; no turn stays `pending`.
  - `test_asking_ends_the_turn_and_the_answer_starts_the_next` — script: `ask("Do you have a GTF?", yes_no)`; the turn ends with a `question` block; posting the answer (Task 9's route) enqueues the next turn.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement; write `prompt.md` for the role in the spec (builds pipelines with this engine's tools; explains choices in its own words; teaches; never claims a value it did not get from a tool; treats rules as advice and gives a reason when overriding; says what it did with the AI's marks in mind). **Step 4:** Run — PASS. **Step 5:** Commit: `feat: the builder agent's loop on the AI worker`.

---

### Task 9: The API for the agent's chat, and the old flow's routes go

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/routes/authoring.py` (new routes; delete the stage routes)
- Modify: `packages/mendel-api/src/mendel_api/services/session.py` (the session view: thread, turn state, AI choices not reviewed)
- Test: `packages/mendel-api/tests/agent/test_agent_routes.py`

**Interfaces:**
- Consumes: `run_builder_turn` (Task 8).
- Produces (all under `/api/pipeline/authoring`):
  - `POST /` `{prompt}` → creates a draft and session, writes the person's turn, enqueues the agent turn → `AuthoringSession`.
  - `POST /{id}/messages` `{text}` → as above for an existing session (waits behind a running turn as today).
  - `POST /{id}/questions/{question_id}` `{value}` → the answer as the person's turn, then the next agent turn.
  - `POST /{id}/turns/{seq}/retry` → re-enqueues a failed turn.
  - `POST /{id}/reviewed` `{nodes: list[str] | "all"}` → records the person's review of AI choices.
  - `GET /{id}` → `AuthoringSession` with `turns` (blocks as in Task 8), `graph`, `canvas`, `ai_unreviewed: list[{node, what}]`, `working: bool`.

- [ ] **Step 1: Write the failing tests:** `test_starting_writes_the_persons_turn_and_queues_the_agent`; `test_answering_a_question_queues_the_next_turn`; `test_retry_requeues_only_a_failed_turn` (409 for an answered one); `test_reviewing_clears_the_ai_marks` (`ai_unreviewed` empties after `"all"`); `test_the_scripted_flow_routes_are_gone` (`/proposals/{id}/decide`, `/gaps`, `/goal` return 404).
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement; `make client`. **Step 4:** Run — PASS. **Step 5:** Commit: `feat: the agent chat's API; the scripted flow's routes are removed`.

---

### Task 10: The MCP server

**Files:**
- Create: `packages/mendel-api/src/mendel_api/agent/mcp.py`
- Modify: `packages/mendel-api/src/mendel_api/main.py` (mount at `/api/mcp`), `packages/mendel-api/pyproject.toml` (`mcp` dependency; `uv lock`), `.env.example` (`MENDEL_MCP_TOKEN=`), `docker-compose.yml`, `docker-compose.prod.yml` (`MENDEL_MCP_TOKEN: ${MENDEL_MCP_TOKEN:?Set MENDEL_MCP_TOKEN to serve MCP}`)
- Test: `packages/mendel-api/tests/agent/test_mcp.py`, `tests/repo/test_deployment_boundaries.py`
- Docs: `docs/how-to/` page "Build a pipeline from another agent over MCP"

**Interfaces:**
- Consumes: `TOOLS`, `call` (Tasks 6–7).
- Produces: MCP tools of the same names and schemas, plus `open_draft(draft_id | None, name)` (creates when `None`) which every other tool requires first in the MCP session; `ask` returns the question as the tool result for the client's own user.

- [ ] **Step 1: Write the failing tests:** `test_without_the_token_nothing_runs` and `test_a_wrong_token_is_refused` (Review Focus 5, 401); `test_mcp_lists_the_same_tools_as_the_agent`; `test_an_mcp_write_is_recorded_with_the_clients_name` (`who` = the MCP client name, `actor_kind == "model"`); `test_production_refuses_to_serve_mcp_without_a_token` (compose config).
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement. **Step 4:** Run — PASS. **Step 5:** Commit: `feat: the engine's tools over MCP, behind a token`.

---

### Task 11: The scripted flow is deleted

**Files:**
- Delete: `packages/mendel-api/src/mendel_api/stages/` (keep sample upload and characterisation, moved to `mendel_api/agent/samples.py` and called by the `upload` answer shape), `services/authoring_jobs.py` (except `characterise_sample`, moved beside the loop), `services/authoring_ai.py`, the builder prompts under `mendel_api/authoring/prompts/`, the authoring protocol and commands in `packages/mendel-authoring/src/mendel_authoring/` (`protocol.py`, `commands.py`, `pacing.py`, `progress.py`, `wrapup.py`, `plan.py`, `forks.py`, `alternatives.py`, `amend.py`) and their tests; `comeni_core/egress/authoring.py` and `egress/resolution.py` with their doors.
- Modify: `ai_worker.py` (remove the retired jobs), `services/proposals.py` (#462 evidence: only person-given or person-reviewed answers), CLAUDE.md (the boundary sentence and the AI-points bullet), `docs/explanation/architecture.md`, `docs/explanation/invariants.md`.
- Migration: drop `pipeline_authoring_proposal` and the retired session columns; migrate stored turns (old blocks become one `message` block of their text).
- Test: `packages/mendel-api/tests/test_rule_proposals.py` (add), guards.

**Interfaces:**
- Keeps: `services.decisions`, `services.changes`, `services.gaps`, `services.blueprint.resolve`, review tracking, sample upload and characterisation.

- [ ] **Step 1: Write the failing test:** `test_rules_learn_only_from_answers_a_person_gave_or_reviewed` — a draft whose alignment was chosen by the model and not reviewed is not evidence; after `POST /reviewed`, it is.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Delete the code; implement the evidence filter; write the migration; update CLAUDE.md to say "the engine validates, routes, applies rules as advice and emits; the agent chooses, recorded as the AI's" and keep the doc-size budget (`make doc-sizes`). **Step 4:** `make check`, `make guards`, `make doc-sizes` — PASS, alone on the test DB. **Step 5:** Commit: `refactor: the scripted builder flow is deleted; the agent replaces it`.

---

### Task 12: The chat in the browser

**Files:**
- Create: `frontend/src/build/living/AgentThread.tsx`, `AgentThread.test.tsx`, `ToolTrail.tsx`, `AgentQuestion.tsx`
- Modify: `frontend/src/build/living/ChatPanel.tsx`, `LivingSurface.tsx`, `LivingNode.tsx` (the AI mark), `useAuthoringSession.ts`
- Delete: the stage cards in `frontend/src/build/living/blocks/` (goal, gap, step proposal, pacing, handover, change set) and their tests; `Describe` stage branches.

**Interfaces:**
- Consumes: the session view (Task 9).
- Produces: `AgentThread({ turns, working, onAnswer, onRetry })`; `ToolTrail({ tools, live })` — live lines while `working`, folded into one "How I got here · N steps" line once the turn has a `message`; `AgentQuestion({ question, onAnswer })` rendering `options` as buttons, `number` as a field with its unit, `yes_no`, `upload` (the existing `SampleUpload`), `text`; a node chosen by the AI shows "chosen by the AI · review" and the step sheet has "Looks right".

- [ ] **Step 1: Write the failing tests:** `shows each tool call while the turn runs, then folds them under How I got here`; `draws an agent question's options as buttons and sends the choice`; `offers Retry on a failed turn`; `marks a step the AI chose until it is reviewed`; `keeps the chat height fixed: a new message does not resize the rail` (asserts the rail's style has a fixed height and `overflow-y: auto`).
- [ ] **Step 2:** `cd frontend && npx vitest run src/build/living/AgentThread.test.tsx` — FAIL. **Step 3:** Implement; remove the deleted cards' imports. **Step 4:** `npx vitest run && npx tsc -b` — PASS. **Step 5:** Commit: `feat: the builder's chat is the agent's thread, with its working trail and questions`.

---

### Task 13: Keep and publish say what the AI chose

**Files:**
- Modify: the keep and publish routes and their frontend dialogs (`frontend/src/build/living/LivingHeader.tsx`, the keep/publish service in `mendel_api/services/drafts.py`)
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py` (`Pipeline.ai_choices: list[AiChoice]` with `node`, `what`, `reviewed: bool`, excluded when empty)
- Test: `packages/mendel-api/tests/agent/test_keep_review.py`, the header's vitest file

**Interfaces:**
- Produces: `pipeline.yml` lists each AI choice and whether it was reviewed; keeping and publishing never refuse for unreviewed choices; the dialog shows "N choices by the AI, not reviewed" and one "Looks right" (calls `POST /reviewed {"nodes": "all"}`).

- [ ] **Step 1: Write the failing tests:** `test_keeping_with_unreviewed_ai_choices_works_and_records_them` (`ai_choices[0].reviewed is False`); `test_looks_right_marks_every_choice_reviewed`; vitest `shows how many AI choices are not reviewed before keeping`.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement; shape golden and migration if the stored artifact shape changes. **Step 4:** Run — PASS. **Step 5:** Commit: `feat: a kept pipeline records what the AI chose and whether anyone reviewed it`.

---

### Task 14: Checks, the walk, and the issues

- [ ] **Step 1:** `make check`, `make guards`, `make verify` (resolution and the saved schema changed), `cd frontend && npx vitest run && npx tsc -b` — all PASS, alone on the test DB.
- [ ] **Step 2:** Restart `api`, `mendel-worker`, `ai-worker`; walk the RNA-seq goal and the QUAST goal in the browser at 1440×900 and 390 wide, light and dark; the operator rates the chat live. File every defect as a sub-issue of #463.
- [ ] **Step 3:** Close #497 and #493 with what replaced them; tick #494 and #496's chat items; leave #499 (plan 2) open.
