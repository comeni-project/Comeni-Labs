# Plan 3C — Mendel, the builder

> **For the executor:** drive this with `superpowers:executing-plans`, task by task, yourself.
> `CLAUDE.md` forbids farming implementation out to subagents here. **Tick each `- [ ]` as it
> completes**, and where a step was carried out differently, tick it anyway and record the
> deviation in that phase's execution-record table.

**Goal:** show a pipeline Mendel already resolves — every step, every wire, every decision and
the tier it exited at — on a canvas a biologist can read.

**Architecture:** two backend prerequisites first, both pure and golden-tested, then the
interface in thin layers with the operator looking at three named points. Layout is computed in
Python, not in the browser, so the same IR gives the same coordinates forever.

**Tech Stack:** Python 3.12 / Pydantic / FastAPI, React 19 / TS / Vite / Tailwind 4, generated
TS client (`make client`).

**Design:** [`docs/design/dashboard.md`](../../docs/design/dashboard.md) §4–§8, and
[`docs/design/dashboard.html`](../../docs/design/dashboard.html) — **922 lines of working pan,
zoom, drag and orthogonal wire routing.** Read both before phase 3. This is the difference
between 3C and the forge: there is a design to execute, so **do not invent screens**.

**Spec:** [`notes/specs/2026-08-18-the-interface.md`](../specs/2026-08-18-the-interface.md) §3C.

---

## Why this plan has checkpoints, and where they are

**3D's interface was rejected three times.** The cause was not execution — the ranking, the API
and the guards were sound — it was that *nobody had designed the screens and I designed them as I
built*. 3C removes that failure mode: `dashboard.md` specifies resize ranges in pixels, zoom
clamps, corner radii and which settings groups open by default.

What it does not remove is the risk of getting the **shell** wrong and then building eight
phases on top of it. So:

| checkpoint | after | what the operator is looking at | cost if wrong |
|---|---|---|---|
| **1** | phase 3 | three columns, drag-resize, collapse to rail, empty canvas that pans and zooms | ~1 phase |
| **2** | phase 5 | nodes and wires actually laid out, nothing interactive | ~2 phases |
| **3** | phase 8 | the whole builder | the plan |

**At each checkpoint: stop, run `make dev`, and say plainly what to look at.** Do not continue
to the next phase without an answer. That is the whole mechanism — a checkpoint that gets
narrated past is not a checkpoint.

## Global constraints

- **`make verify`, not `make check`.** Phases 0–1 touch `resolve_verbs.py`, which is on the named
  list; run `make verify` unpiped, so the exit code is `make`'s.
- **Byte-identical emission survives.** Phase 0 moves the orchestration and must not change one
  byte of `pipeline.yml` or `main.nf`. `tests/test_counts.py` and the golden files are the check.
- **Layout is deterministic.** Same IR → same coordinates, held by a golden file. Invariant 10
  is about `.nf`, and this extends the same discipline to the thing a person will screenshot.
- **`frontend/src/api/` is generated.** `make client` after any API change; never hand-edit.
- **The frontend gate is `npm run build` (`tsc -b`).**
- **No new design token, colour, radius or font.** `dashboard.md` §2 is the token system and it
  already covers this screen — that is what it was written for.
- **An absence is not a zero.** Anything unmeasured renders `—`.
- **Guards must be watched failing.**

## Two things the design says that this plan deliberately does not build

Stated here rather than discovered in phase 7.

- **The "Ask Mendel" tab is out of scope.** `dashboard.md` §6 designs a right rail of three tabs
  and the third is a chat that turns prose into a typed goal. That is **door 1**, the prompt
  door, and the interface spec §3C says plainly *"AI is not in 3C either — #69 first, then the
  tier-4 resolver."* The rail ships with **two** tabs. The design is not wrong; it is ahead.
- **Drag-to-connect is out of scope**, per `dashboard.md` §9's own gap list. Ports render with
  their hollow/filled state and hit targets, because those are what a later phase needs; the
  drag behaviour is not built.

## What the canvas opens on — decided here, because nothing else decides it

**Nothing stores a pipeline.** There is no table, no `pipelines` model, and 3C is not the phase
to add one. The AI path that would supply a goal is out of scope per above.

So the builder takes a **typed goal** and renders what the engine resolves from it:

- `POST /api/pipeline` with a `Goal` → a resolved pipeline with layout, in memory, nothing written
- the screen opens on `examples/rnaseq-goal.yml`, which produces the five-module spine today

