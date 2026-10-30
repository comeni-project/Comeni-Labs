# 2026-10-30 — Forge MVP 3: forging

[The design](../../superpowers/specs/2026-10-30-forge-3-forging-design.md) and its plans,
[3a, the shared engine](../../superpowers/plans/2026-10-30-forge-3a-shared-engine.md) and
[3b, forging](../../superpowers/plans/2026-10-30-forge-3b-forging.md), on `forge-3-forging`, for
#364. Numbered by GitHub's *Forge MVP N* (operator).

## Where things stand

- **Decided (operator):** share the builder's engine (now `comeni-flow`); the person chooses who
  drafts each piece; the AI may propose writing, changing or removing anything and only a
  person's approval makes it count; rejecting opens the chat on the item; several adaptations
  at once, isolated, with assembled drafts' vocabulary visible to later ones as *pending*; any
  model through LiteLLM. The seven forging boards were agreed; **the Rules panel needs more
  design work**, built as drawn for the deadline.
- Built: `comeni-flow` (the builder declared on it, its diagram byte-identical); forging's
  rules, values and checks in `mendel-forge`; adaptations and the `forge_drafting` door in
  `mendel-api`; assembly into a draft layer proven by the loader and conformance; the Forging
  tab and the adaptation page.
- **Live (dev stack):** a re-forge of star/align, approved by hand, assembled into a draft that
  loads over the registry and conforms to nf-core's current `main.nf`. **Not yet run: forging
  with a model** (the stack had none configured); the plan's measurement of gemma3:12b against
  an API model is still to do.
- Found on the way: the API needed the forge cache mounted; `conformance` does not flag input
  channels in a different order (worth an issue).
- Not merged, not pushed.
