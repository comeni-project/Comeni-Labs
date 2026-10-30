# 2026-10-30 — Forge MVP 5: pull requests

[The design](../../superpowers/specs/2026-10-30-forge-5-pull-requests-design.md) and
[the plan](../../superpowers/plans/2026-10-30-forge-5-pull-requests.md), on
`forge-5-pull-requests`, above MVPs 3 and 4, for #366.

## Where things stand

- **Decided (operator):** two buttons; approve only on green CI. The description is the engine's
  record, not a model's summary; an AI summary can join it later.
- Built: placing a draft in the registry's layout, the registry's checks run locally,
  `GitHubPublisher`, `forge_pull_request` with at most one open, a cron every minute, and the
  catalogue's *in review* and *merged, not released*.
- **The GitHub token moved to the worker alone.** It was on every Mendel service. The others get
  `COMENI_FORGE_GITHUB_TOKEN_SET`, so they can say whether publishing works without holding it.
- Merging runs in the worker, since only it has the token: the click records the approver and
  queues; a refused merge is reported in the chat, not as the click's answer.
- **Not done, so #366 stays open:** no real pull request. `comeni-registry` still needs `test` in
  `layout:`, `changelog.d/` and a new `ENGINE_REF`.
- A draft's new type goes under `vocabulary/types/`. A type only one tool touches belongs in that
  tool's `types/` (MD0023), so such a tool will be refused by the local check until placing learns
  it. Not seen yet: found by reading the lint.
- Not browser-checked.
