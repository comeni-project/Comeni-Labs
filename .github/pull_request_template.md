## What this changes

<!-- One or two sentences. What was true before, what is true after. -->

## Why

<!-- What broke, or what was missing. If you rejected an obvious alternative, say which
     and why — that reasoning is the part that is expensive to reconstruct later. -->

## Which tier does this exit at?

<!-- Only if your change makes or affects a choice. Which of the four tiers carries it,
     and why is that honest?

     1 structural — no choice existed
     2 convention — a documented default
     3 data-profiled — a declared rule matched measured data
     4 ambiguous — nothing decided it, so it is flagged

     A choice recorded at a tier lower than it deserves is the failure this project
     exists to prevent. If you are unsure, say so and we will work it out. -->

n/a

## Did you watch your guard fail?

<!-- Only if you added a test asserting something *cannot* happen.

     Break it on purpose, confirm the message names the right file and line, restore it.
     Three of three earlier guards in this repository had holes, and all three were found
     this way. Paste the failure message. -->

n/a

## Checklist

- [ ] `make check` passes (`ruff check`, `pytest`, the generated-stub freshness check)
- [ ] New behaviour has a test, written before the code
- [ ] Comments explain *why*, not *what*
- [ ] Process names and container URIs, if touched, were read out of
      `vendor/modules/**/main.nf` rather than out of a plan
- [ ] Generated or golden files, if touched, were read before committing
- [ ] `docs/` updated if this changes a schema, a flag, or observable behaviour

If this touches the egress boundary, a pure package's imports, or how a `DataProfile` is
built, say so explicitly — those three are enforced by tests that are meant to be
annoying.
