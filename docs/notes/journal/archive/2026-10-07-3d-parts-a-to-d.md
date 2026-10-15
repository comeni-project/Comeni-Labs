# 2026-10-07 — 14.7.8.3d, Parts A to D fixed

## Where things stand

- **Parts A–D of 14.7.8.3d (#284) are done and closed** (#285–#288). Each issue was researched,
  its approach confirmed with the operator where research changed it, fixed test-first, and
  checked against the running stack where that was possible. Every new guard is in the ledger.
- **Still open from these parts:** #273's second half (durable run parameters) under Part H;
  #294 (the canvas can draw a step twice), filed tonight under Part G.
- **Next: Part E** (#289): #279 (models and migrations drift; Wiener has no migration test),
  then the rest of #274 (no CHECK constraints; Wiener has no foreign keys). Then F, G, H, I.

## What changed

- `8ea39904` #263: the walk offers a card after projecting the quiet steps.
- `1fc07ea8` #281: level 0 lets a sample excerpt reach Redis's snapshot (operator).
- `8ca86492` #271, `1e4e732e` #277, `56f8c83c` #278, `d16f0d07` #280, `2b34dec8` #283 (did not
  reproduce; parity guard kept), `03d6124b` and `14fa939e` #268: Part C.
- `bfdac361` #273, `568c25f0` #282, `ca8c9302` #274 streams, `2fb0e7ab` #268 restart: Part D.
- Migrations: Mendel `c9e5a1f3b724` (kept on the draft), `d1f7b3a5c826` (one live gate per
  draft); Wiener `e6b2c4d8f103` (the projection holds the fold). Applied to the dev databases.

## Decisions made, and why

- **#277:** *changed since kept* compares a fingerprint of the graph, not the revision: a hand
  save does not move the revision (#272). The row is the one record of keeping; drafts kept
  before it list as not kept (operator: nothing is live).
- **#278:** only the gate job gets the long timeout (the worker is shared), one try, a partial
  unique index for one live gate per draft, and a sweep on a timer — a gate has a hard limit,
  so time can tell lost from slow.
- **#268:** the author is a *Your name* setting under System, before git (operator's choice
  over an env var). The home page asks `/settings/ai`, a settings fact, instead of the
  diagnostic `/health/ai`, and waits for it with the rest of its data.
- **#273:** no job id — each submit is a new run, and a redelivery is the same job; the claim
  under the run's row lock is what stops a second launch.
- **#282:** the fold's missing facts are columns on the projection (operator, over a JSON
  snapshot); `wiener_core.state.restore` rebuilds the state; `seq` is taken under the run lock.
- **Reboot:** the whole dev stack is `unless-stopped`, as the prod overlay already was.

## Traps

- **The browser automation's first click and keys after a navigation do not reach the page**
  (listeners logged none). That was the "dropped first submission"; wait, or check the value.
- **`WIENER_TEST_DATABASE_URL`** opts in to `test_seq_race.py`; point it at a throwaway,
  migrated Wiener database, never the dev one. A `wiener` database exists on the throwaway
  Postgres at 127.0.0.1:5442 (container `mendel-test-db`), gone when it is stopped.
- **The workers and Wiener's containers are baked**: rebuild them after a backend change.
- Seven journal entries now wait for compaction (`compaction.md`).
