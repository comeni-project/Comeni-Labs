# Plan: forge question cards, engine checks, reviewer v2 (#451–#454)

Spec: [2026-11-04-forge-question-cards-design.md](../specs/2026-11-04-forge-question-cards-design.md).
Branch: `forge-question-cards`. The operator delegated the design and implementation through
to closing the issues (2026-11-04).

## #451 Derive `new` (mechanical)

- [x] Failing test: a declared type marked new is stored not new; an unmarked undeclared one is
  stored new (`test_the_engine_not_the_model_says_which_options_are_new`).
- [x] `validate.option_is_new` and `mark_new`, applied in `draft_piece` and in chat replies.
- [x] `forge_context` uses the same helper for `proposed`.
- [x] Guard ledger row.

## #452 Engine checks

- [x] `mendel_forge.forging.checks`: arrival by meta name (A1), format by pattern, otherwise by
  channel name (B1), and duplicate type; tests on a quast-shaped module.
- [x] Declare MF0520–MF0522 as advisory (`refuses: false`).
- [x] `services/forge_checks.for_adaptation`: findings on `ItemView`, in `QuestionContext`
  (with `arrival` and `channel`), and in `ForgeRequest.findings`.
- [x] End-to-end test on the quast fixture; guard ledger row.

## #454 Question cards

- [x] `QuestionCards.tsx`: an accordion with one question open, plus rows with status, summary and
  finding chips.
- [x] Open card: module evidence, findings as notes, a radio card per option, the picker and new
  name, the second opinion, and a footer reading Answer / Not needed / Ask it again.
- [x] Phone: two options, then "N more"; 44 px targets; no horizontal scroll (scrollWidth 373 in
  a 390 frame).
- [x] Tests updated to the new interactions, plus the findings test; guard ledger row.
- [x] Browser: 1440 dark and light, and 390 dark, on the live quast adaptation, compared with the
  canvas.

## #453 Prompts

- [x] `forge.questions.v5` (no `new`, scope and format guidance) and `forge.review.v2`
  (comment only on a concern, quote required, findings given).
- [x] `KnownIds.described`, `ForgeRequest.findings`, and egress allowlist entries.
- [x] `review_piece`: subset of keys; a revision with no comment gets an empty-comment row;
  unquoted comments are dropped and counted.
- [x] The reviewer's key label: gemma3:12b copied the prompt's ` [proposed]` into item keys,
  which refused the whole review. Only that exact label is stripped, and the case has a guard.
- [x] v5 is given each input's arrival as the engine reads it (`{{inputs}}`). With one smoke run
  and no such hint, v5 still suggested genome.fasta for consensus.
- [x] `tools/measure_forge_prompts.py`, five runs each with gemma3:12b; results on #453.
  - Drafter v5 moves consensus to `assembly.fasta` in 4/5 runs, but fasta follows it, so the
    inputs still share one type.
  - Reviewer v2: 0/30 verbatim quotes, so nothing is shown.
  - Keep v5/v2; the engine checks backstop the rest.

## Checks

- [x] `make check`: lint, types, docs, links, doc-paths and doc-sizes pass, and `make guards`
  passes. `make test`: 3817 passed. The 62 failures and 2 errors are all from #455: `.env`
  tokens leak into the tests through the Makefile's recipe shell. The same tests pass without
  those variables, and they fail on any branch with this `.env`.

## Deviations

- Diagnostics are MF0520–MF0522, inside the forge's MF05xx range, not the MF06xx the spec
  named: MF06xx is not allocated to the forge.
- The measurement is a separate tool (`tools/measure_forge_prompts.py`), not a mode of
  `measure_prompts.py`. That tool runs the builder's calls in-process, and the forge's need
  a different setup.
  - It replays the live quast adaptation instead of stored fixtures.
  - It runs inside `mendel-ai-worker`, the container that can reach the model.
- New (my call): a suggestion that an engine finding flags is not pre-selected.
- New (my call): a reviewed revision with no concern shows "no concern raised" in muted text.
