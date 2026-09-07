# The living pipeline — the design canvas

Eleven artboards for [Task 1](../../docs/superpowers/plans/2026-09-07-the-living-pipeline.md) of
the living-pipeline plan: a researcher describes an analysis, and Comeni hands the pipeline
back one typed decision at a time on a canvas and a conversation that are two views of **one
draft**.

**Nothing in `frontend/` may change until these have been opened and compared.** That is the
plan's own checkpoint, and it is the 2026-09-01 lesson written as a gate — *reading finds wrong
strings; it does not find wrong pictures.*

```bash
cd .design && python3 living-pipeline/build_living.py     # rebuild every board from one fixture
cd .design && python3 _prev.py --dir living-pipeline --glob 'Living*'
# renders at 1400 and 900 into build/prev/. THE 900 PASS IS NOT OPTIONAL.
```

`--dir` is new. It exists because this canvas lives in a subdirectory and `_prev.py` globbed
`.design/` only — three flat canvases at the root is already one more than
[`.design/README.md`](../README.md) is comfortable with, and a canvas nothing cites yet has no
paths to rot.

---

## The boards

Every board is 1400 × 880 and composed from one shell, one canvas function and one fixture —
`S` in `build_living.py`. Change a count once and every board moves together, which is the
Forge canvas's rule and the reason its *5 ready for review* could not disagree with its five
rows.

| Board | The moment | What it has to get right |
|---|---|---|
| `LivingOpen` | the door | the live prompt, and Build vs Spawn as a real choice |
| `LivingGoal` | goal read back | have / want / organism / unsure, and the grouping question |
| `LivingBuild` | **the primary state** | four settled, one proposed as a ghost, alternatives |
| `LivingChoose` | an alternative | hover **and focus** preview, and the change set it drags |
| `LivingParam` | a tier-4 value | the question, the values card, a finding that does not block |
| `LivingCollect` | the grammar | 1→1, N→N, N→1 — and never N copies of a node |
| `LivingSpawn` | automatic | the same engine, and who chose what |
| `LivingTrouble` | five stops | pending, refusal, stale, failed, no model configured |
| `LivingDense` | hard content | fifteen steps, a long contract id, five ports, a long reason |
| `LivingQuiet` | narrower, and still | 1180 / 900 / 640, and every movement switched off |
| `LivingDone` | complete | the artifact grown as a projection, and who settled what |

Interaction states drawn across them: goal summary · goal edit · ambiguous grouping ·
module proposal · alternatives · ghost preview on hover · ghost preview on focus · substitution
preview · change set · parameter question · open-domain escape · validation finding · receipt
of a direct edit · collapsed decision · pending model · model refusal · stale proposal · failed
turn · no model configured · staged reveal · completion · artifact projection.

**Module browsing and the port picker are deliberately not redrawn.**
[`BuilderBrowse.dc.html`](../BuilderBrowse.dc.html) and
[`BuilderPort.dc.html`](../BuilderPort.dc.html) are established artboards for the same
overlays, reached the same way. A second drawing of one screen is a second
specification for it.

---

## The plan, and where it came from

### The palette and the type were not this canvas's to choose

Observatory, from [`frontend/src/tokens.css`](../../frontend/src/tokens.css), lifted **by
value**. Geist and Geist Mono. One curve, `cubic-bezier(.32,.72,0,1)`. `tokens.css` is
**unchanged by this design and no hue is added** — that is a deliberate constraint, not an
omission. A canvas that invents a colour for a new idea is how a product ends up with two
palettes and no tier ladder.

### The one idea: there is no inspector

The conversation **is** the inspector, because every object on the canvas was put there by a
decision that is already in the transcript. Select a node, the log scrolls to the decision that
created it. Select a card, the object highlights.

That is what dissolves the tab strip. `Builder.tsx` today stacks four bands of chrome above the
first sentence anybody wants to read — a panel header, its own three tabs, `Rail`'s own three
under those, and the gate panel. The living builder has **one strip and no tabs anywhere
beneath it**, because the rail has nothing to switch between. That is strictly *less* chrome
than what ships.

### Two encodings the product did not have, both extensions of a language it did

**Author is drawn as stroke; tier stays colour.** `impl-inv` fixes colour to the tier ladder —
settled spends none, measured is amber, open is red — so author cannot take a hue without
destroying what colour already says. Plan 3B settled the other axis: *certainty is drawn as
stroke*. So the node's left bar is **solid** when the resolver settled it, **dashed** when a
model chose it, and **solid with a notch** where a person put their thumb. The same three marks
are the transcript's ticks, so the rail and the canvas are one language read in two directions.
An amber dashed bar composes correctly and means *measured, chosen by a model*.

**Collection is drawn on the wire.** One stroke for a run-scoped value, a three-strand ribbon
for a per-item channel, and a ribbon that **converges** into a wide port for a gathering one.
The convergence is the picture of `.collect()`. Three strands whether N is 12 or 12,000 — the
count lives on the source node, never on the wire, and `×12 samples` is drawn only where
`measurement.n_samples` supplies it. Otherwise `×N items` and nothing more.

**The transcript is a ruled log, not a chat.** Bubbles were the shipped artboard's form
(`build_boards.py::RAIL_ASSISTANT`, a right-aligned `#122029` bubble) and they are wrong here
for a reason that is not taste: a chat log has nowhere to put *who decided this*. A hairline
with a tick per turn does.

### What this reopens from the 2026-08-29 canvas — one thing, named

`impl-settled` says **no prompt box on the populated page**: creation is monthly, checking a run
is daily, and the prompt lives in the empty state and the command palette, never as a banner.

