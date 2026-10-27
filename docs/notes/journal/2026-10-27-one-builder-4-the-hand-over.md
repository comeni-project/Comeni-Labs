# 2026-10-27 — One builder, plan 4: the hand-over

[The plan](../../superpowers/plans/2026-10-27-one-builder-4-the-hand-over.md), on `one-builder-4`
(stacked on `one-builder-3`, PR #405), for #393.

## Where things stand

- **A build ends with a hand-over card**: what was built, how its values were decided, what
  still needs you, what next. **No server change**: the engine already wrote a wrap-up receipt
  per revision; the page draws the newest one of a complete session as the card
  (`handoverId`), from records it holds. Older wrap-ups stay lines.
- Frontend tests (836), types and lint pass. Not browser-checked: with plan 3's, in #404.
- **Not merged, not pushed.** Next: plan 5, the pipeline file (#394), mockups first.
