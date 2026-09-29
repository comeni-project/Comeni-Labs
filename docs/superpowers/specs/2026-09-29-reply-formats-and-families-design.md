# Replies in the right shape, types chosen by family — 14.7.4

**Substep 14.7.4 (#180)** of Task 14 (#119). Brainstormed with the operator on 2026-09-29; every
decision below is also commented on #194.
**Issues:** #194 (the phrasing call answers with the schema itself). Related and not in scope:
#197 (late-bound parameter pins) and #189/#190 (what the forge must supply).
**Builds on:** [the consultant's words](2026-09-29-the-consultants-words-design.md) (the split
prompt, the call record) and [the authoring protocol](../../design/authoring-protocol.md).

> **This is theory until it is benchmarked.** Both halves — the enforced reply format and the
> two-step type choice — rest on one probe and on reasoning about scale. §9 defines the benchmark
> that decides whether each is worth keeping, and the family step is built with a switch so the
> benchmark can compare it against the one-step choice.

---

## 1. Why

- **The model copies the schema instead of answering.** gemma3:12b answered 4 of 18 phrasing calls
  with the JSON Schema itself; stripping the schema's docstrings made it 12 of 12 (reverted,
  e77a08b). A refused call costs its full duration, 10–47 s, before the engine's words show.
- **A value outside the vocabulary refuses the whole first call.** `"want": ["gene counts"]` is
  refused, and the session stays at *understanding*. The engine's claim, *a model cannot produce a
  value outside the candidate set*, holds only after the fact, by refusal.
- **The vocabulary will not stay small.** The operator's aim is hundreds to thousands of tools.
  Tools never reach the model, but the types they touch do, and the first call shows every type.

**The probe (2026-09-29, throwaway, run in `mendel-api`).** Through LiteLLM 1.97, with
`response_format` set and **no schema in the prompt**, `AskedGap` was valid on gemma3:12b,
gemma3:4b and qwen2.5:7b (10.4 s, 3.9 s and 1.8 s; 47–67 input tokens). Without the format, all
three answered in the wrong shape. LiteLLM's own `supports_response_schema` said *False* for
`ollama_chat/` while the format was honoured.

## 2. What success looks like

On the three walk sentences of #194, with each of the three local models:

1. **No reply is refused for its shape** on a lane that enforces the format.
2. **The schema no longer reaches the prompt** on such a lane: fewer input tokens per session
   than the 14.7.4 walk's ~9k, and the number is in the header.
3. **The first call cannot name a type it was not shown**, and a request that fits no type
   becomes a visible question, never a forced pick.
4. **The type is chosen in two steps**, family and then the whole family, and the protocol diagram
   shows it.
5. **Hosted lanes behave exactly as today** until a walk with a key verifies them.

## 3. Decisions (operator, 2026-09-29)

| Question | Decision |
|---|---|
| How is #194 fixed? | **Constrained output**: the schema goes to the server as the required reply format |
| The schema in the prompt, where the format is enforced? | **Removed.** The prompt's prose already says what each field means |
| Which providers? | **Ollama on now; OpenAI and Anthropic built as scaffolds**, off until a keyed walk verifies each. One base class, a subclass per provider, a factory |
| Closed vocabularies in the format? | **Yes, as allowed-value lists, always with a way out** |
| Scaling to thousands of tools? | **Two-step type choice by family, built now**, not deferred |
| Parameters named up front? | **Out of scope**: #197, bound late against the route's tools |

## 4. Global constraints

- **Validation is unchanged and stays the authority.** An enforced format guarantees shape, never
  meaning: every reply is still validated against its shape, and every admission check that exists
  today (a bad `already` dropped, an unknown id refused) stays.
- **A refusal falls back exactly as today.**
- **The allowed list for a call is exactly what that call shows the model**, built by one function
  per call. A model is never held to ids it was not shown, and never shown ids it may not pick.
- **Every allowed list has a way out**: `null`, an empty list, or a question back to the person.
- **No new `AiPoint`.** The family step is a second id-choosing call inside goal extraction.
- **The vocabulary stays closed** (invariant 7): families are declared, and a type whose prefix
  names no declared family fails to load.