**This is deliberately not persistence.** A `pipeline.yml` is already the save file
(`CLAUDE.md`: *the artifact on disk **is** the payload*), and inventing a second home for it in a
database is the kind of decision that should be made when something needs it, not to make a
screen easier. Phase 8's execution record must say whether that held.

---

## Phase 0: the orchestration seam

**No interface. The prerequisite the last three plans all named.**

`resolve_verbs.run(args, parser)` is one ~190-line function that takes an argparse `Namespace`,
loads layers, resolves, and writes files. No API can call it.

**The good news, verified before writing this:** the core is already clean. Lines ~136–148 are
`resolve(...)` → `ir` → `Pipeline.of(...)`, in memory, and the function's own comment says
*"nothing here needs files on disk: `verify` differs from `upgrade` only in whether bytes are
written."* **This is a lift, not a rewrite.**

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/orchestrate.py`
- Create: `packages/mendel-compiler/tests/test_orchestrate.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli/resolve_verbs.py`

**Interfaces:**
- Produces: `orchestrate.build(goal: Goal, *, registry_root: Path, vendor_root: Path,
  registry_roots: list[Path] | None = None, prior: Pipeline | None = None,
  resolver: AmbiguityResolver | None = None) -> Built` where
  `Built = NamedTuple(pipeline: Pipeline, ir: PipelineIR, layers: Layers)`.
- **Takes roots, returns objects, writes nothing.** The CLI keeps every path decision and every
  byte written; the API gets the half that has no filesystem in it.

- [ ] **Step 1: Write the failing test — the seam produces what the CLI produces**

Create `packages/mendel-compiler/tests/test_orchestrate.py`:

```python
"""The build path, callable without argparse.

**This is the prerequisite three plans named and none built.** `resolve_verbs.run` takes a
`Namespace` and writes files, so `mendel-api` could not call it — which is why 3C came last.

The test that matters is not that the function exists. It is that **it produces byte-identical
output to the CLI**, because a seam that quietly changes the artifact is worse than no seam.
"""

from pathlib import Path

from comeni_core import yaml_strict
from mendel_resolver.goal import Goal

from mendel_compiler import orchestrate, pipeline_file

ROOT = Path(__file__).resolve().parents[3]


def test_the_seam_builds_the_spine_without_touching_disk(tmp_path):
    goal = Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))
    built = orchestrate.build(
        goal, registry_root=ROOT / "registry", vendor_root=ROOT / "vendor"
    )
    assert built.pipeline.steps, "the spine has steps"
    assert list(tmp_path.iterdir()) == [], "the seam wrote nothing"


