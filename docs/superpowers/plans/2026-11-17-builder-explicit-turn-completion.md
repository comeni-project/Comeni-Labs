# Plan: explicit builder turn completion

Status: implemented; AI worker restarted on 2026-11-17 at 13:12 UTC with builder.agent.v2.
Full verification stopped at the operator’s request; do not infer a full-suite pass.
GitHub issue creation was waived by the operator.

Spec: [Explicit completion of builder-agent turns](../specs/2026-11-17-builder-explicit-turn-completion.md).

## 1. Establish the regression before changing behavior

- Read `tests/README.md` and the guard-ledger evidence rules (already inspected for planning).
- Confirm Makefile test URLs target the disposable server on `127.0.0.1:5442`, databases
  `mendel` and `wiener`, and inspect any explicit test/admin URL overrides without printing
  credentials. Never run truncating fixtures against the development database.
- Add a scripted case in `packages/mendel-api/tests/agent/test_loop.py`: the exact reported
  “I'm checking…” response, then `read_data` and a successful existing terminal `ask`.
  Assert the second model request occurs, contains the exact fixed reminder, and retains the
  first text as narration. This uses an existing terminal tool so a failure cannot merely be
  caused by the not-yet-implemented `reply` tool.
- Run that case against the current loop; retain the failing assertion and command as evidence.
  Append its before/after evidence to `tests/fixtures/guard-ledger.md` only after observing both.

## 2. Declare and validate `reply`

- Add `agent/reply.py`, register it through `agent/tools.py::_load`, and test tool discovery,
  nonblank bounded `message` validation, multiline preservation and refused inputs.
- Add `RepliedView` / its discriminator to `comeni_core.egress.agent::AgentView`; cover the
  declared payload through the egress guards rather than returning an undeclared dict.
- Confirm the shared MCP surface returns the typed result without trying to terminate an
  unrelated server-side turn. No writes to pipeline decisions belong in this tool.

## 3. Replace heuristic completion in `run_turn`

- Add a successful `reply` branch beside the existing successful `ask` branch. Render its
  validated message as `AgentMessage(narration=False)` and finish ANSWERED.
- Replace `nudged` / `_ANNOUNCES` with the consecutive-slip counter and the exact fixed reminder.
  Preserve invocation records, narration, prior tool lines and running-line cleanup.
- Declare the available protocol-failure diagnostic (proposed `MI0227`) and emit it with
  `coded()` in a FAILED Notice after two consecutive slips. Successful tool calls reset the
  counter; refused calls do not. Keep limits reachable after slips and ordinary tool rounds.
- Update `prompt.md` persistence/completion instructions and consistently version the new
  protocol in prompt/invocation metadata. Keep nonterminal narration and `ask` behavior intact.
- Tests: terminal reply, malformed reply, two slips, reset by a successful tool, refused tool
  without reset, empty tool-free response, ask, and both step/token LIMIT cases. Assert the
  first terminal call in a batch prevents subsequent tools from executing.

## 4. Add optional provider enforcement

- Extend `comeni_ai.agent::AgentTransport.converse` and `ScriptedAgentTransport` with an optional
  required-tool request; preserve defaults for callers not opting in. Update test seams.
- Implement capability-aware forwarding in `comeni_ai.client::LiteLLMTransport.converse`.
  Verify installed LiteLLM capability/exception APIs before selecting the narrow detection.
  Omit for unsupported/custom-local providers; handle a specific tool-choice capability
  rejection with at most one fallback request. No broad catch-and-retry of provider errors.
- Mock LiteLLM to assert required forwarding, omission, narrow fallback, and unchanged error
  handling. Record transport policy identity in provenance without leaking configuration or
  credentials into model payloads. `mendel-ai` remains a compatibility shim; preserve its
  identity/import tests rather than creating a second transport implementation.

## 5. Migrate scripts and protect recording/replay

- Update prose endings in `tests/agent/test_loop.py`, `test_agent_routes.py`,
  `test_keep_review.py` and any other scripted turn fixtures to explicit reply calls. Replace
  regex-specific expectations with the structural slip assertions; keep genuine transport-only
  plain-text parser tests where text is still a valid transport result.
- Check `comeni-ai/tests/test_agent.py`, mendel-ai compatibility tests, egress fixtures and
  `frontend/src/build/living/AgentThread.test.tsx` as applicable. Existing normal message and
  failed-turn Retry rendering should be reusable without product UI changes.
- Verify saved model text/calls and decisions are retained and replay paths use recorded
  decisions without live calls. Do not invent a new model-driven replay path.
- Run `make client` for the changed egress/API union and review generated diffs.

## 6. Verification and handoff

Run `make test-db && make test`, `make check`, and `make guards` after confirming isolated URLs.
Record exit codes, test counts/skips and each failure's cause. A failed aggregate command does
not establish that its later stages ran. Report known frontend token/reported failures in
preferences and `analysis/data/Start.tsx`; leave them alone. Run focused fake-transport tests
first to diagnose regressions quickly, without any live-model requests.

Report the green/red guard evidence and remaining failures faithfully. Restart the deployed
`ai-worker` after approved implementation so its imported loop and prompt are refreshed; do
not restart it for this documentation-only proposal. Do not commit unrelated working-tree edits.

## Execution status

The original regression failed as recorded in the guard ledger; the focused run then passed
83 tests. A broader focused run passed 276 tests with one tool-description budget failure;
the reply description was subsequently shortened without raising the budget. `make test-db`,
`make client`, and `make guards` completed (84 guard tests passed). `make test` did not complete
and `make check` was not run before the operator requested no more tests. Whole-tree Ruff also
reported existing import-order / line-length problems in main.py and routes/data.py, outside
this protocol change. The AI worker was restarted and its startup, v2 protocol and registered
reply tool checked directly. No live model request was sent for verification.

## Operator override, 2026-11-17

The operator requested removal of the blocking slip rule after repeated MI0227 failures.
Builder protocol v3 accepts ordinary text answers, omits required tool choice, and no longer
emits MI0227 or inserts slip reminders. The optional reply tool and reference tools remain.
Earlier diagnostics and invocation records are retained as history. No tests were run for
this override, as instructed.

## Follow-up after the demo, 2026-11-17

The code ships as `builder.agent.v4`: v3 plus reading every choice of a `chatgpt/` reply
(`docs/notes/agent-tool-calling-check.md`). The slip tests in `test_loop.py`, which asserted the
removed rule, were replaced by tests of the current contract. The guard ledger records the
guard's retirement. MI0227 is retired, since nothing emits it
(`test_every_declared_code_is_emitted`). `make check`: lint green; tests 3,982 passed, 2 failed:
MI0227, since retired, and #413 (Python 3.14 words a `ValueError` differently; it predates this
work). Types, docs, links, paths and sizes green. Frontend: 678 tests, `tsc -b` clean.
