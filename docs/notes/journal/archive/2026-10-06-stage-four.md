# 2026-10-06 — 14.7.8.3b, stage ④ built

## Where things stand

- **After *that's right*, the build walks the pipeline on the build plan** (spec §13): an overview
  count, the **Pacing fork** (*together* / *stop only where needed* / *ask*), each step placed or
  stopped on — a fact a rule lacks (asked once), a choice between the resolver's own tools, a
  **registry gap** under the **Dev fork**, or *continue* — and a wrap-up receipt. Keep is the
  draft's, as before.
- **Build/Spawn and `Mode` are gone** from the API, the session row and the browser. Tier 4 always
  stops; `ModelResolver` is kept, unwired, for a later Tier-4 answers fork.
- Pure flow: `uv run pytest packages/mendel-authoring/tests -q`. Rows, against a database:
  `MENDEL_DATABASE_URL=… uv run pytest packages/mendel-api/tests/test_stage_four_shell.py -q`.
- **Not yet walked in a browser** (see What is next).

## What changed

- Run 1: `3b17c316` registry gaps, a no-domain setting is not a choice (issue 252), `fork_keys`;
  `274be9ef` Dev mode, Pacing live; `41063ef7` Build/Spawn retired (migration `a7c3e9d1f402`);
  `b8c523f6` the review's fixes (the no-model notice; the reveal's tests restored).
- Run 2: `6debf24a` stage ④ — the protocol redrawn, the handlers, the snapshot, `with_facts`;
  `47a8e952` the step card's brief, need and gaps, and the pacing question in the browser.
- Spec: §13 (`3e1caa71`), amended against the code (`18514845`) and while building.

## Decisions made, and why

- **No compatibility for pre-3b sessions** (operator): not even the MVP yet.
- **The existing cards carry the new content**; part 5 designs them.
- **The need before the gaps**, and **route around hides the gap, not the step** (it applies the
  pacing) — both found by tests while building; the first by a revert, the second by the shell
  test of *together*.
- **Quiet steps are placed inside one entry of `step`**: a loop through the interpreter would hit
  its 64-node cycle limit on a large pipeline.
- **A fact is typed or chosen in stage ④, not uploaded**: the sample section belongs to gathering.
- **Re-resolving keeps the confirmed goal** and folds the facts in (`with_facts`), so a goal-card
  edit stands.

## What is next

1. **Walk it** (CLAUDE.md: every driven session finds what no suite does): rebuild the baked
   images, clear the dev database's authoring sessions once (`DELETE FROM
   pipeline_authoring_turn; DELETE FROM pipeline_authoring_proposal; DELETE FROM
   pipeline_authoring_session;`), `make migrate`, `make dev`; scenario 1 with the read length
   unknown, then each Pacing, then Dev mode on.
2. The registry fix: STAR's `seq_platform` gets the SAM `PL` domain.
3. Part 4, ask anything.

## Open questions

- The `comeni-core` version bump for `ProducerDecision.unknown` (release time).
- A tier-4 setting **with** a declared domain is shown on its card but has no value picker yet
  (part 5).

## Traps

- **Pacing defaults to *ask***; the mendel-api suite pins `COMENI_BUILD_PACING=together` in an
  autouse fixture, and the tests of pacing clear it.
- **This machine**: no host Node (frontend tooling in podman's `node:24-alpine`); Docker's socket is
  root-only (a throwaway Postgres on podman, `:5442`); `make check` is red without Postgres in the
  known places.
- Pure test file names must be unique across packages (`test_gaps.py` collided; rootdir imports).
