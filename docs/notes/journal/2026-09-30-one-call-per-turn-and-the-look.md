# 2026-09-30 — one call per turn, and the look

## Where things stand

- **#201 is fixed and closed** (2bf5b41): a turn answered with a question no longer runs the
  follow-up call too. The former strict xfail passes, and a one-step twin was added.
- **`comeni-registry` branch `families` is pushed**, so `registry/`'s pointer (`c7208bd`) now
  exists on GitHub.
- **The visual check is done** (gemma3:12b, family step on). It covered the token counter, the
  call panel with the family call as *choosing the kind of result*, the reworded question card,
  and the card with its read-back, compared against `LivingGoal`. The one gap found is filed as
  #207: the panel does not show whether a reply's shape was enforced.
- **#198 is summarised on the issue**, with a proposal to narrow it to one step against two on a
  ~300-type layer, run after #202.

## What is next

1. **#202 decision** (a request nothing fits is forced into a family and then fails): options
   are on the issue and in the session; the operator chooses.
2. **#207 approach** (mechanical, needs a yes).
3. **#198 narrowed**, after #202; and whether `family_step_from` gets a threshold.
4. **Then 14.7.5**, the settings menu.

## Traps

- **A background Chrome tab does not poll.** TanStack Query stops `refetchInterval` while the tab
  is hidden, so a driven walk in a window that is not in front looks stuck on *Working on it*.
  That is by design (a person returning refetches on focus); reload to see the new state.
- **The test Postgres is a throwaway**: `walk-testdb` on `127.0.0.1:5442`, started with
  `docker run --rm` and migrated with alembic. It does not survive a reboot.
