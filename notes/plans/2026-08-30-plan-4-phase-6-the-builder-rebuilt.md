# Plan 4 Phase 6 — the builder, rebuilt against its artboards

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes; leave one **unticked** if
> it was not done, and record every deviation in the execution table.

**Goal:** the builder canvas as `BuilderCanvas.dc.html` draws it. The operator drove the built
page and the verdict was *incredibly different — treat it as a rebuild from scratch*.

**Design source: the canvas annotations, and they are the specification.** Read all of them
before starting — `python3 -c "import json; [print(a['text'].replace(chr(92)+'n',chr(10))) for a
in json.load(open('.design/canvas.json'))['annotations'] if a['page']=='page-1']"`. The ones that
decide this phase are `n-bcanvas`, `impl-geom`, `impl-settled`, `impl-reuse` and `impl-walkbugs`.

**Depends on:** phases 0–5. Nothing here touches the runs *screens*, but Task 1 changes the graph
both canvases draw — see the note below, it is the one cross-cutting decision.

---

## What is actually wrong — measured against the boards on 2026-08-30

| The artboards | What ships |
|---|---|
| **Left to right** — `impl-settled`, under *do not re-litigate* | **Top to bottom.** `layout.py:327` is `x=across, y=top[rank]` |
| Uniform **172×112** symbol, every node identical | Variable height, ~190 wide, height follows port count |
| **Types on the node**, tier as a **left edge bar** | Types on the wire labels; tier as text |
| **Settled gets no colour at all** | Every node carries colour |
| Click a port → **only what fits**, ranked, with the reason | Nothing happens. `Picker.tsx` exists and no port opens it |
| Orthogonal **H/V/H**, endpoints derived from node geometry once | Wires drawn from separately-typed coordinates |
| Grid **only during a drag**, three rulings 8/40/80 | No grid at any time |
| The canvas has **its own field** — three arc families, chords, a pool, a graticule | The page field, showing its empty corner |
| Settings in a **card on the node**, opened from `⋯` in its header | Settings in the rail |
| The rail is about the **choice**; the card is about the **values** | The rail is both |

---

## The rule this phase exists to enforce

**A schematic, not a diagram toy** — `n-bcanvas`. Every item above is one decision restated:
uniformity, right angles, colour only where something needs you, and no permanent grid. The
single loudest hobby-editor signal is a dotted grid behind everything, and the second is a bezier.

**And `impl-geom`'s rule, which is a correctness rule rather than a style one:**

> **Port positions are DERIVED from node geometry in one place. Never write a coordinate twice.**
> `spine = node.y + NODE_H/2` · `second = node.y + NODE_H/2 + 22`

That is what the 2026-08-29 walk found the hard way: nothing had `box-sizing: border-box`, so a
declared 180px node rendered at 182 and every wire sat 6px above its port.

---

## Global constraints

- **`dag-core` is PURE and has no clock, no network.** Invariant 1. It is also the *only* layout
  implementation — `impl-reuse`: *both canvases, one arithmetic*. Do not fork it.
- **Uniform symbol size is load-bearing**, not cosmetic: variable heights put a jog between every
  pair and the main chain stops reading as a chain.
- **Five movements, one curve.** A grid that fades in on pointer-down is `settle`, not a sixth.
- **Invariant 15 still decides the input design.** A source node carries a TYPE and never a path;
  the binding lives with the run. `norule.test.ts` holds it and must keep passing.
- **Invariant 6**: an open value shows on the node, in the status line, in the settings card and
  in the run sheet. Four places is correct, not redundant.
- The gate is `npx tsc -b && npx vitest run && npm run lint` from `frontend/`, plus `make check`
  for `dag-core`. **`make verify` is not needed** — no file in its six is touched.

---

## Pre-execution notes — checked against the code on 2026-08-30

**P6-1 — the orientation is one line, and it moves the runs graph too.** `_place()` ends with
`x=across[node.id], y=top[rank[node.id]]`. Flipping to `x = left[rank], y = across` is the whole
change, plus renaming the pitches so the names stop lying. **`RunGraph` draws the same `Placed`**,
so the runs DAG turns left→right in the same commit. `impl-reuse` says that is correct — one
arithmetic for both canvases — and it is called out here because it is the only part of this phase
that touches a screen the operator asked to leave alone.

**P6-2 — the port picker is BUILT and unreachable.** `frontend/src/build/Picker.tsx` and
`GET /api/pipeline/candidates` shipped in phase 3b with component tests. What does not exist is a
port you can click. This is wiring, not a build — and `impl-walkbugs` says adding from a port is
also what fixes *every step landed on identical coordinates*, by construction.

**P6-3 — `validate`, the compatibility index and `producers_of` all exist.** `impl-reuse` is
explicit that the picker's filter IS the index and its ordering IS `(surplus, -priority, id)`.
Do not write a second rule anywhere in this phase.

**P6-4 — `#78`: `ModuleContract` has no description field.** The type signature is the
description. **Leave the slot empty; do not invent prose.**

---

## Task 1 — left to right

- [x] `dag-core`: `x` comes from the rank, `y` from the position within it. Rename `COL_PITCH`
      and `RANK_GAP` so the names describe the axis they now drive.
