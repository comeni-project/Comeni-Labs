# 2026-10-13 — 14.7.8.3d Part I.0, Plan A: the conversation

Part I.0 (#307) came out of starting I.2: the operator asked whether the main data structures
still fit, given the project began fully deterministic. Research (Rasa CALM's commands, Google
LangExtract's grounded spans, event-sourced agent state, risk-based confirmation, Nix's lockfile)
and the codebase agreed: the store was already right — Part F's decision families are intent and
facts, and `Goal` is already only their projection — and the smell was at the model's boundary
(an `Extraction` blob, special-cased three ways; a chat whose intents changed nothing) and in the
save file. The [spec](../../superpowers/specs/2026-10-13-part-i0-intent-facts-steps-design.md)
has two plans; Plan A (the conversation) is implemented on `stage-four-the-consultant-build`,
`99fd3741` through this entry. Nothing pushed.

## Where things stand

- `mendel-api` and `mendel-authoring` suites green (1410 at Task 10, then Tasks 11–12 added).
  `make check`'s remaining failures are the two #303 gzip tests (Python 3.14) and the operator's
  `comeni-core` audit commit `11689084` (`test_measured_entries` ×4, `test_doc_checks` on
  `invariants.md` line 260).
- **One writer for every change** (`services/changes.py`, `c.Change`, the correction edges); a
  model's change is *heard* when it quotes the person (≥ 3 characters, found in one of their
  turns), recorded before the goal is confirmed, offered as a suggestion otherwise and always
  after. The quote lives on the revision, never in a payload.
- **The rows are the only home** of the want: `session.extraction` is gone (migration
  `c6a2e8d4f159`, carry frozen in `migration_data/extraction_v1.py`); confirmation is recorded
  (`pipeline_draft.confirmed_revision`).
- **Memory:** `family.v4`, `goal.v8`, `chat.v3`, `ask.v2`, `readback.v2` carry *what is known*,
  rendered from the rows. `chat.v3` replaces `chat.v2` and `gap.v2`: a typed answer is a fact.
- The goal card shows the words each fact was heard in; suggestions wait above the composer.

## Decisions (operator)

Intent, facts and steps in one save file; heard or suggested (the model's ideas kept); what is
asked but not offered reported by the model, quoting the person, no registry vocabulary;
quotes stay in the database; the registry pinned by locator and digest (Plan B); one file to
start from and one home in the database. All on #307.

## Rulings worth reading

The ledger's rulings are in the final message of the run; the ones a reader trips on:
- the payload is `DecisionChange` (FastAPI schema names collided on `Change`);
- a fact the registry refuses refuses the whole reply (spec §9), where #170 dropped it;
- a heard change is recorded only if the decisions did not move since the job started;
- suggestions are a table, not a proposal kind (one pending proposal per session);
- the frozen legacy conversion's *writer* follows the schema; its interpretation is untouched.

## Next

1. The walk with a model (Task 12 Step 3), which needs the stack's `ai-worker` rebuilt.
2. The final whole-branch review of Plan A.
3. Plan B (the save file), after the operator's `artifact/` audit lands.
4. Part I.2 on top: the goal card's words for *not offered*, the undetermined-sample wording,
   names on the chips (#306).

## Traps

- `#307` in a frontend test name fails `tokens.test.ts` (read as a hex colour): write *issue 307*.
- A data migration's reads must skip `alembic --sql` (`context.is_offline_mode()`).
- `record_said` returns the pending answer's `seq`; the person's turn is the one before it.