def test_the_seam_and_the_cli_agree_byte_for_byte(tmp_path):
    """**The only assertion that makes the extraction safe.**

    Moving orchestration is exactly the change `make check` waves through — nothing outside
    `test_counts.py` runs a tool, so a lost flag is invisible. This compares the serialised
    artifact, which is what `mendel emit` reads and what a person reviews.
    """
    import subprocess
    import sys

    out = tmp_path / "cli"
    subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "build",
         "--goal", str(ROOT / "examples" / "rnaseq-goal.yml"), "--out", str(out)],
        check=True, cwd=ROOT,
    )
    from_cli = (out / pipeline_file.FILENAME).read_text()

    goal = Goal.model_validate(yaml_strict.load(ROOT / "examples" / "rnaseq-goal.yml"))
    built = orchestrate.build(
        goal, registry_root=ROOT / "registry", vendor_root=ROOT / "vendor"
    )
    seam = tmp_path / "seam"
    seam.mkdir()
    pipeline_file.write(seam, built.pipeline)
    assert (seam / pipeline_file.FILENAME).read_text() == from_cli
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_orchestrate.py -v`
Expected: `ModuleNotFoundError: mendel_compiler.orchestrate`.

**Three imports were verified against the code while writing this**, and two were wrong in the
first draft: `Goal` is `mendel_resolver.goal`, not `comeni_core.goal`, and `pipeline_file` is
`mendel_compiler`, not `comeni_core.artifact`. `python -m mendel_compiler.cli` is a real entry
point and its `__main__.py` exists precisely so tests can subprocess it — the console script
`mendel` points at `main` directly and never reaches it. Written against `resolve_verbs.py` at
`1a88867`.

- [ ] **Step 3: Lift the core into `orchestrate.py`**

Move the block that loads layers, builds the registry, resolves and constructs the `Pipeline` —
`resolve_verbs.py` lines ~46–150 minus every `args.*` reference — into `orchestrate.build()`.

**Keep in the CLI, deliberately:** every path decision, `--out` collision checks, the divergent
directory refusal, `--dry-run`, the upgrade report, and all writing. Those are a *transport's*
job, and the forge's `cli/` holding no logic is the shape to copy.

Write the module docstring against what was learnt:

```python
"""The build path, as a function.

**Extracted in Plan 3C phase 0**, and it is a lift rather than a rewrite: the core was already
in memory. `resolve_verbs.run`'s own comment said so — *"nothing here needs files on disk:
`verify` differs from `upgrade` only in whether bytes are written"* — and what kept it
uncallable was the `Namespace` around it, not the work inside.

**Takes roots, returns objects, writes nothing.** Every path decision and every byte stays in
the CLI, which is the same split `mendel_forge.cli` already has: a transport holds no logic.

`test_the_seam_and_the_cli_agree_byte_for_byte` is what makes this safe. Moving orchestration
is precisely the change `make check` waves through, because nothing outside `test_counts.py`
runs a tool.
"""
```

- [ ] **Step 4: Make the CLI call it**

`resolve_verbs.run` now parses `args`, calls `orchestrate.build(...)`, and writes. Its length
should fall by roughly half.

- [ ] **Step 5: Run the byte-identity test, then `make verify`**

Run: `uv run pytest packages/mendel-compiler/tests/test_orchestrate.py -v` then
`make verify > /tmp/v.log 2>&1; echo $?` — **unpiped**.

Expected: both pass. **A changed golden file here is a defect, not a golden to regenerate.**

- [ ] **Step 6: Commit**

---

## Phase 1: DAG layout, in Python

**`dashboard.md` §9 calls this "the largest outstanding piece"**, and it is the one part of 3C
that is an algorithm rather than a rendering.

**In Python, not in the browser, and that is a decision rather than a convenience.** Same IR →
same coordinates, golden-file tested, exactly as `.nf` is. A browser library (dagre, elkjs) would
put the position of every box outside the determinism guarantee and add a dependency to compute
something the backend already has the graph for.

**Layered, Sugiyama-style**, which for this graph is not hard: the RNA-seq spine is a chain with
two branches.

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/layout.py`
- Create: `packages/mendel-compiler/tests/test_layout.py`
- Create: `packages/mendel-compiler/tests/golden/rnaseq-spine.layout.json`

**Interfaces:**
- Produces: `layout.of(ir: PipelineIR) -> Layout` where `Layout` carries
  `nodes: list[Placed]` (`id`, `column`, `row`, `x`, `y`) and `wires: list[Wire]`
  (`from_node`, `from_port`, `to_node`, `to_port`, `type_id`, `points: list[Point]`).
- **Coordinates are integers**, so a golden file compares exactly and no float formatting can
  drift between machines.

- [ ] **Step 1: Write the failing test**

```python
"""Where the boxes go.

**Deterministic, and in Python for that reason.** A browser layout library would put the
position of every node outside the guarantee the rest of the system keeps — same input, same
output, byte for byte — and the canvas is the thing a person screenshots.
"""

def test_a_producer_is_left_of_its_consumer(spine_ir):
    placed = {n.id: n for n in layout.of(spine_ir).nodes}
    for wire in layout.of(spine_ir).wires:
        assert placed[wire.from_node].column < placed[wire.to_node].column


def test_the_same_ir_lays_out_identically(spine_ir):
    assert layout.of(spine_ir) == layout.of(spine_ir)


def test_the_layout_matches_the_golden_file(spine_ir):
    """Regenerate with LAYOUT_GOLDEN=update, and READ the diff. A layout change is a visual
    change, and the golden file is the only place it is reviewable before somebody sees it."""
    ...


def test_nothing_overlaps(spine_ir):
    """Two nodes in one column may not share a row — the failure that makes a graph unreadable
    rather than merely ugly."""
    ...
```

- [ ] **Step 2: Run, watch fail.**
- [ ] **Step 3: Implement.** Longest-path layering for columns, then order within a column to
      reduce crossings (median heuristic, two passes — sufficient for a spine, and say so in the
      docstring rather than implying more).
- [ ] **Step 4: Wire routing.** Orthogonal, down-across-down, **7px corners** — `dashboard.md`
      §4's reason is crossings, and it must be quoted in the docstring so a later refactor to
      beziers has to argue with it.
- [ ] **Step 5: Golden file, read not just regenerated.**
- [ ] **Step 6: `make verify`, commit.**

---

## Phase 2: the API