- [x] The wire router follows: **H / V / H**, leaving a node's right edge and entering the next
      node's left edge.
- [x] `test_the_graph_runs_left_to_right` over the real spine — the aligner is right of the
      trimmer and at the same `y` as its siblings. **Watch it fail on the current layout.**
- [x] `make check`, and confirm the runs graph still renders (it changes orientation, by design).

## Task 2 — one symbol

- [x] 172×112 for every process node, `box-sizing: border-box` on everything.
- [x] Ports **derived** from node geometry in one place: `spine`, `second = spine + 22`.
- [x] Types on the node. Tier as a **left edge bar**. **Settled gets no colour.**
- [x] Corner registration marks, fixed to the viewport rather than the stage.
- [x] A guard that no wire endpoint is computed anywhere but the one derivation.

## Task 3 — click a port, get what fits

- [x] A port is a control: focusable, `role="button"`, and it lifts (the lift contract).
- [x] Clicking one opens `Picker` anchored to it, filtered by direction, ranked by the router's
      own key, with the computed reason.
- [x] Choosing places the new node **where the port is**, which is `impl-walkbugs`' fix for every
      step landing on identical coordinates.
- [x] Keyboard-first: focus on open, arrows, enter to add, escape to close.

## Task 4 — the canvas's own field, and a grid only while moving

- [x] The canvas field: three arc families so something always crosses the graph, long chords, a
      pool where the pipeline sits, a graticule of 13 ticks. **Anchored to the viewport; it does
      not pan.**
- [x] The millimetre grid **pans with the nodes** and exists only between pointer-down and
      pointer-up. Three rulings, 8 / 40 / 80.
- [x] A guard that the grid is absent at rest. Watch it fail with a permanent grid.

## Task 5 — the card on the node

- [x] Settings open from `⋯` in the node's header, ordered by **what could need you**: no-rule
      first as choices, then measured with its premise, then `n settled` folded.
- [x] The rail keeps only the **choice** — what this step is, why this tool, swap it.
- [x] The two lists of the same thing are gone.

## Task 6 — write it down, then look at it

- [ ] Journal, `CLAUDE.md` pointer in the same commit, `notes/README.md` row, guard ledger with
      every revert **verified to land** and every guard watched failing against its own defect.
- [ ] **Drive it in the browser** — the whole point of this phase existing.

---

## Execution record

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes, and it found a guard that did not exist | `geometry.ts` claimed its constants were held to `layout.py`'s by a named test "rather than trusting the comment". No such test existed, and `NODE_W` was 232 in the browser against 172 in Python. `dag-core/tests/test_geometry_agrees.py` is that test, written under the name the comment used; it failed on its first run. The plan said "turn the layout"; it was also a **de-drift**, and the runs graph turned with it because `dag-core` is one implementation for both canvases |
| 2 | Yes, plus one reversal the plan did not authorise | The three-band symbol, the rail colours and the footer went in as written. **Ports became clickable**, which reverses an operator decision that they were drag-only — written up in the ledger rather than done quietly, because a drag-only port is a gesture with no discoverable affordance and the annotation `n-bport` asks for one. `Port.tsx` distinguishes click from drag with a 4px slop on `pointerdown`, so the drag gesture is unchanged |
| 3 | Yes | The picker mounts outside the transformed stage, so its canvas coordinates need the view transform applied **forward** — without that it opened in the page's top-left on every zoom but 1:1. The socket gutter was 240px against a 224px rank pitch, which drew every non-root node's entry sockets on top of the node feeding it; roots keep theirs to the left and everything else drops below |
| 4 | Yes, and it uncovered a defect no API test could see | The field, the three-ruling grid and the registration marks are as written. **Adding a step made its sibling vanish** — `seed` pinned every node once-ever, so a re-layout that moved an unmoved node was discarded. The saved draft was correct throughout (verified against the API), which is why only looking at it could find it. Fixed with a `moved` ref: *being drawn somewhere is not being put there* |
| 5 | Yes, and the rail lost a whole tab as well as the card | The card is three bands ordered by what could need you, not four tier groups; a tier-4 value renders as **chips** where the contract enumerates and a field only where it declares no domain. The rail's Step tab is name / contract / *why this tool* / Swap / a one-line `Values` summary pointing at the node. **The Review tab went with `<Settings>`**: it was a third list of the same values, and `impl-inv` names invariant 6's four places — node, status line, settings card, run sheet — with the rail in none of them. Two things the plan did not ask for and the screen did: the card is a **card on the node** rather than a centred modal with a backdrop (a modal says *stop what you are doing*; the whole point of moving settings off the rail was to put them beside the step), and the settled band stays **answerable** once open, because departing from a convention is allowed and `because` exists to keep the departed-from convention readable |
| 6 | | |

**Two tasks are open and one thing is owed that the plan never listed.** Task 5 (settings move
from the rail to a card on the node) and Task 6 (the write-up, then the hand-driven walk) are
genuinely not done, and their boxes stay unticked. The unlisted thing is a **chrome pass**: this
plan rebuilt the canvas, the symbol and the port gesture, and left the title row, the provenance
bar, the CANVAS/ARTIFACT toggle, the Run button and the right rail exactly as Plan 3C drew them.
They are now the least artboard-like part of the screen, and wire labels still collide mid-canvas.
