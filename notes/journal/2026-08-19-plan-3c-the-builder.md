# 2026-08-19 (night) — Plan 3C: Mendel, the builder

## Where things stand

**Plan 3C is complete**, nine phases, on `plan-3c-builder` — branched from `main`, which now
carries 3A, 3B and 3D. **Not merged.**

`/build` shows a pipeline Mendel already resolves: every step, every wire, the tier each decision
exited at, and what still needs a person. The nav's `Builder` is a real link and **nothing in the
interface is disabled any more**.

```bash
make verify                                    # 1421 + 5 counts + 75 guards, exit 0
cd frontend && npx vitest run && npm run build # 100 tests, tsc -b green
curl -s localhost:8000/api/pipeline/example | head
```

## What made this different from 3D

**There was a design.** `dashboard.md` §4–6 gives resize ranges in pixels, zoom clamps, corner
radii and which settings groups open by default; `dashboard.html` is 922 lines of working pan,
zoom and orthogonal routing. The plan's standing instruction was *do not invent screens*, and
holding to it is why this went differently.

**It earned itself immediately.** The plan assumed the graph flowed left to right. It flows
**downward** — `elbow()` routes vertical → horizontal at the midpoint → vertical. Every
structural assertion in the layout test would have passed on a sideways graph: *a producer is
left of its consumer* is exactly as satisfiable as *above*. The design was the only thing that
said which way is down.

## The checkpoints found three defects the suite structurally cannot

Written down because this was the argument for having them, and it turned out stronger than the
argument.

1. **`GET /api/pipeline/example` answered 500 in the container** and 200 everywhere else. The
   example goal was a bare relative path, resolved against the process's working directory —
   repository root under pytest, `/app` in a container, where `examples/` was not even mounted.
   Eight tests passed over it.
2. **The canvas had no height.** Wrapping it in a flex column under the provenance bar left it
   sizing to its content, and everything inside is absolutely positioned — so the bar rendered
   and the graph went into a zero-height box. **jsdom has no layout engine**, so this is not
   something any test in that file could be wrong about.
3. **Two worktrees, one port.** The containers collide loudly on fixed names; **Vite does not** —
   it takes 5174 and the banner still says 5173. Checkpoint 2 opened 3D's app, where `/build`
   does not exist, and Vite's SPA fallback answers **200** for an unknown path. My check was the
   status code; the operator's was the screen.

## Decisions made, and why

### Layout is computed in Python

Same IR → same coordinates, golden-file tested, exactly as the emitted `.nf` is. A browser layout
library would put the position of every node outside the guarantee the rest of the system keeps,
and the canvas is the thing a person screenshots.

**Reading the golden file found three defects no assertion had**: ordering is not placement (every
rank began at x=0, so the converging node hung off the left edge while a feeder sat 338px away); a
bare median picks the upper of two, so the first fix left it under one parent rather than between
both; and a straight drop emitted four points, two identical, handing the renderer a zero-length
segment to round.

### The provenance bar was counting the wrong thing

It counted **steps** and reported *0 needing a decision* on a pipeline whose `star_align.seq_platform`
exits at tier 4 and says, in its own artifact, *selected the first of 1 candidates without
judgement — please review*. `dashboard.html` counts **parameters**; this counts both, because a
module choice carries a tier too.

**Understating on the element that carries the product claim is the same failure as overstating**,
and the test for the other direction — *does not count a rule that read measured data as settled* —
had been written first. 80% became 78%, and *nothing to review* became *one*.

### Read-only, and the field is absent rather than disabled

The design's settings card has an editable input per row. Nothing in 3C persists an answer, so a
box that looks typeable and discards what you type is worse than a value that admits it is a
record. The card says so on the screen, not only in a docstring. Same reason a dragged node does
not stay dragged.

### Two tabs, not three

*Ask Mendel* is door 1 — a chat turning prose into a typed goal — and the interface spec §3C says
AI is not in 3C. Stated in the plan up front rather than discovered in phase 7.

### The left panel lists this pipeline's steps, not the registry

`dashboard.md` §4 designs a catalogue you drag from, which belongs with drag-to-connect — itself
on the design's own gap list. Browsing the registry already has a home in `Tools`, and a second
catalogue here would be the duplication 3D spent a phase removing.

## What is next

1. **Alignment tuning**, which the operator deferred to after the plan.
2. **Nothing persists a pipeline.** The canvas opens on `examples/rnaseq-goal.yml` because that
   is the only goal that exists. Editing, saving and opening a second one all wait on a decision
   about where a pipeline lives — and `pipeline.yml` is already the save file, so the answer may
   be a path rather than a table.
3. **[#77](https://github.com/comeni-project/Comeni-Labs/issues/77)** still open.

## Traps

- **Vite falls back silently when a port is taken.** Before any checkpoint:
  `pgrep -af bin/vite` and kill what is not this worktree. A 200 from `curl` proves nothing —
  the SPA fallback serves `index.html` for every path and the router renders not-found inside it.
- **jsdom has no layout engine.** Height, overflow and overlap are not things these tests can be
  wrong about. The guard added for the zero-height canvas asserts a **class name**, which is
  worth what testing a CSS string is worth; it names the failure so a refactor trips over it.
- **`COL_PITCH` was measured off the wrong elements for a phase.** The two things at `left:14`
  and `left:352` in `dashboard.html` are *input chips*, not modules. The real nodes are at 14 and
  290 — pitch **276**. The claim *"the geometry is the design's to the pixel"* was written in the
  same commit that took one pixel from a different kind of object.
- **`git checkout <file>` reverts the whole file.** Used to undo one experimental edit, it also
  reverted two good ones in the same file that had not been committed.
