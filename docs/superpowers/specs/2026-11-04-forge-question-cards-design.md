# Forge question cards, engine checks and reviewer v2

Issues: #451 (derive `new`), #452 (engine checks), #453 (reviewer v2, drafter v5),
#454 (question cards). Found on the GPU walk of quast (#412, #426), 2026-11-04.
Design canvas: <https://claude.ai/artifact/G1ZC5XsrZsexHGFDK3ySSP> (Main 1440 interactive,
Phone 390), approved by the operator on 2026-11-04 ("still super dense, but it has to be").
The operator then delegated the remaining choices ("you have the freedom to design and
implement this until you can close the issues"): Choices A and B below were taken as A1 and B1
by Claude under that delegation.

## Why

On quast, gemma3:12b suggested `genome.fasta` for both `consensus` (a per-sample assembly) and
`fasta` (the reference). It also suggested `annotation.gtf` for a GFF input. Nothing on the page
said any of this was wrong. Three things were wrong:

1. **The page.** Each option's registry meaning sat in a separate block under "Curated ·
   registry", away from the option. Every question was open at once, and the card read as one
   undivided block.
2. **The engine stayed silent.** It knows `genome.fasta` is `scope: run` and that two inputs got
   the same type, but it said nothing.
3. **The models were told too little.** They saw bare type IDs with no meaning or scope. The
   reviewer had to comment on every item, and its quotes were optional. The result was "not
   useful yet" (operator, #426). The drafter's `"new": true` was trusted rather than checked
   (`validate.py:221` skips an option marked new).

## Goals

- Mark a question's options as new or declared from the registry, never from the model (#451).
- Have the engine report scope, duplicate-type and format findings on type questions. It shows
  them, the AI sees them, and they never decide (#452).
- Build the question cards as in the canvas (#454).
- Give the reviewer and the drafter type meanings, scopes and the engine's findings. The
  reviewer may say nothing, and every comment it makes must quote the source (#453).
- Measure the prompt change as rates on recorded quast requests.

## Non-goals

- No new question kinds, and no change to answer validation beyond #451.
- No automatic answers from findings. A finding never picks an option, never removes one and
  never stops an answer (the operator kept "warn, don't block").
- Non-question items (contract, rules, tests) keep their current rows. The redesign covers the
  Questions piece only.
- Catalogue snapshots (#450) are separate work.

## Anti-goals

- Hiding a finding behind a click. A finding shows on the collapsed row.
- Presenting a model comment as the engine's. The engine's findings are labelled "Engine check".
  The reviewer's comments are labelled "Second opinion · <model> · a model's comment, check it".

## 1. Derive `new` (#451, mechanical)

The engine sets `Option.new` on the reply's way in:

- Where: in `forging_ai._proposed` for `Piece.QUESTIONS`, before `_item_problems`.
- How: `new = identifier ∉ (known types ∪ pending ∪ own ∪ introduced)` or the states are not
  declared for it. Roles follow the same rule against `roles.names ∪ pending`.
- The model's own value is discarded. `forge.questions.v5` stops asking the model for it.
- `validate.py:221` keeps its skip for a new option, but the flag is now the engine's.
- `forge_context.ContextChoice.proposed` already computes the same thing. Both use one helper in
  `mendel_forge.forging.validate`, so they cannot disagree.
- Test first: a reply that marks `genome.fasta` as `new: true` is stored with `new: false`. A
  reply that leaves `assembly.fasta` unmarked is stored with `new: true`. The guard must fail
  on the current code.

## 2. Engine checks (#452)

There is one pure function in `mendel_forge.forging.checks`:
`findings(items, known, spec) -> dict[item_key, list[Finding]]`. A `Finding` has `code`, `says`
and `option` (the option it concerns, or none). Diagnostics are declared in `diagnostics.yml` as
advisory MF0520–MF0522 (deviation: the spec first said MF06xx) and emitted through `coded()`. It runs on type questions only, and it checks the
answer when there is one, otherwise the suggestion, otherwise each option.

| Check | Signal | Example wording |
|---|---|---|
| **Scope** | The channel's arrival (below) differs from the type's `scope` | "consensus arrives one per sample, but genome.fasta is one per run." |
| **Duplicate type** | Two inputs of this tool have the same type as answer or suggestion | "Same type as consensus. A tool rarely reads one kind of file twice." |
| **Format** | The channel's file format (below) differs from the type ID's last segment | "Format: gff, type: gtf." |

**Choice A — how a channel's arrival is known.** nf-core inputs are almost all
`tuple val(meta…), path(x)`, so "has a meta map" does not separate samples from references.

- **A1 (recommended):** by nf-core convention, `meta` means one per sample and `meta2`, `meta3`
  and so on, or no meta, mean one per run. This is right for quast and most modules, but it is
  only a convention, so the finding says "the module's meta naming suggests…". Cost: a
  convention can be wrong. Because the finding is advisory, a wrong one costs the person a
  second look.
- **A2:** no arrival check. Show the type's scope chip only. Cost: the quast mistake gets no
  warning, only a chip.

**Choice B — how a channel's format is known.**

- **B1 (recommended):** the meta.yml `pattern` extensions when present. Otherwise, the channel
  name when it exactly equals a format segment some registry type uses (`gff`, `fasta`, `bam`
  and so on). Otherwise, no check. Cost: a channel named `fasta` holding `.fa.gz` passes. That
  is the safe direction.
- **B2:** the meta.yml pattern only. quast has no input patterns, so its `gff` mistake would go
  unreported.

**Where findings show:**

- Findings go on the adaptation read (`AdaptationView`, per item) so that collapsed rows can show
  them without fetching the question context.
- They go into `QuestionContext` for the open card.
- They go into the drafter and reviewer prompts as "engine findings".
- They are recomputed on every read, and never stored, so they always describe the current items.

## 3. The question cards (#454)

The canvas is the reference. The structure, in `PieceItems.tsx` (questions only) and
`QuestionContext.tsx`:

**One open at a time.** The first question that needs you opens; the others are collapsed
rows. A collapsed row shows:
- a status dot (answered, waiting or flagged);
- the kind ("Job", "Input", "Output") and the channel name in mono;
- the answer, or "AI suggests: <name>";
- each finding as a red chip;
- a +/− toggle, as a real `<button aria-expanded>`.

**The open card**, top to bottom:
1. The question in plain words, and what it decides (the `decides` text).
2. "From the module": the upstream description as a quote, the `main.nf` line, and "one per
   sample" or "one per run" from Choice A. The full `main.nf` excerpt stays in a `<details>`.
3. Engine findings as `role="note"` boxes labelled "Engine check".
4. A radio group with one card per option. Each card shows:
   - the curated name, the mono ID and a scope chip (red when the scope check fires, amber
     "new · one per <scope>" for a new type);
   - an "AI suggests" badge;
   - the curated explanation, and "AI: <because>";
   - "Which tools use it", which expands the used-by list.
   Picking an option does not answer the question yet.
5. Dashed "Pick another registry type…" (the existing `RegistryPicker`) and "Propose a new type"
   (the existing own-answer path), merged. The free-text "Another answer" box goes.
6. The second opinion (§4), when there is one for this revision.
7. Footer: primary "Answer: <name>"; quiet "Not needed for this tool" (the existing
   `QuestionRemoval`) and "Ask it again" (the existing reject).

**Phone (390):**
- The two most likely options show (the suggestion first); the rest fold under "N more".
- Buttons are at least 44 px tall.
- The rows stack. There is no horizontal scroll.

**Tokens:** existing ones only (`tokens.css`). The hex values in the canvas map to `needs-you`,
`measured`, `now` and `done`. No raw hex goes in the source (`tokens.test.ts`).

**Not changed:** the API commands (`answer`, `reject`, removal), polling, and the chat aside.

## 4. Reviewer v2 and drafter v5 (#453)

**Context for both** (`forging_ai._values`): `known` lists every type as
`id — name — scope — explain`, truncated to 160 characters, plus the engine's findings for the
piece. This replaces bare comma-separated IDs. The prompt grows by about 2.5k tokens for the
current vocabulary; the size is measured and recorded.

**`forge.review.v2`:**
- "Comment only where you have a concern; otherwise return no comment for that item."
  `review_piece` stops requiring the exact key set; unknown keys are still refused.
- The quote is required. A comment whose quote is not verbatim in the named file is dropped, as
  a quote is today, and the dropped count is recorded on the invocation.
- Told: engine findings are already shown; do not repeat them, say what they miss.

**`forge.questions.v5`:**
- No `new` field (§1).
- Told the scope of each channel and of each type, and to prefer a type whose scope matches.
- Told that two inputs with one type need a reason in `because`.

**Measurement:** `tools/measure_prompts.py` measures builder prompts only. It gains a `forge`
mode that replays recorded `ForgeRequest`s (quast's, captured from this walk as fixtures) under
v4/v1 and v5/v2, `--runs 5`, with gemma3:12b. It counts:
- the drafter's suggestion for `consensus` is not `genome.fasta` (scope matches);
- `fasta` and `consensus` get different suggestions;
- the reviewer's comment rate per item, and the share of its comments with a verbatim quote.

Success is decided by the operator on those rates, not by a fixed threshold. Live model calls stay
out of `make test`; tests use recorded replies.

## Order and cost

1. #451, test-first.
2. #452 checks: pure function, diagnostics, tests on a quast fixture.
3. #454 cards, then browser comparison at 1440 and 390, light and dark, against the canvas.
4. #453 prompts, with the `forge` measurement mode, run before and after.

Estimate: about a day of session time. The prompt measurement is the least certain part. If the
work passes two days, I stop and report.

## Calls I made (for the operator to check)

- Findings are recomputed on read, not stored.
- The scope check uses the answer, otherwise the suggestion, otherwise every option; each
  option's chip turns red on its own.
- A reviewer comment without a verbatim quote is dropped, not shown with a warning.
- The free-text "Another answer" box is removed in favour of "Propose a new type", which opens
  the same name input.
