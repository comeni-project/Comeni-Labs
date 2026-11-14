# 2026-11-10: tool constraints, phase 1, reconciled

**What happened.** The plan for #460 (`docs/superpowers/plans/2026-11-06-tool-constraints-phase-1.md`)
was ticked only through stage 4, but PR #476 merged stages 5 and 6 and the docs task too. Each
task has its commit: run rules `e5895b92`, Wiener and the run sheet `eb64360c`, the
`optional_input` decision `3ccc5e8e`, step cards `085681b5`, the model's switch `c67ee08c`,
docs `f7b11e91`. The plan is now ticked from those commits.

**The QUAST builder fixes merged after #476:** #477 (PR #478), #479 (PR #480) and #481 (PR #482).
Those issues, and #471 and #473 (fixed in #476), are closed. #468, #470 and #472 are fixed by
commits in #476 but are still open.

**What is left of #460:**
- Browser checks at 1440 and 390, light and dark, for the forge page (Task 10), the run sheet
  (Task 12) and the step cards (Task 14). No commit records any of them.
- Task 17, the QUAST walk to a real run: with a reference, and with it left empty.

**Decision.** Walks run on GPT through the ChatGPT subscription (#457), not on local models: "we
use gpt now for the walks no point in using local stuff".
