# 2026-10-07 — 14.7.8.3c, the blueprint decides, the walk reviews

## Where things stand

- **Every decision in stage ④ is written into the goal** (spec §14): a tool chosen for a step is
  a pin (`goal.constraints.producers`, `ProducerPin(site, contract)`), a fact told is a measurement
  in its profile. The pipeline is resolved again from the goal, and **the draft is always the
  resolved pipeline's reviewed steps**, never built up by appending. A swap that brings steps
  with it (HISAT2's index in, STAR's out) leaves no orphan.
- **Any step can be swapped for a compatible tool** — the router's own candidates at its site —
  shown as the whole pipeline it gives; one that cannot be built is shown with why. A tool chosen
  over the engine's is tier 4 and the person's, the engine's pick and reason kept beside it.
- **The walk:** Pacing, then Dev mode, both before it; `step` places every quiet step in one
  entry; one `step_card` (Continue, or change it); `amend` resolves again. Hand edits open once
  the walk is done (`MI0217` during it); a goal changed after them asks first.
- **The CLI says when a chosen tool applies nowhere** (`MD0230`): `build` reports it, `upgrade`
  refuses; `upgrade` reproduces a pinned pipeline from its goal.
- Pure: `uv run pytest packages/mendel-authoring/tests packages/mendel-resolver/tests -q`. Rows,
  against a database: `MENDEL_DATABASE_URL=… uv run pytest
  packages/mendel-api/tests/test_stage_four_shell.py -q`.
- **Not yet walked in a browser** (see What is next).

## What changed

- Run 1: `b16e3a3` the router decides through a chain; `bbc1f09` a person's pin in the goal;
  `13ece5b` amendments, the diff, alternatives; `0aa0466` the projection and one stop policy;
  `07ae885` the review's fixes (an inert pin named, `MD0230`; a quiet pin not the engine's).
- Run 2: `4d7a933` the protocol (one card, one amend, Dev before the walk); `8daab1e` the session
  row (`reviewed`, `policy`; migration `b8d4f0e2a613`); `dddb24e` the shell (`stages/building/`
  as a package: walk, cards, amending); `101bfcd` the browser.
- Spec: §14 (`17b8452c`, `fe06a09e`). Issues 253–259 come from 3b's review.

## Decisions made, and why

- **The goal holds every decision** (operator): three copies of "what has been decided" — the
  session's facts, its cursor, the draft — drifted apart in 3b.
- **Alternatives are whole pipelines, one decision at a time**: no combinations.
- **A person's review carries across a swap** to the step at the same site, only where the goal
  pins it; a fact or a registry change shows the new step again.
- **A candidate that consumes its own site's type is not an alternative** (MultiQC for FastQC).
- **A fact option is `fact_<measurement>`**: option ids are bare identifiers.
- **Setting values wait for part 5**, with the picker; the AI as guide is part 4, through the same
  amendments.

## What is next

1. **Walk it**: rebuild the baked images, clear the dev database's authoring sessions once
   (`DELETE FROM pipeline_authoring_turn; DELETE FROM pipeline_authoring_proposal; DELETE FROM
   pipeline_authoring_session;`), `make migrate`, `make dev`; scenario 1 without a read length:
   *tell me 50*, then a swap on the card; each Pacing; Dev mode on.
2. The registry fix: STAR's `seq_platform` gets the SAM `PL` domain.
3. Part 4, ask anything.

## Open questions

- The `comeni-core` version bump for `Constraints.producers` and `ProducerDecision.unknown`
  (release time); an older reader refuses a goal that pins a tool.
- The canvas's *added by your choice* marking (part 5).

## Traps

- **`make slow` needs Docker** and was not run here (the router changed): the operator's.
- **`bp.candidates` reads the default registry stack**, not the roots a blueprint was resolved
  with: right until lab layers reach the shell.
- Package tests cannot import `support.paths`, and nothing imports from a `conftest`.
