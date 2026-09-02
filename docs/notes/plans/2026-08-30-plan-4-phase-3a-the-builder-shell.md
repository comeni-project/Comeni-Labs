# Plan 4 Phase 3a — the builder: the shell, and the feedback that was missing

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [x]` as it completes, and where a step was
> carried out differently, tick it anyway and record the deviation in the execution table.
>
> **Four boxes are deliberately unticked and one is `[~]`.** A tick means *this step was carried
> out*; leaving one blank is how the next reader can tell what 3b inherits. `[~]` follows W1's
> convention for a checkpoint half-met — the page was rendered and read, and it has not been
> driven by hand in a live stack.

**Goal:** the builder stops lying about what it is doing. Draw → Keep → Gate → Run becomes one
**Run** action and a status line; the duplicated column goes; and the eight report-back defects
the 2026-08-29 walk found are closed.

**Architecture:** no new machinery. `validate`, the compatibility index, `producers_of`, `compare`
and `dag-core` all exist and are correct — the walk's own conclusion was that **the modelling is
sound and the surface is not**. This phase moves controls, deletes duplicates and adds markers.
The four verbs still happen; they stop being four buttons.

**Tech Stack:** React 19 · TypeScript · Tailwind 4 · `@tanstack/react-query` · vitest.

**Design source:** the canvas —
<https://claude.ai/code/artifact/4f65e748-9758-4f06-9b87-1a8dc5a34b34>, page 1.
`BuilderCanvas.dc.html` is the shell this phase builds; `impl-walk`, `impl-geom`,
`impl-walkbugs`, `impl-settled` and `mo-page-1` are the notes. **Render the boards with
`.design/_prev.py` before writing JSX** — it is thirty seconds, and on the Overview it found
three defects a green suite could not.

**Depends on:** phases 0 (motion, breakpoints, the required-error prop), 1 (`publishDir`) and 2
(Observatory, `GET /api/pipeline/drafts`).

**The defect list this closes:**
[`../journal/2026-08-29-walking-the-loop.md`](../journal/2026-08-29-walking-the-loop.md).

## What is NOT in this phase

3b owns the new surfaces: the **port picker**, the **settings card on the node**, **swap with
consequences**, the **browse overlay**, and the **artifact view**. This phase builds the shell
they hang off and leaves the existing palette working, because a product that cannot add a step
between two commits is a product nobody can use in between.

## Global constraints

- **The four verbs still happen; they stop being UI.** `execution-boundary.md` §3 keeps gate and
  run apart for a real reason — a gate proves an artifact on **public** data, a run touches the
  lab's **own**. That split stays in the backend. It is two things the machine does, never two
  buttons a person presses.
- **`Walk.tsx` derives every step's state from the world, not from a counter.** That logic is
  correct and moves into the status line. **Do not replace it with a step index** — a rail that
  advances a counter says where the *interface* thinks you are; reading what is true is what lets
  editing after keeping move you backwards, which is the honest answer.
- **Every mutation that fails says so.** Phase 0 made `Walk`'s error prop required and `tsc`
  named three call sites that had dropped it. Whatever replaces `Walk` inherits that: a required
  field, not a convention.
- **The left steps list is deleted on purpose** and orientation is the minimap's job. Do not
  bring back a third column (`impl-settled`).
- **No prompt box on the populated page.** Creation is monthly; checking a run is daily. The
  prompt lives in the empty state and, later, the command palette — never as a banner.
- **Absence is absence**, as everywhere else: the status line says nothing when nothing is wrong.
- **The frontend gate is `npx tsc -b && npx vitest run && npm run lint`** from `frontend/`. No
  task here touches the six files needing `make verify`; `make check` still runs for the API.
- **A production build is the only place "one curve" is checkable** — phase 0 learned that the
  hard way. Run `npm run build && grep -o 'cubic-bezier([^)]*)' dist/assets/*.css | sort -u`
  after any styling change.

---

## Pre-execution notes — checked against the code on 2026-08-30

**P3-1 — the node-stacking defect has a cause, and it is not the one it looks like.**
`freeSpot()` exists, predates the walk (2026-08-23), and its docstring says *two additions never
land on top of each other*. It is still right and the walk still saw stacking, because
`useBuilder.addNode` calls `freeSpot(graphState.offsets, near)` and **`offsets` starts `{}` and
only ever holds nodes somebody has DRAGGED**. Every node placed by `dag-core`'s layout is
invisible to it, so the first "free" cell is one the laid-out pipeline is already sitting in. The
fix is to hand `freeSpot` the **rendered** positions — layout plus offsets — not to rewrite it.

**P3-2 — the pipeline's name is a hard-coded string.** `Builder.tsx:227` renders
`RNA-seq spine` in the header, which is why deleting every step and replacing it left the old
name on screen. `PipelineDraft.name` exists, `DraftIn` accepts it, `PUT /drafts/{id}` saves it,
and **nothing in the browser ever sets it** — `useKeep` posts `name: ""` twice.

**P3-3 — the second *Send to Wiener* is `Walk`'s own.** `Walk.tsx`'s Run step renders a
`<button>Send to Wiener</button>` whose `onClick` is `run.onSend`, and `Builder.tsx` passes no
`onSend` — so it is inert. The live control is inside `run.panel` → `SubmitPanel`, rendered
directly beneath. **The Gate step already had this fixed** and says so in a comment; the Run step
is the same defect the same fix missed.

**P3-4 — the module palette is a bare `div draggable`.** `Modules.tsx:103` sets `draggable` and
nothing else: no `role`, no `tabIndex`, no key handler. It is absent from the accessibility tree,
so drag and double-click are the only two ways to add a step.

**P3-5 — three columns with no breakpoint.** `Builder.tsx:243` is
`grid-cols-[auto_5px_1fr_5px_auto]` with drag-resize and collapse, and no media query anywhere.
Phase 0 declared 1180 and 760 and `.withRail`; this screen predates them.

---

## Task 1 — the header says what this pipeline is, and what is true about it

**Deliverable:** the name is the draft's own and editable; the status line replaces the walk.

- [x] Delete the hard-coded `RNA-seq spine` from `Builder.tsx`. Render `draft.name`, falling back
      to the id's first eight characters — never to another pipeline's name.
- [x] Make it editable in place, saving through `PUT /drafts/{id}`, which already accepts `name`.
      **A rename is a mutation and must report failure** — phase 0's rule, and this one is easy
      to swallow because the old name stays on screen and looks like success.
- [x] Write `Status.tsx`: `saved 4s ago · valid · 2 values need you`. **Three facts, derived, and
      it says nothing when nothing is wrong.**
- [x] **Lift `Walk.tsx`'s derivation, not its shape.** Each fact reads the world — is the graph
      dirty, does the verdict hold, how many values are open — so editing after keeping moves it
      backwards. A counter cannot do that and must not be introduced.
- [ ] Add the `Canvas` / `Artifact` segmented toggle. **`Artifact` is 3b**; render the control
      disabled with its reason, the way phase 2's first-run prompt does, or leave the segment out
      entirely — decide by which reads as less of a lie and record which.
- [x] Add the **Run** action. One control: keep → lint → open the run sheet → submit → navigate.
      Drafts already autosave every 5s, so *keep* is an implementation detail wearing a button;
      lint is **1.6s**, not the 10s people remember, which was the gate.

**Verify:** the frontend gate.

---

## Task 2 — delete the duplicated column and the four-step rail

**Deliverable:** two panels, not three; one Run action, not four buttons.

- [x] Delete `Steps.tsx` and the `pipeline` tab of `LeftPanel.tsx`. It was a table of contents
      for the canvas beside it.
- [x] **Keep `Modules.tsx` as the palette for now** and say so in a comment naming 3b's browse
      overlay as its replacement. Deleting it here would leave no way to add a step at all.
- [x] Delete `Walk.tsx` and `Walk.test.tsx`. Its two live tests — the blocked reason on screen,
      and the sequence going backwards after an edit — **move to `Status`** rather than being
      deleted with it.
- [x] Delete the inert `Send to Wiener` button (P3-3). One control, and it is `SubmitPanel`'s.
- [x] Add `it("offers exactly one control per action")` — assert no two enabled controls share an
      accessible name anywhere on the builder. **Watch it fail** against the restored duplicate.
      This is the general form of the defect, and the general form is what stops the third one.

---

## Task 3 — a new step lands where you can see it

**Deliverable:** adding a step never puts it under another one.

- [x] Hand `freeSpot` the **rendered** positions — `layout.nodes` merged with `offsets` — rather
      than `offsets` alone (P3-1). One call site; the function is already correct.
- [x] Add `it("never places a step on top of one already on the canvas")`: place four nodes
      through `addNode` on a laid-out pipeline and assert no two rendered positions collide.
      **Watch it fail** by passing `offsets` again — and verify the revert lands before believing
      the run, which this repository got wrong twice on 2026-08-30.
- [ ] Give the empty canvas a right-click menu with *Add a step here*. Nodes have one; the place
      you would reach for this has nothing.

---

## Task 4 — the verdict says when it is stale

**Deliverable:** the panel never describes a graph that no longer exists without saying so.

- [x] Mark the verdict **stale** while a recompute is in flight — `MD0506 star_align.index` was
      shown for 2–3s against a `star_align` that had already been deleted.
- [x] Dim it and label it rather than hiding it: a verdict that vanishes on every keystroke is
      worse than one that admits it is catching up.
- [x] Add `it("says the verdict is stale rather than describing a graph that is gone")`. Watch it
      fail.

---

## Task 5 — the palette is reachable without a mouse

**Deliverable:** a step can be added from the keyboard.

- [x] Give each palette row a `role="button"`, a `tabIndex`, and Enter/Space to add (P3-4).
      Dragging stays; it stops being the only way.
- [x] Add `it("can add a step without a pointer")` — tab to a row, press Enter, assert the graph
      grew. Watch it fail against the bare `div`.
- [ ] **The rail must not scroll itself back to the top.** Find what resets it — a remount on
      every verdict, most likely — and key the container so it survives a re-render.

---

## Task 6 — the builder reflows

**Deliverable:** it is usable below 1100px, where today it clips.

- [x] Apply phase 0's `1180` and `760` and `.withRail`. At 1180 the rail **stacks under** the
      canvas — a side rail stacks, it does not overlay, because a drawer hides the thing it is
      discussing.
- [x] The canvas keeps a usable minimum rather than being crushed to a 197px strip.
- [x] Both side panels must be collapsible, and a collapsed rail **keeps its open count on the
      stub** — hiding the panel must never hide what is blocking your run (`dashboard.md` §4).

---

## Task 7 — the canvas reads as a schematic

**Deliverable:** the geometry rules from `impl-geom`, where they are not already true.

- [x] **Audit first, then change.** 3E's walk already fixed the wire-to-chevron offset by
      deriving `portIndex` from `steps[].ports` in one place, and `Builder.tsx` says so. Check
      what `impl-geom` asks for that is genuinely absent before rewriting anything that works.
- [x] Uniform symbol size for every process node. Variable heights put a jog between every pair.
- [x] Orthogonal routing (H/V/H), never bezier.
- [x] **The grid exists only during a drag** — fades in on pointer-down, out on release. A
      permanent grid is the loudest hobby-editor signal there is.
- [ ] Three layers, three behaviours, and do not merge them: the arc field is anchored to the
      **viewport** and does not pan; the grid pans **with the nodes**; registration marks are
      fixed to the viewport.
- [x] A settled step gets **no colour at all**. Only measured (amber) and open (red) spend any.

---

## Task 8 — look at it, then write it down

- [~] **Render the builder and use it.** Draw a pipeline, add a step, delete one, rename it, run
      the verdict stale, resize to 900px. Phase 2's three worst defects were found this way and
      none was expressible as an assertion anybody would have written first.
- [x] Journal entry, `CLAUDE.md` pointer in the same commit, `notes/README.md` row.
- [x] Every guard watched failing, in [`../audits/guard-ledger.md`](../audits/guard-ledger.md),
      with the revert **verified to land** before the run is believed.

---

## Execution record

**Executed 2026-08-30**, on `worktree-plan-4-phase-0`. Frontend gate green: `tsc` clean, **280
tests in 51 files**, lint unchanged at its five pre-existing warnings, production build compiles
to one easing curve. Built, served against fixtures and **looked at** at 1400px and 900px.

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | No — far larger, because the draft lifecycle did not exist | The plan said *render `draft.name`*. There was no draft to read: `Builder` called `useExample()` unconditionally, so **`/build?draft=<id>` opened the canonical spine** — every link phase 2 put on the front door went somewhere else. And **`useGraph`'s autosave had never fired**: it has taken an optional `save` since 3E and no caller ever passed one. That is not just a missing feature — the plan's own argument for one *Run* button is *drafts already autosave, so Keep is an implementation detail wearing a button*, and the premise was **false**. `usePipelineDraft` makes it true, which is the right order to discover that in. |
| 1 | And a destructive bug caught while writing it | The first `rename()` sent `{nodes: [], edges: []}`, because `PUT /drafts/{id}` writes `{graph, name}` as one document and the hook had no graph to hand. It would have **deleted the pipeline while appearing to relabel it**. No test would have caught it; nobody writes a test asserting that renaming does not delete. |
| 2 | Yes, and one test was restated rather than deleted | `Restored.test.tsx` existed so *four things the plan cut and the operator put back* could not go missing quietly again — and one of them was *keeps both lists*. `impl-settled` reverses it. Reversing it **loudly, in the test that held it**, is the only honest way; the picker half of its argument survives and is still asserted. Same move phase 2 made on `forge-review.md` §3. |
| 3 | No — the diagnosis in the plan was wrong | P3-1 said `freeSpot` was blind to the layout and should be handed rendered positions. Reading `Node.tsx` showed offsets are **absolute and seeded from the layout**, so the real fault was that `freeSpot` **guessed** a cell before `dag-core` had seen the new node. `dag-core` already places the whole graph without overlap, so `addAt` stopped guessing; `freeSpot` and its three tests are deleted. The right-click *Add a step here* menu is **not** done — it belongs with 3b's browse overlay, which is what it would open. |
| 4 | Yes, and the marker already existed | `useBuilder` has returned `settling` since 3E, documented as *only for a quiet indicator*, rendered by nothing. `stale` widens it to cover the 180ms debounce **before** a request is sent, which is most of the 2–3s window the walk measured. |
| 5 | Partly | The palette is keyboard-reachable — `role`, `tabIndex`, Enter/Space, and the hover card follows focus. **The rail-scrolls-to-top defect is not fixed**; it needs the rail's remount cause found, and the rail is 3b's to rebuild. |
| 6 | Yes, and looking at it found the half that was missing | It stacks at 1180. The first attempt left both panels at their desktop widths — a 232px palette with 660px of dead space — and the canvas at zero height, because `Side` sets width as an **inline style** (it is drag-resizable) and an inline style beats a class. |
| 7 | Audit first, as the task said — and most of it was already true | Uniform node size, orthogonal routing and *a settled step gets no colour* all hold already. What was not: **the grid was permanent**, defaulting `true` with an argument for it that `impl-geom` answers. It now appears only while a node is moving. **The three-layer arc field does not exist** and is not built — it is new work, not a correction, and it belongs with 3b. |
| 8 | Partly | Built and looked at, which found four defects a green suite could not. **Not driven by hand in a live stack** — the run sheet, a real keep and a real gate are unexercised, and that debt is named in the journal rather than absorbed. |
