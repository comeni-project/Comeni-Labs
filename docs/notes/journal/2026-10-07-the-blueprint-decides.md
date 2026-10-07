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

1. **Walk it, on the operator's main PC** (its `.env` holds the model; Ollama on the AMD card).
   Start Claude with `claude --chrome` so the walk can be driven in the browser.
   - Get the branch: `git fetch && git checkout stage-four-the-consultant-build && git pull`,
     then `git submodule update --init` and `uv sync`.
   - Bring the model up if it is not: `make ai-up OLLAMA_GPU=rocm` (`.env` already names it).
   - Rebuild and start: `make dev` (rebuilds `api`, `ai-worker`, `wiener-api`; the `api`
     container applies migration `b8d4f0e2a613` itself).
   - Clear the old authoring sessions once — they rest on nodes that no longer exist:
     `docker compose exec postgres psql -U mendel -d mendel -c "DELETE FROM
     pipeline_authoring_turn; DELETE FROM pipeline_authoring_proposal; DELETE FROM
     pipeline_authoring_session;"`
   - Walk at http://localhost:5173/ (or http://localhost/): describe the RNA-seq analysis
     **without saying the read length**, then:
     - Pacing *together*: at STAR's card, *tell me* the read length `50` — the canvas should
       become HISAT2 with its own index, no STAR step left; walk to the wrap-up.
     - Again, and on STAR's card choose HISAT2 instead — the next card is HISAT2's index; the
       wrap-up credits you.
     - Pacing *stop only where needed*, and *ask me every time*; then Dev mode on (gap cards).
     - Look at it against the artboard (`.design/_compare.html`). File each defect as an issue
       (the `walk` label), then `make slow` (Docker) for the router change.
2. The registry fix: STAR's `seq_platform` gets the SAM `PL` domain.
3. Part 4, ask anything. Deferred minors of 3c: issue 260.

## Open questions

- The `comeni-core` version bump for `Constraints.producers` and `ProducerDecision.unknown`
  (release time); an older reader refuses a goal that pins a tool.
- The canvas's *added by your choice* marking (part 5).

## Traps

- **`make slow` needs Docker** and was not run here (the router changed): the operator's.
- **`bp.candidates` reads the default registry stack**, not the roots a blueprint was resolved
  with: right until lab layers reach the shell.
- Package tests cannot import `support.paths`, and nothing imports from a `conftest`.
