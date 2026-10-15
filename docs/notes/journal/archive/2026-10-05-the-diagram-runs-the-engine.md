# 2026-10-05 — the diagram runs the engine (14.7.8.1, parts 1a–1c)

Part 1 of the consultant build (#136) is done: three plans, **behaviour unchanged** for a person,
the shell rebuilt underneath so parts 2–5 have somewhere clean to land. Nothing is pushed;
the branch is `living-pipeline-design`.

## Where things stand

- **The protocol is a pure package**, `packages/mendel-authoring` (on invariant 1's list and the
  purity guard's allowlist): `protocol.py` (the one sectioned diagram: nodes that *act* or
  *wait*, edges named by the command or outcome that takes them), `interpret.py` (`follow`,
  `run`), `state.py`, `types.py`, and `commands.py` (one frozen dataclass per thing a person or
  a job does, plain values only, each naming the arrows it may take).
- **A session stores the node it rests on** (`pipeline_authoring_session.at`). Every change is a
  command; it is refused (MI0216) where the diagram draws no arrow. Entering an acting node runs
  its handler, whose outcome names the next arrow; an acting node that does not wait passes
  straight on when its handler names nothing (`family`, `ask`, `suggest`, `readback` only queue
  a model's work).
- **One facade, one transaction per action**: `mendel_api/services/session.py`.
  - `perform(command)`: one database transaction (`db.transaction()`; every `session_scope`
    beneath it is a savepoint). An exception rolls all of it back; `ctx.raised` (a resolver's
    crash) is raised only after the commit, so `failed` stands.
  - `act(command)`: what routes call. `perform` off the event loop, then the jobs it asked for
    are queued **after the commit**; one the queue refuses runs its `unqueued` ending.
  - `queued_after()`: what background jobs wrap their work in; their commands' jobs are queued
    when the work ends.
  - `take(ctx, arrow)` is how a recorder moves the session; a command never performs another.
  - The read model (`read`, `calls`, `pending_id`, `current_phase`, `ai_for`, …) lives here too.
  - The dispatcher compare-and-swaps on the node read, **also when a session comes back to where
    it started** (an answer that offers the next question): a second tab's racing command is
    refused, MI0201, and what it recorded rolls back.
- **One module per stage**, `mendel_api/stages/`: `describe.py` ①, `gathering.py` ②,
  `samples.py` ②a, `goal.py` ③, `building.py` ④ (only what part 3 keeps: `resolve_blueprint`,
  `offer_step`, `commit_step`, `reresolve`, `settle`, `start`, `record_edit`), `_rows.py`
  (shared row helpers, `GOAL`/`GAP`/`STEP`), `_jobs.py` (job constructors). Each records its
  commands (`@records`) and handles its nodes (`@handles`); each declares `READS`, the only
  functions a job may call on it directly.
- **Spawn is fenced off** in `services/spawn.py`, outside the facade's transaction (its resolver
  calls a model), marked for deletion in part 3. `services/authoring.py` is deleted.
- **Guards**, all watched failing and in `tests/fixtures/guard-ledger.md`:
  `packages/mendel-api/tests/test_authoring_binding.py` (every acting node has one handler and
  every command one recorder, both ways; only the dispatcher writes the phase; nothing moves a
  session by event; routes and jobs change a session only through the facade);
  `packages/mendel-authoring/tests/test_commands.py`; `packages/mendel-api/tests/test_db_transaction.py`.
- Verify: `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
  → 3540 passed. The test database is the `walk-testdb` container (`docker start walk-testdb`).

## What changed

- **Spec** `docs/superpowers/specs/2026-10-04-the-consultant-build-design.md`: §1–§10 the whole
  consultant build; §11 part 1's second half (1c). It stays in `specs/`: parts 2–5 argue from it.
- **Plans**, each ticked with an execution record listing every ruling and its cost, now in
  `docs/superpowers/plans/archive/`: `2026-10-04-consultant-1a-the-core.md` (`256fab57` …
  `539ca025`), `…-1b-the-diagram-moves-the-session.md` (`a35192d9` … `ad261bb7`),
  `…-1c-stage-modules-one-transaction.md` (`6c055f55` … `63649b0a`).
- **Issue 251** (1c's five deferred minors) fixed test-first in `c442d4d8` and closed.
- **Issue 250** opened under the forge rework (#189), labelled `deferred`: score a model's
  closed-vocabulary answers by likelihood (logprobs) with our own models, and compare against a
  hosted structured-decision service (Jev AI) only if the operator approves its data. After
  all of 14.7, against the 14.7.10 walk.

## Decisions, and why

- **Scope of 1c was "C"**: move stages ①–③ whole, from ④ only what part 3 keeps; Spawn and
  `Mode` parked in one file to be deleted, so part 3 deletes rather than untangles.
- **Nothing that calls a model runs inside a transaction**; a model's answer is its own command.
  Rejected: holding a transaction across a provider call (a lock held as long as the provider
  likes).
- **An exception rolls back; a refusal returned as a value commits** (a stale proposal is still
  marked stale).
- **Jobs are queued after the commit, never inside it**: a job never reads what is not saved, nor
  runs for an action that rolled back.
- **Commands are typed** and live in the pure core, so the diagram and the things that can happen
  to a session are declared in one package.
- **Reads are not commands** (ruling 2 of 1c): a stage's `READS` are what jobs may call on it.
- **`ask` queues the phrasing** (question on offer and the next), replacing the old end-of-turn
  prefetch, which only ever produced duplicates the queue refused.
- **Rulings made while executing** (each in its plan's execution record, with its cost): the
  held-node check above; `queued_after` for jobs (the plan had jobs drop their follow-up jobs);
  `dataclasses` added to `mendel-authoring`'s purity allowlist; the tests import the facade as
  `facade` and commands as `commands` (they already use `session` and `c` as locals).

## What is next, in order

1. **14.7.8.2, the build plan** (spec §4): the pure core. `plan_of(blueprint, registry, facts) →
   BuildPlan`: stages grouped by the family of what they make (a family's optional `stage`
   label, else its description: `comeni_core/declared/families.py` `Family` has no `stage` field
   yet, and adding one is the `comeni-core` version-bump question in §10); each step's brief
   (does / why / makes / check, each marked curated or engine); what a step needs (nothing, a
   fact, or a choice, #174's decision); the overview counts; `waits(plan, pacing)`; the wrap-up.
   It reads the blueprint (`mendel_api/services/blueprint.py` `Blueprint`) but belongs in a pure
   package, with golden-file tests. **Start with the brainstorm** (`superpowers:brainstorming`),
   then a spec section, then plan 2: the spec gives the shape, not where `plan_of` lives or how
   a blueprint reaches a pure package.
2. **14.7.8.3 Stage ④** (§5): the handlers for the consultant's steps, `Mode` and Build/Spawn and
   the old step proposals removed (delete `services/spawn.py`, `SettleStep`, `settle`'s old
   envelope), and the Pacing setting made live (#117).
3. **14.7.8.4 Ask anything** (§6), with the AI / engine / curated marks on every message.
4. **14.7.8.5 The cards and the walk**: artboards first, approved by the operator.
5. Then **14.7.9** (tune what the walks found, #210) and **14.7.10** (the nine scenarios).

Each part gets its own plan, written once the part before it has landed. Execute plans inline
(`superpowers:executing-plans`); subagents only for review.

## Open questions

- Where `plan_of` lives (a new pure package, `mendel-resolver`, or `mendel-authoring`) and how
  the blueprint type reaches it: it is a `mendel-api` model today.
- Whether a family's `stage` label is a `comeni-core` change now or a description fallback until
  release (§10 defers the version bump to release time).
- 1c's final review was a self-review (the fresh reviewer stopped on a usage limit). A fresh
  review of `aa053695..c442d4d8` is cheap insurance before part 3 builds on the facade.
