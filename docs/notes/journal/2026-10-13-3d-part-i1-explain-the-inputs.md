# 2026-10-13 — 14.7.8.3d Part I.1: explain the inputs

Part I (#293) is split into three, each with its own spec and plan: **I.1 explain the inputs**
(no model), **I.2 say what was narrowed or already known**, **I.3 a conversation, not a form**
(part 4's ask-anything folded in; needs a model only for its walk). I.1 is implemented on
`stage-four-the-consultant-build`, `3abdd0fe` through `8c4e587c`, from the
[spec](../../superpowers/specs/2026-10-13-part-i1-explain-the-inputs-design.md); the registry
text is commit `396a5c6` on the local `explain-the-inputs` branch of `registry/`. Nothing pushed.

## Where things stand

- `make check`: green for this work. The two #303 gzip tests fail under Python 3.14 only; four
  `tests/registry/test_measured_entries.py` tests (`DataProfile` has no `source`) and
  `tests/repo/test_doc_checks.py` (on `docs/design/invariants.md`) fail from the operator's
  `comeni-core` audit commit `11689084`, reproduced with this work stashed.
- Every question about the data shows *What is this?* (the registry's words, marked *curated*)
  and why it is asked (marked *engine*): the tools that can read an input, or the rule a
  measurement decides with its citation. Open by default; Settings → Building → *Explain each
  question* (kept by the browser) starts it collapsed.
- A type has a `name` (*gene annotation (GTF)*) and may have an `explain`; a measurement may
  have an `explain`. Questions read *Do you have the gene annotation (GTF) this analysis needs?*;
  the goal card's sentence uses names.
- The upload says what a sample would answer, from the inspectors' declared measures and only
  among questions still open, and nothing about sizes or the AI read.
- The voice is `docs/design/voice.md`; its marked block is what I.3 inserts into prompts.

## Decisions (operator, in the brainstorm)

- *Too mechanical* means the words, then turn-taking, then who leads: all three, in that order.
- Curated text, not model-written; if it reads stiff, a model words it from the same text (I.3).
  *What the pipeline does with it* is derived by the engine, never curated.
- Open by default, as a setting. A curated `name` per type. The minimum in the registry: no
  sub-fields, no lint rule, no `TypeExtension` override (revisit extensions toward tools later).
- No bytes and no AI-read line on the upload card (comment on issue 135). The AI may say it in
  conversation.
- The voice: confident, slightly caring, professional, scientific.

## Rulings in execution

- The question became *Do you have the … this analysis needs?*: *This analysis needs sequencing
  reads (FASTQ). Do you have one?* has no article and the wrong pronoun for a plural name.
- The steps line names tools (*STAR, HISAT2, Subread (featureCounts)*) and says which run depends
  on choices to come: the walk knows candidate readers, not their order.
- What a sample settles is named by each measurement's `description`, lower-cased, so a new
  inspector changes the copy with no edit.
- Ten declared types are named, not eight: the STAR and HISAT2 index types are declared under
  their tools. `measurement.<id>` types are derived and keep their ids.
- The wrap-up's *To run it you need* still shows ids (it is built behind the `Declared` port in
  `mendel-authoring`); I.2 rewrites it.

## Next

1. The final whole-branch review of I.1.
2. I.2: what was narrowed (*differential expression* became a counts matrix with no word that DE
   is not offered) and what was already known (paired-end asked although stated), with #306's
   goal-card chips.
3. I.3, with #306's mechanical lines and model-less measurement questions.

## Traps

- `pkill -f <pattern>` in a shell whose own command line contains the pattern kills that shell
  (exit 144). Kill walk servers by pid.
- The walk needs no model: seed a gathering session with `tests/authoring_setup.py`
  (`move(WANT_RETURNED)`, `offer_next_gap`) and open `/build?session=<id>`.