**Files:** Create `packages/mendel-api/src/mendel_api/services/build.py`,
`routes/build.py`, `packages/mendel-api/tests/test_build_route.py`.

**Interfaces:**
- Produces: `POST /api/pipeline` taking `{goal: Goal}` → `BuiltPipeline`:
  `steps`, `settings`, `wires`, `layout`, `provenance` (count per tier), `needs_review`.
- Produces: `GET /api/pipeline/example` → the same, built from `examples/rnaseq-goal.yml`, so
  the screen has something to open on before anything can author a goal.

- [ ] **Step 1: Write the failing test** — the example route returns a spine with steps, wires
      with points, and a provenance count summing to the number of decisions.
- [ ] **Step 2: Run, watch fail.**
- [ ] **Step 3: Implement**, composing `orchestrate.build` and `layout.of`. Cache on the goal's
      digest the way `registry.stack()` caches — a resolve is ~0.4s and the 0.5s budget is the
      operator's stated floor.
- [ ] **Step 4: Add it to `test_every_operation_is_named_by_hand`** — that guard holds a literal
      list and will refuse until you do.
- [ ] **Step 5: `make client`, `make verify`, commit.**

---

## Phase 3: the shell, and nothing in it

**This phase deliberately ends with an empty canvas.** Three columns, both panels resizing and
collapsing, a canvas that pans and zooms over a dot grid — and no nodes, no rail content, no
picker rows.

**`dashboard.html` is the reference and it works.** Port its behaviour rather than reinventing:
pan by dragging empty space, wheel zooms toward the cursor **clamped 30%–220%**, node drag
divides deltas by the zoom factor, the dot grid scales with the view.

**Files:** Create `frontend/src/build/Builder.tsx`, `Canvas.tsx`, `Rail.tsx`, `Builder.test.tsx`;
modify `router.tsx`, `Shell.tsx` (the `Builder` tab stops being `Soon`).

- [ ] **Step 1: Write the failing test** — the two panels resize within their declared ranges
      (**190–430 left, 280–560 right**), collapse to a **42px** rail, and the collapsed rail
      still shows its undecided count. That last one is `dashboard.md` §4's own rule: *hiding the
      panel must never hide what is blocking your run.*
- [ ] **Step 2: Run, watch fail.**
- [ ] **Step 3: Build the three columns and the resizers.**
- [ ] **Step 4: Build the canvas shell** — pan, zoom, dot grid, the −/+/reset/Fit buttons bottom
      right. No nodes.
- [ ] **Step 5: `npm run build`, `npx vitest run`, `make verify`.**
- [ ] **Step 6: Commit.**

### ▸ CHECKPOINT 1 — stop here

- [ ] **Run `make dev` and hand it over.** Say: *the shell only — drag both panel edges,
      double-click to collapse, pan and zoom the empty canvas.* Name what is deliberately absent
      so it is not read as broken.
- [ ] **Wait for an answer. Do not start phase 4.**

---

## Phase 4: nodes and wires

> **Correct this phase against phase 1's real `Layout` and phase 2's real response before
> executing.** Written against the shapes declared above; they will have moved.

- [ ] **Step 1: Write the failing test** — a node renders per step with its tier stripe; a wire
      renders per edge with its type label on the horizontal run; the count matches the API.
- [ ] **Step 2: Run, watch fail.**
- [ ] **Step 3: Render nodes** at the coordinates the backend computed. **The frontend does no
      layout arithmetic** — if it is computing a position, phase 1 is incomplete.
- [ ] **Step 4: Render wires** from the points the backend computed.
- [ ] **Step 5: Node drag**, dividing by zoom. Dragging moves a node **in the view only** — there
      is nowhere to persist it and inventing one is out of scope.
- [ ] **Step 6: `npm run build`, `make verify`, commit.**

---

## Phase 5: the provenance bar

**`dashboard.md` §4: *"the product thesis compressed into one element."*** A 10px strip above the
canvas, segmented proportionally by tier, headlined **"N% settled without judgement"**. Clicking
a band isolates those steps.

- [ ] **Step 1: Write the failing test** — the segments are proportional to the tier counts, the
      headline is the tier-1+2 share, and clicking a band filters the canvas.
- [ ] **Step 2: Run, watch fail.**
- [ ] **Step 3: Build it.**
- [ ] **Step 4: Check the honesty case** — a pipeline with a tier-4 decision must not read as
      settled. Add the assertion.
- [ ] **Step 5: `make verify`, commit.**

### ▸ CHECKPOINT 2 — stop here

