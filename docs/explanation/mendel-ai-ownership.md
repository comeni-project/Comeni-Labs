# Mendel AI ownership

Builder-specific AI behavior belongs to Mendel. The forge, which will adapt tools into the
registry, is being rebuilt (`docs/superpowers/specs/2026-10-19-forge-mvp-design.md`) and has
no model calls in this workspace yet. `comeni-ai` supplies reusable provider access and validation; `mendel-api` owns the
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

## What stays with each owner

| Owner | Keep here |
|---|---|
| `comeni-ai` | Provider credentials/access values, transport protocols, provider formats, typed response validation, generic chat/choice helpers, caller-owned prompt loading and recorded transports. |
| Builder AI subpackage, proposed inside `mendel-api` | Builder prompt catalogue/files, prompt context preparation, reply admission and the optional tier-4 adapter. Dependency injection must supply access and an invocation-recording boundary. |
| `mendel-api` application integration | ORM/models, transactions, queue IDs/routing, worker startup/concurrency/timeouts, stored access/settings, invocation persistence, turn/proposal claims and retry/recovery actions. |
| `mendel-authoring` | Pure protocol, commands, transition rules and calculations over supplied values. Neither provider transport nor prompt files belong in the interpreter. |
| Wiener, when implemented | Execution-specific AI prompts and admission remain Wiener-owned; generic provider primitives can reuse `comeni-ai`. No Wiener AI package is introduced speculatively. |

## Recovery is application behavior

Queue deduplication and database context/claim checks serve different failure boundaries.
They should remain explicit while changing file placement.

The AI worker has no recovery pass over authoring turns, proposals or model calls. Builder
handlers check pending context and represent refusals as application notices, but that is not
proof of recovery after every worker crash or cancellation. Do not move a state machine into
shared transport to conceal this. Any broader recovery guarantee needs
its own killed-worker test and a defined retry/settlement policy under
[#310](https://github.com/comeni-project/Comeni-Labs/issues/310).

## Refactoring sequence and checks

The invocation vocabulary (`Agent`, `InvocationPurpose`, `InvocationState`) is already
application-owned, in `mendel_api/invocations.py`. Next, separate
prompt preparation and reply admission from invocation recording through explicit inputs and
an injected recording adapter. Only after those seams are tested should files move into the
proposed builder AI subpackage. Keep compatibility imports until callers and tests move together.

Tests that substantiate the current boundaries include:

- `packages/comeni-ai/tests/`: provider formats, validation, chat, prompt loading and recordings.
- `packages/mendel-api/tests/authoring/test_authoring_ai.py` and `test_authoring_prompts.py`:
  builder context, admission, prompt identity and recorded invocation behavior.
- `packages/mendel-api/tests/authoring/samples/`: characterisation evidence and excerpt handling.
- `packages/mendel-api/tests/infrastructure/test_invocations.py`: the recorded vocabulary's values.
- `tests/repo/test_compose.py`: process/queue separation and access-setting propagation.

This review traces source and existing tests; it does not claim that every crash path was
reproduced. Package responsibilities are summarized in the [workspace map](package-boundaries.md).
