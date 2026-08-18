# Mendel dashboard — visual design

**Date:** 2026-08-02
**Status:** Approved first pass
**Mockup:** [`dashboard.html`](dashboard.html) — open it directly in a browser; self-contained, no build step.

This is the visual and interaction spec for the builder screen described in
[Plan 3](../../notes/plans/2026-08-02-mendel-api-and-dashboard.md), Tasks 6–8. Where
the plan says *what* the components do, this says *what they look like and why*.

---

## 1. The governing idea

Every other pipeline builder draws all nodes the same and puts status in a badge. Mendel's
nodes are not equal — some choices were forced, some measured, some guessed — so
**certainty is a property of how a thing is drawn, not a label attached to it.**

That single decision generates most of the design:

| Tier | Rail drawing | Wire drawing | Review level |
|---|---|---|---|
| 1 structural | solid | solid, neutral | `none` |
| 2 convention | solid, 42% opacity | solid, neutral | `none` |
| 3 data-profiled | **dashed** (5 on / 4 off) | dashed | `advisory` |
| 4 ambiguous | **gapped** (3 on / 8 off) | long-dashed, coral | `required` |

Wires inherit their **source's** treatment, so uncertainty propagates visually down the
graph: everything below `STAR_ALIGN` is visibly resting on an unconfirmed platform tag.

**Rejected alternative:** a coloured dot or badge per node. That is the templated answer and
it demotes certainty to metadata. Drawing incompleteness as incompleteness is the point.

---

## 2. Tokens

### Colour

Neutrals are biased toward the accent rather than pure grey — a pure mid-grey reads as
unconsidered.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#F4F6F5` | `#0E1113` | canvas ground |
| `--surface` | `#FFFFFF` | `#171B1D` | panels, nodes, cards |
| `--surface-2` | `#EDF0EE` | `#1F2426` | hover, chat bubbles |
| `--ink` | `#12151A` | `#E8EDEA` | primary text |
| `--ink-2` | `#4A5350` | `#A3AEAA` | secondary text |
| `--ink-3` | `#7C8783` | `#6E7A76` | captions, disabled |
| `--line` | `#DCE2DF` | `#2A3134` | dividers, grid dots |
| `--line-2` | `#C4CDC8` | `#3A4347` | borders, inactive wires |
| `--pea` | `#2C6E49` | `#5FAE80` | **primary** — brand, tier 1–2 |
| `--pea-soft` | `#E4EEE8` | `#1B2A22` | goal card, accent fills |
| `--on-pea` | `#FFFFFF` | `#0E1113` | text on primary |
| `--measured` | `#B77B2B` | `#D9A458` | tier 3 |
| `--undecided` | `#CC4B2C` | `#E87352` | tier 4 |
| `--fault` | `#8B1E1E` | `#D96B6B` | **build failures only** |

**Why deep botanical green as primary.** Mendel's peas. It is subject-derived rather than
SaaS-blue-by-default, and it is desaturated enough to coexist with amber and coral without
fighting them.

**Why tier 4 is coral, not red.** An undecided choice is not an error. If it shares a colour
with genuine build failures, users learn to ignore both. Real faults get `--fault`,
deliberately darker and separate. The traffic-light *logic* is kept because biologists read
it instantly; only the hue is shifted.

### Type

Three roles. In production, self-host **IBM Plex** — Sans for UI, Mono for typed data,
Serif for the display role. The mockup uses system stacks because the artifact CSP blocks
font CDNs and inlining three families as data URIs would be enormous; a silent fallback was
the greater risk.

| Role | Mockup stack | Production | Used for |
|---|---|---|---|
| Display | `Georgia, "Iowan Old Style", ui-serif` | IBM Plex Serif | product name, panel titles. **Sparingly.** |
| UI | `ui-sans-serif, system-ui` | IBM Plex Sans | everything interface |
| Data | `ui-monospace, "SF Mono", Menlo` | IBM Plex Mono | module ids, type ids, states, parameter values |

**Why a serif in a technical tool.** It reads scholarly rather than startup, matching a
product whose claim is provenance and whose components are named for historical scientists
(Mendel, Wiener, Nightingale). This is the design's one real risk.

### Scale

`--r: 3px` corner radius throughout — near-square, instrument-like, deliberately not
`rounded-lg`. `--pad: 20px` panel padding.

**Six type roles, and a size belongs to a role rather than to a screen.** Both halves of the
product draw from this one list.

