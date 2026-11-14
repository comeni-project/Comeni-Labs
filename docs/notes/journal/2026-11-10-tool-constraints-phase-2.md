# 2026-11-10: tool constraints, phase 2 (#464)

[The plan](../../superpowers/plans/2026-11-10-tool-constraints-phase-2.md), on
`feat/constraints-phase-1-stages-5-6`, from [the design](../../superpowers/specs/2026-11-10-tool-constraints-phase-2-design.md).
Part 2 of #463. The operator set the push: parts 2–5 back to back, the walk and browser checks
once at the end, part 6 deferred. Goal: import a tool easily, and the builder builds with it.

## Where things stand

- **A survey of 33 nf-core modules** (the design's appendix) found the biggest blocker outside
  #464 as written: an optional file inside a tuple with other files, refused by phase 1's
  MD0601. Twelve of the 33 have that shape. The operator made it phase 2's first piece.
- **Built:** shared slots (a left-out file passes `[]` in its position); a join per port;
  `type.<input>` conditions on the type routing connected; the check tries each accepted type
  (MD0612); the router decides optional inputs with the types its required inputs connected;
  the forge drafts all of it (items.v3, forge.draft.v8) and tests name their data's type
  (`ToolTest.types`); the step card shows an `accepts` input's connected type.
- **Found and fixed on the way:** an `accepts` input fed from the goal crashed materialisation
  (empty channel type); the forge could not round-trip an `accepts` input through its items;
  routing and resolution could disagree on the connected type; a refused alternative left
  orphaned steps.
- **Reviewed:** a fresh reviewer after every task (operator's request). Rulings and deferred
  minors are in the plan's *Deviations*.
- **Not done:** no browser check and no walk (operator: at the end of parts 2–5). The registry's
  CI `ENGINE_REF` must be bumped after merge for forged contracts using these shapes.

## Next

Part 3, rules v2 (#461): brainstorm, design, plan.
