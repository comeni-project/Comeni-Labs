# Every screen, measured — 2026-08-29

Evidence from walking every route in the app. **Findings only.** An earlier version of this file
carried proposed fixes and five design directions; the operator's verdict was that those were a
reskin — one structure in five palettes — and they were deleted. The measurements survive because
they are facts, and the restart should not have to re-derive them.

Companion to [the loop audit](2026-08-29-the-loop-a-user-should-walk.md) and
[the journal](../journal/2026-08-29-walking-the-loop.md).

## Measured

| Claim | Measurement | How |
|---|---|---|
| Not responsive | **1 of 50** component files uses a breakpoint — 3 occurrences, all in `home/Home.tsx`. Builder, both run screens and the forge: zero | `grep -rlE '\b(sm\|md\|lg\|xl\|2xl):' --include='*.tsx' frontend/src` |
| Needs a dictionary | **8 terms** in *What the words mean*: `contract`, `type`, `role`, `measurement`, `drift`, `hole`, `band`, `proposal`. All internal | the modal |
| Work is unreachable | **7 rows** in `pipeline_draft`, **0** routes list them. `/build` always loads the example | `select count(*) from pipeline_draft`; `router.tsx` |
| Results unreachable | **No `publishDir`** emitted anywhere. A finished run leaves outputs in `work/<hash>/` | `grep -rn publishDir packages/mendel-compiler tests/golden` |
| Front door is stale | Home renders **"The pipeline builder is not built yet"** — three plans after it shipped | `/` |
| Mostly clerical | **24 actions** to build and run a two-step pipeline; **4** are decisions | [loop audit](2026-08-29-the-loop-a-user-should-walk.md) |

## Per screen

**`/` Home.** Marketing hero over a `pipeline.yml` excerpt. Both CTAs go to the forge. Body content
is a registry inventory — 12 contracts, 22 declared types, 12 measurements, 1 rule, annotated *"the
design expects many"*. Empty state reads *"Nothing is waiting on you."* Neither the builder nor runs
is linked from the body. Says the builder does not exist.

**`/build` Builder.** Three fixed columns, no reflow. The rail is Draw → Keep → Gate → Run, each
gated on the last, with explanatory prose under each. The Gate panel spends four lines defining a
gate. Two steps added by double-click land on identical coordinates. The pipeline is still called
`RNA-SEQ SPINE` after every step is replaced; the draft row's `name` is empty.

**Settings dialog.** `seq_platform` — the one value the resolver could not settle — is a **bare text
input**: no candidate values, no default, no help. Annotated *"A value you set exits at tier 4 and
is recorded as yours."*

**Compare tab.** Works; returns `SAME` for all five steps. Third-level tab, labelled *"where your
pipeline and Mendel's part company."*

**`/runs` Board.** Four tiles; two of them say nothing is happening, in sentences (*"nothing is
waiting on you"*, *"the instance is idle"*). No `PIPELINE` column. Tiles carry no comparison.

**`/runs/:id` Run detail.** Overview, Console, Graph, Tasks — all correct and matching convention
(structured status primary, log as a tab). No Outputs tab. Nothing in the Tasks table is clickable.
Page title says *Mendel* on a Wiener page. Elapsed reads 42s here, 45s on the board, 44.7s in the
database.

**`/forge/queue`.** Sidebar of three zeros, four filter controls, a two-line paragraph explaining
the page — for zero rows.

**`/forge/tools`.** The densest and most domain-native screen in the app: one row per tool, name
plus type signature (`fastq.reads → qc.report`). No column headers, no legend for its status dots.

**`/forge/contracts/…`.** Shows a container-internal absolute path (`/app/vendor/modules/…`) to the
user. Announces an unbuilt feature (*"pipeline pins — not tracked yet"*). Breaks grammar at n=1
(*"1 RULES AIM AT ITS ROLES"*).

**Shell.** Five nav items in two groups — `Builder · Forge · Runs | Queue · Tools` — so the forge
holds three of five slots. Nothing signals which half of the platform you are in.

## Operator's verdict, recorded

- the home page is *"AI slop, random information, no thought / use behind any of them"*
- *What the words mean* is *"REALLY BAD"* — explanation should attach to the term (a `?` on hover,
  or a help **toggle** that enables hover cards), not sit in a modal read in advance
- draw / keep / gate / run is *"stupid"* — a consumer should not have to handle it; **save and
  validate must be automatic and invisible**
- the input system is *"the worst thing I've ever seen"* — an absolute path breaks on a cluster and
  with multiple inputs
- the pages are full of *"long text descriptions of AI stuff"*
- Wiener is *"kind of ok but still bland"*; the forge is bad but explicitly out of scope
- **the whole builder needs a rework and a rethink, before any AI is wired in**

## Open questions, unanswered

1. Who is the primary user — someone who could write Nextflow but would rather not, or someone who
   cannot?
2. Is a pipeline a document or a project?
3. Where do a run's outputs go by default — a location the lab registered, or a Comeni-owned area?
4. Do Mendel and Wiener keep their names in the interface?
5. Does the builder open empty, on a template, or on your last pipeline?
6. How much of the tier vocabulary should a user ever meet?
7. Is `compare` a feature or the pitch? Research found no surveyed platform that shows what a
   deterministic engine would have done differently, or that carries per-value provenance.
8. Light mode, or dark only?

## What failed on 2026-08-29, so it is not repeated

Five design directions were produced and rejected. They shared **one interaction model** — the same
navbar, the same four-tile dashboard, the same node-graph builder with a side inspector, the same
run list, the same waterfall, the same file picker — and differed only in palette, typeface and
panel arrangement. Varying surface treatment across five options is not five directions; it is one
direction with five paint jobs. A real alternative has to change **what the screens are and what
the user does on them**, not what they look like.
