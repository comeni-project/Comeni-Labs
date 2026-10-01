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

## When nothing fits (#202, plan 14.7.4.7)

- **Built and walked, and #202 and #208 are closed.** The family call answers `fits` before it
  lists anything (`builder.family.v3`, which now carries the shared block). A want nothing can
  make asks the person instead of failing (`WANT_UNREACHABLE`, `list_needs → say`).
- **The first walk, on v2, caught 2 of 3 no-fit sentences.** *ChIP-seq peaks* was read as
  `alignment.bam`, a step on the way. The operator chose to tune the prompt (*the result itself,
  never a step on the way to it*), and on v3 all three asked in one call. The fit sentences are
  unchanged.
- **The dead-end net was not reached by any walk sentence**; only its tests hold it.
- **Found #209:** the first calls add details nobody said. The ack copied *paired-end* from the
  prompt's example, and `stated` gained `library_prep: ribo_depleted`.
- A whole-branch review of the plan's range was running at the time of writing; its outcome is in
  the plan's execution record.

## What is next

Decided 2026-10-01: **MVP first, then tune.** The open walk findings moved to **14.7.9 (#210)**,
and #180 (14.7.4) is closed.

1. **14.7.5, the settings menu** (#181: #117, #187). Start with a brainstorm, and the first
   question: is a setting per installation or per person?
2. **14.7.6–14.7.8:** samples, the characteriser, the consultant build. A defect found along the
   way joins #210 unless it blocks the loop.
3. **14.7.9 (#210):** tune everything found so far, **before** the scenarios, so the scenario
   walk does not start under a pile of issues.
4. **14.7.10 (#137):** the nine scenarios, renumbered from 14.7.9.

## Traps

- **A background Chrome tab does not poll.** TanStack Query stops `refetchInterval` while the tab
  is hidden, so a driven walk in a window that is not in front looks stuck on *Working on it*.
  That is by design (a person returning refetches on focus); reload to see the new state.
- **The test Postgres is a throwaway**: `walk-testdb` on `127.0.0.1:5442`, started with
  `docker run --rm` and migrated with alembic. It does not survive a reboot.