- **Determinism is untouched**: the no-model lane and `--no-ai` see no change; recorded fixtures
  replay as before.

## 5. Reply formats, per provider (`comeni-ai`)

```
ReplyFormat                  how a provider is told a reply's shape
├─ InPrompt                  no enforcement; the schema is written into the prompt (today)
├─ OllamaFormat              enforced · verified (the probe)
├─ OpenAIFormat              scaffold · unit-tested, not verified
└─ AnthropicFormat           scaffold · unit-tested, not verified

reply_format_for(access) -> ReplyFormat        the factory, by provider prefix
```

- **Each format answers two things:** the keyword arguments it adds to `litellm.completion`
  (`response_format`, or none), and whether the schema is written into the prompt (only
  `InPrompt` says yes).
- **Each carries `verified: bool`.** The factory returns a provider's format only when it is
  verified, and `InPrompt` otherwise, so turning a provider on is one line backed by a walk. The
  14.7.5 settings menu may later override this per model.
- **Prefixes:** `ollama_chat/` and `ollama/` → Ollama; `openai/` → OpenAI; `anthropic/` →
  Anthropic; anything else → `InPrompt`.
- **`OpenAIFormat` rewrites the schema for strict mode**: every property required, an optional
  field as *type or null*, `additionalProperties: false` at every level. It also has a **cap**:
  past `HOSTED_ENUM_CAP` allowed values in one schema (default 500), it answers as `InPrompt`
  rather than send a schema the provider would reject.
- **`AnthropicFormat`** sends the format LiteLLM turns into a tool, and keeps part 3's cache
  markers. Note for its verification: the tool definition counts as prompt, so a per-question
  allowed list splits the cache per question.
- **Where it plugs in:** `Client.chat` and `Client.respond` ask the factory before composing.
  `LiteLLMTransport.deliver` gains an optional `response_format`; the `Transport` protocol's
  `send` gains the same optional argument, and the fakes in tests take it.
- **The call record:** `ai_invocation` gains `reply_format` (`ollama`, `in_prompt`, …), so a reader
  knows whether the shape was enforced. `last_prompt`, and so the stored digest, ends with the
  schema that was sent as the format, so the digest still covers everything the model received.

## 6. Allowed-value lists

A call names its allowed lists by field; the format carries them as `enum` in the schema it sends,
and the existing admission checks still verify membership.

| Call | Field | Allowed values | Way out |
|---|---|---|---|
| family (§7) | `families[]` | declared family ids | empty list and a question |
| goal | `want[]` | the types of the chosen families | `questions` |
| goal | `stated[].subject` | measurement ids | leave it out |
| ask | `already_option` | that question's option ids | `null` |
| ask | `already_value` | free, validated as today | `null` |
| all | prose (`ack`, `asks`, read-back) | free | — |

The shape is built per call (`with_choices(shape, {field: values})`). The Pydantic type is
unchanged; the enum lives in the schema sent and in the admission check.

## 7. Choosing the type in two steps

### Families are declared

`registry/families/<id>.yml`, a new kind loaded through `mendel_resolver.layers.load()`:

```yaml
declares: family
id: alignment
description: Reads placed on a reference genome, and their indexes
```

A type's family is the part of its id before the first dot. **A type whose family is not declared
fails to load**; a new family arrives through the forge's approval queue like a new type (#190).
The families for today's types are `alignment`, `annotation`, `counts`, `fastq`, `genome`,
`measurement`, `profile` and `qc`. The registry is a submodule: the family files are a commit to
`comeni-registry`, then a submodule bump here. Pushing that commit is the operator's call.

### Two calls instead of one

| Step | Prompt | The model sees | Answers |
|---|---|---|---|
| 1 | `builder.family.v1` | the person's words; every family with its description | `families` (allowed list), `ack`, `unclear` (a question when none fits) |
| 2 | `builder.goal.v7` | the person's words; **every type of the chosen families**, told it is each family whole; every measurement | `goal.v6` without `ack` |

