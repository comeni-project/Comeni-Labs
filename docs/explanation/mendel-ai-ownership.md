# Mendel AI ownership

Builder-specific AI behavior belongs to Mendel. Registry-adaptation AI behavior belongs to
Forge. `comeni-ai` supplies reusable provider access and validation; `mendel-api` owns the
application transactions, queues, access settings and durable outcomes around those calls.
Wiener has no implemented AI agent in this workspace.

Keep the existing distribution packages. A dedicated `mendel_api.authoring.ai` subpackage is a
reasonable next extraction for builder prompts, request/reply preparation and admission. That
is a proposed code organization, not the current import path. A new distribution package would
add installation/versioning work without an existing second consumer of builder behavior.
Do not reuse the deprecated `mendel-ai` name.

## Builder call path

1. Routes in `mendel_api/routes/authoring.py` dispatch through the session service to handlers in
   `mendel_api/stages/`. The pure `mendel-authoring` protocol supplies legal commands and the
   declared transitions; the API binds those actions to rows and side effects.
2. `stages/_jobs.py` constructs jobs with stable IDs and the `arq:queue:ai` queue.
   `services/session.py` queues work through its `queued_after` boundary. Redis transport is in
   `mendel_api/jobs.py`; `AIWorkerSettings` registers the allowed worker functions.
3. `services/authoring_jobs.py` reads the still-pending context, chooses the phase/purpose and
   constructs a `comeni_ai.Client` using application settings. A delivered job whose context no
   longer matches does not spend another model call. Phrasing, read-back and characterisation
   have their own handlers and context checks.
4. `services/authoring_ai.py` composes the request and resolves a committed template through
   `authoring/prompts.py`. `comeni_ai.prompts.PromptTemplate` loads/renders/version-identifies the
   caller's files; it does not own those files. `Client.chat` applies the selected provider
   format and validates the reply shape.
5. Builder admission validates offered IDs, quote evidence and domain constraints. Valid JSON
   alone does not establish a valid builder decision. `services/replies.py` separates heard
   input from suggestions; session/stage actions own subsequent mutation.
6. The API writes `AiInvocation` usage, prompt identity, outcome and failure information through
   `authoring_ai._record`. Application code settles the turn/proposal, records notices and
   applies commands. `comeni-ai` neither commits the session nor owns its retry policy.

`authoring/resolver.py` also implements `ModelResolver` for the resolver's tier-4 port. It is
present and tested, but `services/blueprint.py` currently selects `FlagOnlyResolver`; the adapter
is not wired into that build path. Its existence is not evidence that every build calls a model.

## Forge call path

1. Forge routes/services create and move application-owned adaptation/revision rows.
   `services/forge_jobs.py` enqueues generation or review answers with stable IDs on the AI queue.
2. The AI worker dispatches `generate_forge_revision` or `answer_forge_review_message`.
   The application job claims state through `services/forge_state.py` before doing work.
3. `_generate` reads the workspace/source/holes and selects context with
   `mendel_forge.ai.select`. The application's validation callback applies a candidate in memory
   and runs `mendel_forge.verify`; diagnostics feed the bounded repair loop.
4. `mendel_forge.ai.generate.run` owns proposal/repair behavior. Forge prompt text and versions
   live in `mendel_forge/prompts/`; proposal models live in `mendel_forge/ai/schemas.py`.
   Shared `Client` transport validates provider responses without choosing registry policy.
5. API-side job code persists invocation/outcome data, writes the candidate revision and moves
   adaptation state to review or failure. Human approval remains necessary for landing.
   Scaffolding, source sync and publishing use the ordinary worker, outside the model queue.

The Forge library also supports its CLI without the API database. Moving its adaptation rules
into `mendel-api` would make that independent consumer depend on the web application's storage.

## What stays with each owner

| Owner | Keep here |
|---|---|
| `comeni-ai` | Provider credentials/access values, transport protocols, provider formats, typed response validation, generic chat/choice helpers, caller-owned prompt loading and recorded transports. |
| Builder AI subpackage, proposed inside `mendel-api` | Builder prompt catalogue/files, prompt context preparation, reply admission and the optional tier-4 adapter. Dependency injection must supply access and an invocation-recording boundary. |
| `mendel-forge` | Adaptation prompts, context budgets, proposal schemas, bounded repair, candidate rendering and validation rules usable by CLI and application callers. |
| `mendel-api` application integration | ORM/models, transactions, queue IDs/routing, worker startup/concurrency/timeouts, stored access/settings, invocation persistence, turn/proposal/adaptation claims and retry/recovery actions. |
| `mendel-authoring` | Pure protocol, commands, transition rules and calculations over supplied values. Neither provider transport nor prompt files belong in the interpreter. |
| Wiener, when implemented | Execution-specific AI prompts and admission remain Wiener-owned; generic provider primitives can reuse `comeni-ai`. No Wiener AI package is introduced speculatively. |

## Recovery is application behavior

Queue deduplication and database context/claim checks serve different failure boundaries.
They should remain explicit while changing file placement.

`mendel_api.ai_worker.reclaim_lost_jobs` currently delegates to `forge_jobs.reclaim`, which fails
stale Forge adaptations using the configured timeout threshold and a recorded diagnostic.
It does not provide a universal recovery pass over every authoring turn, proposal or model call.
Builder handlers check pending context and represent refusals as application notices, but that
is not proof of recovery after every worker crash or cancellation. Do not copy the Forge state
machine into shared transport to conceal this difference. Any broader recovery guarantee needs
its own killed-worker test and a defined retry/settlement policy under
[#310](https://github.com/comeni-project/Comeni-Labs/issues/310).

## Refactoring sequence and checks

First move the generic invocation vocabulary out of `mendel_forge.workflow` into an
application-owned module, preserving serialized values and migration history. Then separate
prompt preparation and reply admission from invocation recording through explicit inputs and
an injected recording adapter. Only after those seams are tested should files move into the
proposed builder AI subpackage. Keep compatibility imports until callers and tests move together.

Tests that substantiate the current boundaries include:

- `packages/comeni-ai/tests/`: provider formats, validation, chat, prompt loading and recordings.
- `packages/mendel-api/tests/authoring/test_authoring_ai.py` and `test_authoring_prompts.py`:
  builder context, admission, prompt identity and recorded invocation behavior.
- `packages/mendel-api/tests/authoring/samples/`: characterisation evidence and excerpt handling.
- `packages/mendel-api/tests/forge/test_forge_jobs.py`: application claims, outcomes and recovery.
- `packages/mendel-forge/tests/ai/`: dossier selection, proposal shapes, repair and candidate rendering.
- `tests/repo/test_compose.py`: process/queue separation and access-setting propagation.

This review traces source and existing tests; it does not claim that every crash path was
reproduced. Package responsibilities are summarized in the [workspace map](package-boundaries.md).
