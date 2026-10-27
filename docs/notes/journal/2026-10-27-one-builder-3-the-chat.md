# 2026-10-27 — One builder, plan 3: the chat as one stream, and Describe

[The plan](../../superpowers/plans/2026-10-27-one-builder-3-the-chat.md), on `one-builder-3`, from
[the design](../../superpowers/specs/2026-10-27-one-builder-3-the-chat-design.md) (#395, #392, #391,
#399). Mockups in `.design/one-builder-3/`. Its *Deviations* section is the long form.

## Where things stand

- **Decided (operator):** messages queue (#392: interrupting and parallel answers rejected); the
  open question follows you (full card while newest, docked above the composer once talked
  past); Describe uses the build's frame; a step opens over the chat; phone tabs.
- **Built:** the composer never locks; a session's replies run in order at any AI concurrency
  (`describe.earlier_pending`, `arq.Retry`); proposals carry `asked_at`, receipts `about` (turn
  blocks shape 4); `ChatPanel` replaces the tabs (`StepStrip`, `Stream`, `QuestionDock`,
  `StepSheet`); `Understood` is the left side's switch; Describe has *Start building* in its
  header; announcements link to their step or line; #399's chip and canvas copy fixed.
- **Found while planning:** a reply is already grounded when its job starts (`turn_context`);
  the browser's lock was the only thing stopping a queue. The spec says so.
- `make check` (3434) and `make verify` (plus 19 slow, 93 guards) pass. **The browser check and
  the walk with gemma3:12b are not done** (GPU in use; the operator deferred them): first item of
  #404, with the deferred minors. Self-reviewed (no reviewer subagent).
- **Not merged, not pushed.** The dev database migrates itself when `mendel-api` starts
  (turn shape 4).

## What is next

1. The browser check and the model walk of this plan (#404), against `.design/one-builder-3/`.
2. Part I.2 (#293): say what was narrowed or already known.
3. One builder plans 4 (the hand-over, #393) and 5 (the pipeline file, #394).

## Traps

- **`pgrep -f <pattern>` matches the shell running it**, so a "still running" check can lie;
  read the task's log instead.
- **arq counts a `Retry` as a try** (default `max_tries` 5): a job that waits must raise its own
  `max_tries` (`func(..., max_tries=…)`), or a queued message is dropped after ~10 s.
- **A job may read a stage only through its `READS`** (`test_authoring_binding.py`); a new read
  from `authoring_jobs` must be declared there.
- **`make client` also picks up docstring drift**: the refactoring campaign did not regenerate
  it, so the first regeneration after it is larger than its change.
