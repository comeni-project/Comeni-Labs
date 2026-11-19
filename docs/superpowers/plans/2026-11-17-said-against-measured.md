# A said fact the data contradicts (#510)

**Status:** implemented, 2026-11-18. Option C, chosen by the operator.

## Problem

`services/data/facts.merge` lets what a person, or the AI for them, said about a fact stand over
what the kept samples measured (Checkpoint B). Nothing records that the two disagree. On the walk
of 2026-11-15 `read_length: 150, said` chose STAR while the reads measured about 99 bp, and the
agent explained it as "your reads are 150 bp". A said value near a rule's cut-off would mis-route
the reads, at tier 3, with the review advisory.

## Decision

1. **A person's word still stands.** When it disagrees with the data, both are kept: the fact
   records the measured value beside the said one.
2. **A decision that read a contradicted fact is tier 4**, flagged for review, with both values in
   its reason.
3. **The AI cannot contradict the data.** An AI change setting a measured fact to a different
   value is refused (a new `MI` code). A person can.

Rejected: *measured wins* (A) removes a person's override of a bad measurement, for example one
read from the head of a file.

## Design, grounded in the code

| Layer | Change |
|---|---|
| `mendel_authoring.decisions.FactDecision` | `measured: value \| None`: the data's value, when it differs from the said one. Derived at read, never logged. |
| `mendel_api.services.data.facts.merge` | A said fact whose subject the data measured with another value gets `measured`. A `varies` the data contradicts is not this case. |
| `comeni_core.goal.profile.Measured` | `measured: value \| None`, left out when `None` (no schema bump; the `CallArg.joins` precedent). `Decisions.goal()` passes it on. |
| `comeni_core.plan.tiers.PremiseOrigin` | `CONTRADICTED`: said, and the data measured otherwise. The total maps (`_BY_SOURCE` is per source, so the premise builder sets it; `_ORIGIN_PROSE`; `evidence_of`) each answer it. |
| `mendel_resolver.premises` | A profile entry with `measured` becomes a `CONTRADICTED` premise carrying both values. Its prose: `read_length is 150, said; the data measures 99`. |
| `mendel_resolver` router and setting rules | A rule hit that read a `CONTRADICTED` premise is `Tier.AMBIGUOUS` instead of `DATA_PROFILED`, so review is required. The value it chose does not change. |
| `mendel_api.services.changes.apply` | `kind == "measurement"` from the AI, on a subject the data measured, with another value: refused, `MI0228`. |
| Agent prompt | The next `builder.agent` version says to give a contradicted fact as both values, never as a fact about the reads. |
| Frontend | Where a fact is shown, a contradicted one shows both values. The step's tier 4 badge comes from the tier. |

## Tests

- `merge`: said 150, measured 99 → `measured=99`; said equal to measured → no `measured`.
- Resolution: the RNA-seq goal with read length said 150 and measured 99 routes to STAR at tier
  4, its reason naming both. The same goal without the measurement stays at tier 3. This is the
  regression guard: it must fail without the tier change.
- `changes.apply`: an AI change contradicting a measurement → `MI0228`, nothing written; the
  same change by a person is written.
- Prose: the premise sentence names both values.
- Frontend: a contradicted fact renders both values (vitest), then checked in the browser.

## Cost

About a day across comeni-core, mendel-authoring, mendel-resolver, mendel-api, the agent prompt
and the frontend. `make verify` afterwards, because routing changes.

## Deviations

- **No `PremiseOrigin.CONTRADICTED`.** A contradicted fact stays `asserted` and carries `measured`
  beside it (`Measured.measured`, `Premise.measured`, `PremiseRecord.measured`, all left out when
  `None`). "Asserted, and the data measures otherwise" is one check (`PremiseRecord.contradicted`),
  no total map gains a member, and `evidence_of` already calls it *not measured*. The tier lives
  on `Pin.tier()`, read by the router and the setting rules alike.
- **No new agent prompt version.** The agent reads a step's reason, which now says
  `read_length is 150, asserted, not measured; the data measures 99`; a prompt line repeating
  that is left for the next prompt revision.
- **No new frontend component.** Facts reach the page as each step's reason and premises, which
  carry both values; the tier 4 badge comes from the tier. Checked by the resolver tests, not yet
  in a browser.
- **Schema version 10 absorbs the new fields**, bumped for #507 the day before; nothing shipped in
  between.
