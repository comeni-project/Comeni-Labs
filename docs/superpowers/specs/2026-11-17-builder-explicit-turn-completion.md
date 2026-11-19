# Explicit completion of builder-agent turns

Status: implemented on 2026-11-17, then partly reversed by the operator the same day. The
slip rule (items 4–5 below) was removed; the code ships the optional `reply` tool as
`builder.agent.v4`. See the plan's "Operator override" section. Full verification
was stopped at the operator’s request. GitHub issue waived by the operator on
2026-11-17. This changes the agent protocol and is outside the existing implementation plan.

## Defect and current ownership

In `packages/mendel-api/src/mendel_api/agent/loop.py`, `run_turn` marks any reply without
calls ANSWERED unless the first reply matches `_ANNOUNCES`. The reported live reply was:

> I'm checking the uploaded yeast samples and the current analysis before choosing a
> gene-counting workflow.

It misses the regex and ends the turn after one invocation, with nothing built. The existing
instruction in `agent/prompt.md` explicitly describes tool-free prose as a turn ending.
Strengthening that instruction alone cannot establish a reliable completion protocol.

`agent/tools.py` owns registration, Pydantic input validation and coded tool refusals. Successful
`ask` calls already terminate in `run_turn`. `comeni-ai` owns `AgentTransport`, scripted replies
and `LiteLLMTransport.converse`; `mendel-ai` is a deprecated compatibility shim, not a separate
agent transport. `_record` stores every model reply and usage in `AiInvocation`. The browser's
`AgentThread.tsx` already offers Retry for FAILED turns.

## Alternatives and costs

| Choice | Cost and consequence |
| --- | --- |
| Expand the regex / strengthen the prompt | Small patch, but incomplete wording detection remains; cannot establish correctness. |
| Require tools only at the provider | Helpful where supported; unsupported endpoints lose capability unless it is optional. Does not define a terminal operation. |
| Explicit `reply` / `ask`, bounded slips, optional required tool choice | Proposed. Changes the protocol, prompt, transport policy and fake scripts. A first slip costs one additional model call; repeated slips fail visibly. Works with auto-only local endpoints. |
| Model-based completion classifier | Adds model cost, latency and another fallible payload/decision boundary; still lacks an explicit completion event. |

## Completion contract

1. Register `reply` beside `ask`, including discovery through the shared tool loader and MCP.
   Its sole argument is `message`: a string, trimmed, nonblank, at most 16,000 characters.
   Validate at the receiving boundary, including whitespace-only inputs. Invalid arguments
   produce the normal refused tool result and do not end the turn.
2. Declare a typed `RepliedView` carrying the validated message as `Text`, a corresponding
   `ViewKind`, and membership in `AgentView` in `comeni_core.egress.agent`. Do not widen every
   existing `TextView.text: Line` merely to accommodate a multiline final answer.
3. A successful `reply` adds a normal `AgentMessage(narration=False)` from that validated view
   and ends ANSWERED. Successful `ask` retains its current question block and ANSWERED behavior.
   In a batch, execute tools in order and stop at the first successful terminal tool; later
   calls do not execute, matching the existing `ask` semantics. Ordinary accompanying prose
   remains narration. Do not duplicate the final message from raw arguments or accompanying text.
4. Any model reply with no tool calls is a protocol slip, including empty text and an otherwise
   plausible answer. Preserve nonempty text as narration. On the first consecutive slip, append
   its assistant message and exactly this fixed, loop-owned reminder to the provider history:

   > You replied without a tool. Continue with the tools, or call `reply` to answer the person,
   > or `ask` to ask them.

   The reminder is a single line in code, not an interpolated explanation or a new person turn.
   Write the invocation and blocks, then continue without a separate user-facing admonition.
5. On the second consecutive slip, end FAILED with a refusal Notice whose text is emitted through
   `coded()` and whose code is declared in `diagnostics.yml`. Proposed unused code: `MI0227`,
   owned by mendel-api, for failure to complete the tool protocol. Recheck availability before
   implementation. The existing failed-turn UI supplies Retry. Reset the slip counter after
   each successful tool call (`result.ok`), not after a refused or unknown call.
6. Remove `_ANNOUNCES`, its special first-step behavior and the “Go ahead” nudge. Retain `re`
   where `_label` and `_code` still need it. Update the prompt: keep working with the tools until
   the request is handled; end the turn only with `reply` or `ask`.
7. Preserve step and token backstops on all continuation paths. In particular, a first-slip
   `continue` must not bypass the token check. If there is no budget for another call, emit the
   existing LIMIT notice. A second consecutive slip is the specified coded protocol failure.

## Provider policy and provenance

The loop requests required tool use through an optional transport keyword, defaulting to the
old auto behavior for other callers. Update the protocol and scripted/fake transports together.
`LiteLLMTransport` forwards `tool_choice="required"` only for a known supporting provider;
custom/local endpoints default to omission unless support is established. If an advertised
capability is rejected specifically as unsupported `tool_choice`, retry once with that parameter
omitted. Do not retry authentication, rate-limit, timeout or arbitrary bad-request failures as
capability negotiation. Scope any capability memory to the provider/endpoint, not globally.
The bounded slip protocol remains authoritative even when a provider ignores required choice.

Keep original text/calls in every invocation, including both slips; retain usage accounting.
Version the changed prompt/protocol consistently (`PROMPT_ID` and `_record` currently say v1).
Capture the tool-spec/policy identity with invocation provenance without adding undeclared
application data to messages. The only new model-visible data shapes are the declared reply
view/tool arguments and fixed protocol instruction. Existing saved turns remain readable;
recorded decision replay must neither call a model nor reinterpret decisions through new wording.

## Acceptance and verification

Recorded/fake transports only; follow `tests/README.md`. Before fixing the loop, add the exact
reported wording as a regression and observe a meaningful failure on the current code. Record
that real failure and the passing result in `tests/fixtures/guard-ledger.md`; do not fabricate
red-test evidence. Cover reply validation/rendering, two slips, successful-tool reset, refusal
without reset, ask, limits and capability fallback. Update existing plain-text-ending scripts.

After approval and implementation, confirm the isolated database URLs before `make test-db &&
make test`; then run `make check` and `make guards`, and `make client` if schemas change (the
proposed declared view does). Report actual failures, including the known frontend token/reported
failures in preferences and `analysis/data/Start.tsx`; those files are outside this change.
Restart the AI background worker after deploying the loop changes.

## Operator override, 2026-11-17

The operator requested removal of the blocking slip rule after repeated MI0227 failures.
Builder protocol v3 accepts ordinary text answers, omits required tool choice, and no longer
emits MI0227 or inserts slip reminders. The optional reply tool and reference tools remain.
Earlier diagnostics and invocation records are retained as history. No tests were run for
this override, as instructed.