- **The acknowledgement moves to step 1**, so *got it* shows sooner and the extra call adds no
  perceived wait.
- **`unclear`** is shown and handled like a goal `questions` entry: the person answers, and step 1
  runs again with the conversation.
- **A wrong family is recoverable**: step 2's `questions` can say the chosen families do not hold
  what the person asked for.
- **Measurements stay whole** in step 2. They are few; the same pattern applies to them if they
  grow.
- **A switch, `FAMILY_STEP_FROM`** (the number of declared types from which step 1 runs; default
  `0`, so always on), lets the benchmark compare one step with two without a code change.

### The protocol

A model node, **family**, precedes **goal** in `mendel_api.authoring.protocol`; `TRANSITIONS` and
`RETRY_TARGETS` derive from it as now. The Mermaid diagram in `authoring-protocol.md` is
regenerated by `tools/generate_protocol_doc.py`, and the doc check keeps it in sync. The loosening
is recorded there: a second id-choosing call inside goal extraction, no new `AiPoint`.

## 8. Errors

| Case | What happens |
|---|---|
| Format rejected by the provider (an error, not a reply) | `MA0007` as today; the call is refused and falls back |
| Reply valid in shape, id outside its list (a lane that does not enforce) | refused by admission, as today |
| Step 1 picks no family and asks nothing | treated as `unclear` with the engine's own question: *Which kind of result do you want?* |
| A family file missing for a type | the registry fails to load, naming the type |
| Hosted schema over the cap | that call goes `InPrompt`; recorded as `in_prompt` |

## 9. The benchmark (to run later, before keeping either half)

**Nothing in §5–§7 is measured beyond one probe.** Before 14.7.5 compares models, run:

- **Sentences:** the three #194 walk sentences, plus three that fit no type (e.g. *variant calls
  from my exomes*).
- **Models:** gemma3:12b, gemma3:4b, qwen2.5:7b.
- **Arms:** format off (today) against format on; one step against two (`FAMILY_STEP_FROM`); and
  a synthetic layer of about 300 types in 20 families, so the family step is measured where it is
  meant to pay off.
- **Measured per session:** refusals by purpose; input and output tokens; time to the first
  question; wrong-type rate against a hand-written expected `want`; how often *none fits* became a
  question rather than a forced pick.
- **Kept only if:** the format removes shape refusals without raising wrong-type picks, and the
  two-step choice costs less time or fewer tokens than one step on the synthetic layer without
  lowering accuracy. Otherwise the switch or `InPrompt` stays, and the result is recorded on #194.

## 10. Testing

- **comeni-ai:**
  - the factory picks by prefix and returns `InPrompt` for an unverified provider;
  - each format's keyword arguments;
  - OpenAI's strict rewrite and its cap;
  - no schema in the prompt when enforced, and the schema kept when not;
  - `with_choices` puts the `enum` where named.
- **comeni-core / mendel-resolver:**
  - a family loads;
  - a type with an undeclared family fails to load, naming it (a guard, watched failing).
- **mendel-api:**
  - step 1 → step 2 composes the types of the chosen families only;
  - `unclear` becomes a shown question;
  - the switch skips step 1;
  - the call record carries `reply_format`;
  - the protocol derives the new node;
  - the diagram is regenerated.
- **Recorded fixtures** for both prompts, never a live model; the live check is the walk.

## 11. Build order

1. The reply formats and the factory (§5), with Ollama on. Walk the three sentences.
2. Allowed-value lists (§6) on the ask and goal calls.
3. Families declared (§7) in `comeni-registry`, the loader and its guard.
4. The family step, `goal.v7`, the protocol node and diagram, the switch.
5. The walk, and the benchmark of §9 recorded on #194.

## 12. Open questions

- **Type descriptions.** Step 2 shows ids and states only; a one-line description per type would
  help it choose within a family. It is proposed for the forge (#190), not built here.
- **Whether `measurement.*` belongs in the family list at all.** It holds facts a person states,
  not outputs anyone wants; showing it in step 1 may invite a wrong pick. Left in for now, and
  decided by the benchmark.