**That rule stands and this is not an exception to it.** What it forbids is a *creation*
affordance on a page about something else. The rail here is not a prompt box — it is this
pipeline's provenance record made navigable, and the only place a tier-4 question can be asked.
It appears on an authoring session and nowhere else; `/build?draft=<id>` on an old manual draft
opens the canvas without it.

Two rules from that note are load-bearing and are **not** reopened:

- **The left steps list stays deleted.** Two columns, never three — and the transcript must not
  become a steps list wearing a different border, which is why an accepted decision collapses to
  one line.
- **Settings live in the card on the node.** The conversation *asks* a question; it never
  *lists* values. Asking and listing are different things, and two lists of one thing is exactly
  what was removed.

### What is deferred, and drawn nowhere

Branch creation, branch labels, conditionals, loops, rejoining. An auxiliary branch the
resolver's own blueprint contains is laid out and drawn with neutral wires — `LivingDense` has
five — but there is **no control for authoring one**. Drawing one here would make it look
decided. Also not drawn: token streaming, collaborative cursors, a phone.

---

## The comparison, board by board

Every board below was rendered and **looked at**, and every entry is something the screenshot
found that the source did not show. This section is the deliverable, not a courtesy.

### Found by the first render

| Board | What the picture showed | Fix |
|---|---|---|
| `LivingBuild` | the `×12 samples · once per sample` label ran **under** the first column | the count is already on the source; the wire only says how the channel behaves |
| `LivingBuild` | three nested bends crammed into the 32px between a source's port and column 0, rendering as **six vertical lines in a gutter** | gutter is 124px; columns start at 260 |
| `LivingBuild` | the graph sat in the lower half with a band of dead space above it | `YM` 196 → 150 |
| `LivingGoal` | the goal card and the grouping question stacked, putting **the only thing to answer below the fold** | one block: the grouping question lives *inside* the goal, which is what §1.7 says it is |
| `LivingGoal` | `GROUPING —` at 11px mono reads as an underscore | the row carries its note and no dash |
| all | the transcript's spine at `#172025` **does not exist on screen** — the ticks read as floating marks | `#1E282C` |
| all | the empty state at `#2A3438` on `#080B0D` is technically drawn and practically absent | `#3E5058` / `#5D6C71` |
| `LivingOpen` | the label `READS` beside a prompt about FASTQ files reads as a **noun** | `Sends` |

### Found by the second render

| Board | What the picture showed | Fix |
|---|---|---|
| `LivingCollect` | **the whole point of the board did not read.** The ribbon was "a slightly thicker line" and the convergence was a notch | 12px band, 72px convergence runway, ports sized to the band |
| `LivingChoose` | a dashed ribbon drawn **into empty space** — `ghost=None` skipped the node and kept its edge | the edge is conditional on the node |
| `LivingChoose` | `WOULD REPLACE` wrapped to two lines inside a 172px header | `INSTEAD` |
| `LivingSpawn` | the legend's three swatches **did not draw** — an inline style hack collapsed two of them to nothing | three real swatches: solid, dashed, notched |
| `LivingSpawn` | the chain wrapped and drew a wire **right to left**, which `dag-core` never produces | four columns at 0.84, one row |
| `LivingSpawn` | `MODEL` beside a dashed bar says the same thing twice and **weakens the encoding** | tag removed; the bar is the statement |
| `LivingDense` | `fit to view` ran off the right edge, and the wrapped third row ran right to left | see below |
| `LivingParam` | the values card sat **on top of the chain it belongs to** | moved below and left |
| four boards | the pending block fell **below the fold** under full history | the log scrolls to the pending block; history sits above it |
| `LivingQuiet` | the three frames were not proportional to the widths they claim | 470 / 358 / 255 |

### `LivingDense` took three attempts, and the third is the finding

1. Wrapped fifteen steps onto three rows to make them fit — which put a wire running **right to
   left** on a canvas whose first law is left-to-right.
2. Shrank the whole graph to fit — and every label went with it.
3. **Four columns at 1:1, a minimap that says where you are, and the transcript carrying all
   fifteen.**

That third one is the design finding: **beyond about six steps the canvas is where you look at
one part of a pipeline, and the conversation is where you read the whole of it.** It is also the
strongest argument for the collapsed log — eleven decisions in the space two expanded cards
would take. None of the three attempts is distinguishable in the HTML.

### The 900 pass

The first narrow render squeezed every board to 480px of canvas with the graph clipped —
which is the exact failure the runs rail hit on 2026-09-05, and it meant the layout `LivingQuiet`
specifies **was not in the boards at all**. The breakpoints now live in `_lhead.html`, so
`--width 900` renders the stacked layout: conversation first, composer, then a 430px canvas.
A board that cannot be rendered narrow cannot be checked narrow.

Then the stacked canvas's `Fit` control and minimap landed **on top of the graph**, because an
`inset:0` layer inside a flex child with no definite height has nothing to sit at the bottom of.
Visible only in the 900 shot.

---

## Files

| File | What it is |
|---|---|
| `build_living.py` | the generator. One fixture, one shell, one canvas, one rail |
| `_lhead.html` | the shared style block — `_bhead.html` verbatim, then this canvas's three additions and the breakpoints |
| `Living*.dc.html` | the eleven artboards. **Generated — edit the generator, not these** |
| `canvas.living.json` | artboard placement and the twelve notes arguing the decisions |

`.gitignore` carries `/.design/living-pipeline/living-pipeline.html` for the seeded canvas, one
line, anchored and literal — the same rule the other four follow, and for the same reason.
