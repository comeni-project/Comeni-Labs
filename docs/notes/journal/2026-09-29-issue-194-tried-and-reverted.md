# 2026-09-29 — issue 194 tried and reverted; a stuck-pending defect found

## Where things stand

- **The schema sent to a model is unchanged** from before #194: 879d81e was reverted by e77a08b.
  Check with `git log --oneline -3`.
- **#194 is relabelled `protocol`.** Its three options are on the issue, awaiting the operator.
- **#196 is filed** (`mechanical`, approach awaiting a yes), under #180.
- **The visual check is still pending.** `list_connected_browsers` returned no browser at the
  time of the attempt.

## What changed

- 879d81e stripped the docstrings from the schema the model is shown; e77a08b reverted it.
- `gemma3:4b` and `qwen2.5:7b` were pulled with the operator's OK. The measurements are on #187.

## Decisions, and why

- **Reverted rather than kept.** The approved approach measurably made things worse. Phrasing was
  refused 12 of 12 times, against 4 of 18 before, and the want call was refused 1 of 3 times,
  against 0 of 3. Without the prose, the schema reads as a form, and the model writes its answer
  inside `"properties"`. The docstring was never the cause; showing a raw JSON Schema is.

## What is next

1. **The operator chooses #194's option.** The recommendation is constrained output through
   LiteLLM's `response_format`. The schema could then leave the prompt, which also serves the
   token budget.
2. **The operator approves #196's approach, then it is fixed test-first.**
3. **The visual check**, once Chrome is connected.
4. **14.7.5, the settings menu**, starting with a brainstorm.

## Traps

- **A fix for a model's behaviour has to be measured against the same sentences before and
  after.** The unit test passed and `make check` was green while the product got worse.
- **A walk script that waits a fixed 180 s per card hides a card that never resolves.** It
  reports `pending after None`. Read that as "stuck", not "slow".