- [ ] **Run `make dev` and hand it over.** Say: *the spine, laid out automatically, with the
      provenance bar. Nothing is clickable except the bar.*
- [ ] **Wait for an answer. Do not start phase 6.**

---

## Phase 6: the settings card

> **Correct against what exists.** `ParamDecision` and `Why` carry the tier, the reason and the
> candidates; read them before writing the groups.

Groups **by how each was decided, ordered by what needs attention** — `dashboard.md` §5:

```
Needs your decision   ← open by default
Check the premise     ← open by default
Standard practice     ← collapsed
Forced by inputs      ← collapsed
```

- [ ] **Step 1: Write the failing test** — four groups, the first two open, undecided fields
      carrying the coral border, and a parameter with alternatives rendering a `<select>`.
- [ ] **Step 2: Run, watch fail.** — [ ] **Step 3: Build it.** — [ ] **Step 4: `make verify`, commit.**

---

## Phase 7: the right rail — two tabs

**Two, not three.** The *Ask Mendel* tab is door 1 and out of scope; see the section above.

- **Step details** — ports with types, a button to the settings card, and every judged parameter
  with **what else was considered and why each was rejected**, which is `DecisionRecord.candidates`
  rendered directly.
- **Review** — red first, then yellow; clicking one selects that step on the canvas.

- [ ] **Step 1: Write the failing test** — the review count badge hides at zero, and clicking a
      review row selects the node.
- [ ] **Step 2: Run, watch fail.** — [ ] **Step 3: Build it.**
- [ ] **Step 4: One Run button, in the nav**, carrying the blocking count. `dashboard.md` §6
      records that there were two and both were disabled by the same condition.
- [ ] **Step 5: `make verify`, commit.**

---

## Phase 8: close it

- [ ] **Step 1: The module picker** (left panel) — grouped by role, with the hover description
      card beside the panel rather than under the cursor.
- [ ] **Step 2: Empty and failed states** that explain the screen, and `<Term>` on the first use
      of each word. Phase 5 of 3D is the shape.
- [ ] **Step 3: `useTitle`** — a builder tab says which pipeline it is showing.
- [ ] **Step 4: `make verify` unpiped, `make links`, `npm run build`.**
- [ ] **Step 5: Journal, `notes/README.md`, `notes/journal/README.md`, `CLAUDE.md`.**
- [ ] **Step 6: Commit.**

### ▸ CHECKPOINT 3 — the whole builder

- [ ] **Run `make dev` and hand it over.**
- [ ] **Record the verdict in the journal**, whatever it is. 3D's journal recording *"the
      operator rejected this three times"* is worth more than a green test.

---

## Self-review

**Design coverage:**

| `dashboard.md` | phase |
|---|---|
| §2 tokens | none — they exist and must not grow |
| §3 ports | 4 (render), drag-to-connect **out of scope** per §9 |
| §4 layout, three columns, rail collapse | 3 |
| §4 canvas: pan, zoom clamps, dot grid | 3 |
| §4 orthogonal wires, 7px corners | 1 (routing), 4 (render) |
| §4 provenance bar | 5 |
| §4 module picker + hover card | 8 |
| §5 settings card, four groups | 6 |
| §6 right rail — Step, Review | 7 |
| §6 Ask Mendel | **out of scope** — door 1, spec §3C |
| §6 one Run button in the nav | 7 |
| §7 copy rules | 8 |
| §8 motion | 3–4, inline |
| §9 DAG layout | **1 — the largest piece, and it moved to the front** |

**Known gaps, stated rather than hidden:**

- **Phases 4–8 are thinner than 0–3**, deliberately: they consume types phases 1–2 create.
  Correct each against the real shape before executing. Writing them in false detail now is what
  `notes/README.md` row 17b says killed Plan 2.
- **Nothing persists a pipeline**, and this plan does not add persistence. If phase 8 finds the
  screen unusable without it, that is a finding for the journal and a decision for the operator —
  not a table added quietly.
- **Three imports in phase 0's test were verified and two were wrong** — see step 2. Every other
  type this plan names (`PipelineIR`, `Pipeline`, `ParamDecision`, `Why`, `DecisionRecord`,
  `AmbiguityResolver`) exists but its **shape has not been checked field by field**. Read before
  writing, per this repository's own rule.
- **`docs/design/dashboard.html` has not been read line by line yet.** Phase 3 step 4 depends on
  porting its pan/zoom maths; budget for reading 922 lines before writing that step, and if it
  disagrees with §4, **the HTML is what works** and the prose is what drifted.