| px | Role | Where |
|---|---|---|
| 26 | page title | the forge's detail pages; the canvas has none |
| 21 | brand | the wordmark, and display headings |
| 15 | **object title** | a card, a node inspector, a panel *about a thing* |
| 13 | **body and data** | the workhorse — prose and monospace values share it |
| 11.5 | secondary | supporting lines under a value |
| 10 | label | uppercase, `.13em` tracking, one value |

**This replaced a ten-step scale on 2026-08-18, and the ten steps were not the problem — the
*spellings* were.** `dashboard.html` used eleven distinct sizes and **nine** tracking values;
`16`, `15` and `14` were three spellings of one job (naming an object), and all seven positive
tracking values sat on 10px uppercase labels. The forge's screens were worse: **seventeen**
sizes. Density is what a reference tool is for, and it stops being readable when hierarchy is
carried by variety instead of by difference — so the scale is short and a role owns its size.

Only two trackings survive beside `.13em`, and both are negative: `-.015em` on the wordmark and
`-.01em` on node names, which is display type being tightened rather than a label being spaced.

**Spacing had the same disease and was fixed the same day.** `dashboard.html` carried **19**
distinct padding values and the forge's screens **30**, every one chosen by eye. One scale now,
shared by both halves:

`2 · 4 · 6 · 10 · 14 · 20 · 28 · 40 · 60`

Roughly 1.4× growth — dense at the bottom where rows and controls live, generous at the top where
sections separate. A value that is not on the scale is a bug, not a preference.

---

## 3. Ports

A port is a **dot**. Position encodes direction — top edge in, bottom edge out — and the type is
**text**, on hover and on the wire when a node is hovered.

Two channels survive, and both are binary:

- **Filled vs hollow** — whether required states are satisfied. A hollow port is literally an
  unfilled socket; it is exactly where the router inserts a gap-filling step.
- **Doubled outline** — accepts many (`1..*`). MULTIQC's input announces its cardinality
  without a label.

### What was removed, and why — 2026-08-18

This section used to specify **five shapes** encoding the data family (triangle for reads,
diamond for alignments, square for matrices, circle for references, slot for reports), plus a
colour per family. Both are gone, and the operator's judgement was that they were *"too abstract
to be worth anything"*.

**The tell was already in the design: it shipped a permanently visible shape key.** An encoding
that needs its legend on screen at all times is not an encoding — it is a lookup with extra
steps, and the reader pays for it on every glance while the information sits one hover away in
plain words. Colour had the identical defect.

**What the two survivors have that the five marks did not** is that each is *binary* and each is
something a reader acts on. "This socket is unfilled" and "this accepts many" are facts you do
something about. "This is the alignment family" is a fact you look up.

**The marks left the module picker too**, and for a different reason: a mark is a *connection
point*, and in a list there is nothing to connect to. The picker shows the name and an `io` line
in words, and you see the ports the moment the module reaches the canvas.

**What this costs, stated rather than waved past.** The original claim — read compatibility
without reading text — is genuinely gone. Two ports of different families now look identical
until hovered. The judgement is that the claim was never being collected on: five abstract
shapes are learnable in principle and were not learned in practice, which is what a permanent
key on screen is evidence of.

---

## 4. Layout

```
┌─ nav ──────────────────────────── run pipeline · 2 to decide ─┐
├──────────┬╥──────────────────────────────────────╥┬───────────┤
│ modules  │║  how Mendel decided  (provenance bar) ║│ ask ·step │
│ search   │║ ──────────────────────────────────── ║│ ·review 2 │
│ grouped  │║                                      ║├───────────┤
│ by role  │║   pan + zoom canvas, drag nodes      ║│           │
│  ╷hover  │║                                      ║│  one tab  │
│  └─card  │║                                      ║│  at a time│
└──────────┴╨──────────────────────────────────────╨┴───────────┘
             ↑ drag to resize, double-click to collapse
```

- **Three columns**, not Galaxy's four. Both side panels drag-resize (190–430 left,
  280–560 right) and collapse to a 42px rail with a vertical label.
- The collapsed right rail **keeps its undecided count on the stub** — hiding the panel must
  never hide what is blocking your run.
- **Provenance bar** above the canvas: a 10px strip segmented proportionally by tier, with
  "N% settled without judgement" as the honest headline. Clicking a band isolates those
  steps. This is the product thesis compressed into one element.
