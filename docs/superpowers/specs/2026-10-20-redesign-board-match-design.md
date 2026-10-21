# Redesign — matching the boards

**Parent:** #370 (parts #377–#381 are built on stacked branches; this pass is on
`redesign-board-match`, stacked on `redesign-settings`). **Status:** agreed with the operator 2026-10-20 (departures below are the builder's recommendations, accepted as "what you think is best").
**Operator's rule (2026-10-20):** the screens must match the boards as closely as possible.
The loop is: screenshot beside the board at the same width → fix → repeat until they read the
same, then the operator checks them in Chrome.

**Boards:** `.design/hybrid/{Describe,Build,Question,PipelineFile,RunSheet,Main,Runs,Run,RunFailed}.dc.html`,
rendered with `.design/_prev.py --dir hybrid` at 1400 px. Comparison images were made by pairing
each board with the app at 1400×900 (fixtures served through a DevTools script).

## What "as closely as possible" cannot override

These stay as they are unless the operator says otherwise; each is listed again where it bites.

- **No invented data.** Where a board draws a number or a list the product does not have
  (file counts, compute, *took last time*, a reference picker, other executors), the element is
  not drawn. Absence is absence.
- **No false claims.** Describe's *"It never sees your files"* is not true at protection level 0
  (sampled file text can reach a model), so it is not copied.
- **The MVP has no labs** (#378, #380): no lab name, owners or *started by*.
- **Wiener has one verb (cancel)**: no *Relaunch*.

## Where this departs from the boards, and why (operator: follow the boards unless there is a better way, and say so)

1. **The panel keeps its *Step · Assistant* tabs on Build.** The *Build* board draws no tabs; the
   *Question* board does. Without them the composer would send into a conversation that cannot be
   seen until a reply arrives, and the chat — the way to steer in your own words — would be
   undiscoverable. The tabs are drawn as on *Question*; the × appears only when a step is open.
2. **Describe is one page, as drawn, with one condition.** The goal **is** *What was understood*
   (*You have*, *You want*, then each fact), corrected by clicking a line; *Start building*
   confirms it, and when the engine then asks the pace, the page answers with the card chosen
   (still the person's answer, recorded by the engine; no protocol change). The two pace cards are
   drawn **only when the installation asks every time** (the *Building → Pacing* setting is
   *Ask me every time*); otherwise the engine never asks, the cards would offer a choice that
   changes nothing, and the page says how it will go instead (*Goes step by step — change it in
   Settings*).
3. **Steps not yet offered are named — by their process, for now.** The plan is on the server
   (`Blueprint.order`), so `WalkProgress` gains the remaining steps and the line names them
   (*SAMTOOLS_SORT · step 5*). The board's plain names (*Count reads per gene*) have no source:
   a step's role (`bam_sorting`) carries no human label. That needs a `name` on role declarations
   in the registry repository and its loader in `comeni-core` — a separate issue; until then the
   line reads like the decided steps above it.
4. **No *Skip* on the step card** (found while building, 2026-10-21). Rejecting a step left the
   protocol in the consultant build (its spec §14.4–14.5: the walk's projection has no hole to
   leave; removing a step is a structural edit, after the walk), so a *Skip* button would send a
   command the engine refuses. The card offers *Add it* and *Why this one?*; an alternative tool is
   chosen by its radio card.
5. **The tier chip says the served tier name** (*forced*, *convention*, *measured*, *undecided*),
   not the board's *required*: tier words are declared once (`TIER_VOCABULARY`, served at
   `/registry/tiers`) and read, never typed in a component — the reason `useTiers` exists.
6. **A decided step's row says who chose it and how many values were measured** (*you chose ·
   1 measured*), where the board shows only *1 measured*: who answered is provenance the product
   keeps visible. The count is the step's tier-3 settings, the same number as its canvas footer.

## The builder

### Header (Build, Question, Pipeline file, Run sheet)

| Board | Now | Change |
|---|---|---|
| Name 24 px bold, then a **status chip** (*Building · step 4 of 6* on now-soft; *Valid* on done-soft; *1 value needs you* on needs-you-soft), then *Saved 3 s ago* | name, then a monospace line *building · 3 of 5 steps reviewed · revision 4* | Chip from `phase` + `progress` (*Building · step N of M*, *Checking the goal*, *Complete* → *Valid*); the needs-you chip as now; *Saved* only if a timestamp exists (it does not: drop) |
| *Run* is a quiet grey button with ▸ when not runnable, green when runnable | green at 40 % opacity when disabled | Disabled Run is the quiet grey button |
| No header on *Describe* | header with name and a disabled Run | No header strip while describing |

### Canvas (Build, Question)

| Board | Now | Change |
|---|---|---|
| A rounded panel (border, 16 px margin) on the dot grid; caption *3 steps · 2 inputs* top-left, *12 samples, one task each* top-right; *Fit* and *+ Add step* rounded buttons bottom-left; legend *settled · measured · needs you* bottom-right | full-bleed area, corner ticks, a square *+ Add step*, no caption, grid only while dragging | Panel, captions (counts from the frame; samples from the sample channel), Fit (`useView.fit`), legend |
| **Inputs**: rounded dashed boxes on now-soft — *Input* (now-ink, bold), name, type in mono, *× 12 samples* / *read once per task* | white box with a blue left bar, lowercase *input*, and *once per task* written on the wire | Restyle `SourceNode`; the scope sentence moves into the box; no label on the wire |
| **Steps**: white rounded card, bold mono name, ports as `<` / `>` rows, footer *9 settled* / *1 measured · 13 settled* (measured in amber) | ports as `·` rows, footer *runs 12× · 3 settled*, an amber left bar on tier-3 steps | `LivingNode`: `<`/`>` glyphs, footer counts from the step's settings by tier, no tier bar |
| **Proposed step**: now-blue dashed border, footer *Proposed · not added yet* in now-ink; its wire dashed blue | grey ghost, *PROPOSED* tag, grey dotted wire | Ghost style and wire in `--now` |
| Wires: one grey line with rounded bends | three parallel lines for per-item flows | One line; per-item is said by the input box |

### Step panel (Build)

| Board | Now | Change |
|---|---|---|
| Panel is a rounded card beside the canvas (16 px gap), not a full-height rail | full-height rail with a left border | Card |
| **Step line**: a metro line — green between finished steps, grey after the current one; dots filled ink for settled, amber ring for a step with measured values, blue ring for the current one, hollow grey for later | grey line, ink dots | Colour the segments and dots as drawn; right-hand words *settled* / *you confirmed* / *1 measured* |
| Current step named in plain words (*Sort the alignments*) | process name | Process name until roles carry a name (departure 3); `brief.does` is the tool's whole description sentence, not a name |
| No sentence above the card | *Step 4 of 5, on the canvas already and drawn dashed…* | Remove |
| **Step card**: rounded panel on surface-2; title *Step 4 · sort the alignments* bold, a *required* chip (tier 1) / tier word chip; reason in body text; ports line in mono (*alignment.bam → alignment.bam[sorted]*); options as **radio cards** (name bold mono, note under it; the recommended one tinted now-soft with *suggested* in now-ink); buttons **Add it** (main), **Why this one?**, **Skip** | square box, header *Step 4 of 5 — SAMTOOLS_SORT* + *tier 2*, checkbox squares, *recommended*, *Preview* button, **Continue** / **Show me why** | Restyle `StepProposalCard`; no *Skip* (departure 4); *Preview* stays as a quiet link on an alternative (the boards draw none, but previewing is a feature) |
| Composer: rounded field, placeholder *Ask about a step, or say what to change*, a send icon button | square box with a chevron | Restyle `Composer` |

### Question (a step opened)

| Board | Now | Change |
|---|---|---|
| Opening a step shows *Step · Assistant* tabs and ×; the step's name in bold mono and its contract under it; then **each open value as a question card**: needs-you border, title (the question), *needs you* chip, the setting's path in mono, the reason with a needs-you rule, *Answer from what you know · these three are all the answers there are*, radio cards (value in mono + note), a reason field, *Your reason is saved beside the value…*, **Save answer** / **Cancel**; then a dashed card *Not sure? Measure it instead* with *+ Add step* when a measuring step exists | the step's *Swap / Settings / Remove* tools only | A selected step shows its open values (its settings with tier 4, from the frame) as question cards using the existing setting write (`onSetParam`), then its tools under a quieter *Change this step* row. *Measure it instead* only where the engine offers a measuring step (`need.kind`); otherwise not drawn |
| *Learn it in Code* card | — | Not drawn (Comeni Code does not exist) |

### Describe

| Board | Now | Change |
|---|---|---|
| Title 32 px *What do you want to analyse?*, lede *Say it the way you would to a colleague…* | 22 px title, different lede | Title at the hero size (needs the hero role allowed on describe — `main.css` reserves it for Home; extend it to this page) and the board's lede |
| Sentence in a now-bordered rounded panel, with *Read it again* | plain bordered quote | Panel; *Read it again* re-asks the reading (the session's say with the same sentence) — or not drawn if that is not a real action |
| *Or start from* example chips | — | Not drawn (no examples exist) |
| **What was understood** table: label column (*You have*, *You want*, *Organism*, *Read length*, *Strandedness*), value (mono type + words), a *From "…"* line quoting the words it came from, a source chip (*you said* outline, *convention* outline, *will be measured* amber, *needs you* red); *Wrong? Click a line to correct it* | the goal card (chips, *+ add a type*, *That's right / Not quite*) and, separately, *Current answers* as a plain collapsible list | One table from the goal (have / want, with the quotes the goal card already shows as *heard*) and the facts and inputs (`CurrentFacts` rows); clicking a line opens the existing editor for it; the goal's edit controls appear on the *You have* / *You want* lines |
| *How do you want to build it?* two radio cards with a *good for a first pipeline* chip; *The same description always gives the same pipeline.*; **→ Start building** | *That's right / Not quite* in the goal card; pacing later, as a gap card | See decision 2 |

## Pipeline file

| Board | Now | Change |
|---|---|---|
| Chips under the summary: *Goal · Steps 6 · Settings 41 · Tools 6 pinned · Registry layers 2 · Checks* | — | Section chips; *Settings* is the table shown; the others jump the file column to that section (the file's own top-level keys) |
| File column: *pipeline.yml · main.nf* tabs, *same file you download* | *as it would read · as kept* | Keep the two sources (preview / kept) as the tabs' meaning but word them as the board: *pipeline.yml* (and *as kept* only once kept); *main.nf* not drawn (not served to this page) |
| *4 more steps below · every value has a reason, or it is marked open* | — | That footer line |

## Run sheet

| Board | Now | Change |
|---|---|---|
| In the page: the sheet replaces the canvas under the header; Run turns green | a modal over the canvas | Draw it in the page (the canvas area), keep Esc / × |
| Section 1 *Your files* with the sample-sheet table (*Replace sheet*, *Download template*) | sections *Checked*, *Your files* (types only until sent) | Order as the board where data exists: *Your files* first; the sample sheet appears after sending (Wiener declares it); *Checked* becomes the summary's line (*Checked a moment ago: the pipeline passed a dry run*) |
| *The reference*, *Where it runs* cards, task limits | — | Not drawn (no data; one executor) |

## Home

Close. Remaining: the results rows' file icon; *All results* link (to `/runs` filtered to
succeeded); the *How it was decided* note under the table (*"How it was decided" counts every
value…*). Lab name, owners, compute, *Changed in the registry*, *Import pipeline.yml*: not drawn.

## Runs board

Close. Remaining: counts on every tab (needs a per-phase total: the summary's counts cover 14
days only — draw counts only where exact, i.e. the active tab); the board's selected row tint.
Filters sidebar, search, *Mine*, *Save view*, sort, *Reserved · used*, *Results*, key hints: not
drawn (no data or no feature).

## A run, a failure

Close. Remaining: the failure's explanation line (*Code 137 means the task was killed
(SIGKILL) on its third attempt. The record doesn't say who killed it, so nothing here guesses.*
— a fact from `signal`, allowed); attempt bars full width with figures right-aligned; *Each
attempt used almost all of what it asked for* when every peak is ≥ 95 % of its ask; the
timeline's failed lane tinted needs-you; panel figures as the board (*2 of 6 steps finished*,
*1 task, three attempts*, *stopped 22 min in*, *99 % peak of what was asked*). *Relaunch* and
*Learn in Code*: not drawn.

## Order of work

1. Builder header and canvas (shared by four boards).
2. Step panel and step card (Build).
3. Question (a selected step's open values).
4. Describe (after decision 2).
5. Pipeline file and run sheet.
6. Home, runs, run — the small remainders.

After each: the paired screenshot at 1400, compared and noted in the plan; then 390 and dark.
