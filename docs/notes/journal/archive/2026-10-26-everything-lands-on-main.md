# 2026-10-26 — Everything lands on main; the refactoring campaign

PR #402 (`refactoring-campaign`) merged into `main` the stacked local work since 2026-10-19: the
old forge's removal (#361), the redesign parts 1–7 and board match (#370), the walk fixes, one
builder plans 1 and 2 (#395), and a behaviour-preserving refactoring and documentation campaign
over every package. The campaign's working checklist (`REFACTORING_CHECKLIST.md`) and session log
(`notes/`) are local and untracked by choice.

## Where things stand

- `main` holds all of it: every branch from the entries of 2026-10-19 to 2026-10-22 that still
  exists locally is in `git branch --merged main`.
- **The forge's part 0 landed without part 1.** The plan was to merge them together so `main`
  never lacks a forge; it now does. Registry data is written by hand until #362.
- Campaign validation at merge: `make check` (3,426 passed, 1 skipped: the offline wheel build),
  `make guards` (93 passed), and the 19 slow checks, each in its own stage.

## What is next, in order

1. One builder plan 3 (the chat as one stream, and Describe): #392's protocol question first,
   then #391 and #399's three findings. Mockups before the plan.
2. Part I.2 (#293): say what was narrowed or already known (#268's DE and paired-end items,
   #306). Independent of plan 3.
3. One builder plans 4 (the hand-over; #393 likely belongs there) and 5 (#394, mockups first).
4. The forge, parts 1–8 (#362–#369). Settings' registry release setting (#381) waits on it.

## Open

- The campaign left four things for a separately authorised pass that may change behaviour:
  `SampleUpload.tsx`'s hook-dependency warning, Node 22.6 below Vite's 22.12 floor, a large
  bundle chunk, and one Starlette/httpx deprecation warning.

## Traps

- **The `registry/` submodule has an uncommitted edit** to `inspectors/README.md` (it dropped the
  deleted `mendel-forge` instructions). Land it in a writable registry checkout, not the
  detached submodule, or discard it.