- **Hovering a module** in the picker opens a description card beside the panel — what the tool
  does, and the thing you would actually choose on (*STAR is fastest but wants 32 GB; HISAT2 is
  the low-memory alternative*). It is a card rather than a tooltip because the content is a
  sentence, and it sits beside the panel rather than under the cursor so it never covers the rows
  you are scanning.

### Canvas

Pan by dragging empty space; wheel zooms toward the cursor, clamped 30%–220%. The dot grid
scales with the view so it reads as a surface, not a backdrop. Node drag divides deltas by
the zoom factor. Buttons for −/+/reset/Fit, bottom right.

**Wires are orthogonal, not bezier** — 2026-08-18. They route down, across, down, with 7px
rounded corners so the graph still reads as drawn rather than as a schematic. The reason is
crossings: two curves meeting at a shallow angle are genuinely indistinguishable, and you cannot
tell which is which at the intersection. Two right angles you can. The type label sits centred on
the horizontal run, which is the only stretch with room for it.

---

## 5. Settings card

Opened from a node's "N settings" button or by double-clicking it. Groups parameters **by
how each was decided, ordered by what needs attention**:

```
Needs your decision   2   ← open by default
Check the premise     2   ← open by default
Standard practice     9   ← collapsed
Forced by inputs      3   ← collapsed
```

Each row carries the tier stripe, an editable field, and the reason. Undecided fields take a
coral border so they are findable by eye alone. The collapsed groups are the point: most
settings need no attention, and the card says so without hiding them.

Parameters with alternatives render as a `<select>`; free values as an input.

---

## 6. Right rail

**Three tabs, one at a time.** It was two tabs *plus* a permanently pinned review strip, which
put two jobs in one column and read as clutter. Review is a tab now, with its undecided count as
a badge that hides at zero — nothing was lost, and a whole stacked section went.

**Ask Mendel.** The chat's reply is an **editable goal card** — have / want / samples /
organism — not prose. This is the AI boundary made visible: the model's only job here is
prose → typed goal, and the user corrects it before anything runs. Rendering it as a chat
bubble would hide the seam that makes the system trustworthy.

**Step details.** Ports with their types, a button to the full settings card, then every
judged parameter with **what else was considered and why each was rejected** — the decision
record's `candidates` field rendered directly.

**Review.** Red items first, then yellow; clicking one selects that step on the canvas.

**One "Run pipeline" button, in the nav.** There were two — one in the nav and one in the review
strip — and both were disabled by the same condition, so the second said nothing the first had
not. The nav carries the blocking count beside it (*2 to decide*), which is the part that was
actually load-bearing.

**The composer is pinned to the bottom of the chat tab** and the conversation scrolls above it,
opening at the newest message. A composer is a control, and a control that scrolls away with the
content is a control you have to go looking for. Only the chat tab pins; `Step` and `Review` are
plain scrolling bodies, because neither has a control to hold down.

---

## 7. Copy rules

- Name things by what the user recognises: "Needs your decision", not "tier 4 unresolved".
- Tier explanations are written for a biologist: *"Matched a rule against your data"*, not
  *"resolved at DATA_PROFILED"*.
- A control says what happens: "Apply and rebuild", "Use this goal", "Change seq_platform".
- Empty states direct rather than apologise: *"No module produces or consumes 'xyz'. Try a
  data type like alignment.bam."*

---

## 8. Motion

One orchestrated moment: nodes settle in sequence on load, 45ms stagger down the pipeline,
reading as "this was composed". Everything else is functional — 120ms port scale on hover,
150ms node shadow. `prefers-reduced-motion` disables all of it.

---

## 9. Known gaps

- **Node positions are hand-placed.** The real builder needs automatic DAG layout — layered
  (Sugiyama-style) assignment with crossing reduction — so generated pipelines lay out
  sensibly without a human dragging boxes. This is the largest outstanding piece and belongs
  in Plan 3 Task 7 as a follow-up.
- **No connection-drawing interaction.** You can drag nodes but not draw a new wire between
  ports. Port hit targets and the hollow/filled state are designed for it; the drag-to-connect
  behaviour is not implemented.
- **The forge approval queue is a separate screen** and is not designed here.
- **Accessibility floor is met, not exceeded**: visible focus, keyboard-operable resizers and
  nodes, ARIA on ports and the provenance bar. A full audit has not been done — in particular
  the canvas has no keyboard pan/zoom equivalent.
