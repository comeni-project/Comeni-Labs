# 2026-10-16 — Part I.0 walks: what a tool reads comes from somewhere

Two walks of Part I.0 Plan A with a model (gemma3:12b) found what blocked it (#321). The fixes are
on `fix/i0-walk-findings` (#332, not merged). The operator then set the bar for this one-pipeline
universe (#338): **given a sample, ask nothing a file or the sentence answers; leave what nothing
here can measure as tier 4 on the board.** That is implemented on `facts-a-step-needs`, from the
[spec](../../superpowers/specs/2026-10-15-facts-a-step-needs-design.md) and
[plan](../../superpowers/plans/2026-10-15-what-a-tool-reads.md), and walked end to end. Nothing
merged; `facts-a-step-needs` is pushed only once reviewed.

## Where things stand

- **The rule:** whatever a chosen tool reads, a setting or a fact about the sample, comes from
  somewhere; if nothing supplies it, it is tier 4. Settings already obeyed it. Facts on the
  sample's label (`meta.strandedness`) did not: unknown, the module defaulted (featureCounts
  `-s 0`, #340). Now `conformance.facts_read` derives what each tool's code reads, `resolve()`
  records a `FactDecision` for an unknown one, and the step card's *tell me* asks once; the
  answer is the fact, so every step reading it is settled.
- **Gathering** no longer asks a fact only a tool reads that no rule reads and no sample measures
  (strandedness). Read length, pairing and quality encoding come from the sample.
- **The chat model** cannot settle a step (#336, `chat.v5`) and quotes only the turn it answers
  (#337).
- **The walk:** one sentence plus `SRR6357070_1/_2.fastq.gz` → three input questions → goal →
  *Set it up* → one stop for strandedness → complete; the emitted pipeline carries `reverse`.

## Decisions (operator)

- The bar above (#338); strandedness to tier 4 for now, measured at run time later (#339).
- No `needs:` field: derive what a tool reads from its code. **The simplest change that obeys
  the existing rules**, and say why any new concept is needed.
- #326 B (admit item by item), #331 B (phrase only the question on offer), #336 C, #337 A.

## Next

1. Fresh review of both branches; merge #332, then `facts-a-step-needs`.
2. #341 (the fact card's tier, reason and choices), #327 (prompt quality, measured against the
   second walk's baseline on #327), #333/#334 (setup), #320 (buildx).
3. Plan B (the save file), after the operator's `artifact/` audit.

## Traps

- The browser tool uploads only files shared with the session; post a walk sample to
  `POST /api/pipeline/authoring/{id}/samples` (`proposal_id`, `files` ×2) and reload.
- A reboot clears the scratchpad; the walk sample is re-fetched from nf-core/test-datasets.
- `ai_invocation` keeps every walk's model replies: the baseline for #327 is in the dev database.
