# Frontend redesign, part 1: Welcome, Home, Data, Build, Run

**Status:** design agreed on the board (2026-11-15). Plan: `docs/superpowers/plans/2026-11-15-frontend-redesign-1.md`.
**Sources:** issue #511 and its comments (the written design), the board files in
`2026-11-15-frontend-redesign-board/` (exact layout, copy and tokens), and #508 (run inputs).

## Intent

The product works, but its site is hard to use. The redesign turns it into **a tool, not a website**: one rail on
every page, one job per page, AI choices always visible. Part 1 migrates the everyday path: Welcome, Home, Data,
Build and Run. Part 2 covers Settings, Forge and Registry.

Success: a person ticks a folder of their own files, sees the samples Comeni recognised, builds a pipeline from a
question, and runs it, **with no path typed anywhere** and no run-time inputs form.

## Goals

- One rail on every page, following the rail's grammar (#511, "The rail's grammar"): places on top (Home · Forge ·
  Registry), one fixed slot for the open analysis (Data / Build / Run with sub-pages), the page's labelled controls
  below a divider, and Settings · light/dark · Local at the bottom. It collapses to icons.
- **Welcome** (no analyses): no rail, the mark, *Omnes omnia omnino*, "What do you want to find out?", Add a folder,
  starters across analysis kinds.
- **Home**: the question box with starter chips, Running now, Needs you, analysis cards with a Data / Build / Run
  strip, a New analysis card, and a This machine strip.
- **Data**:
  - **Overview** is data-type neutral: tiles, *Check these*, *Compare samples by [measured fact]*, *What was
    measured*.
  - **Samples** holds the reading rule (shown as examples, with Looks right / Change the rule) and a virtualised
    table whose columns follow the kind of data.
  - **References** are taken From a file, with their measured facts.
  - **Files** lists each file in the ticked folders and what it was recognised as.
  - The rail shows a folder tree to tick, with "Cloud storage · later" below it.
  - The assistant is a floating overlay.
- **Build**:
  - The canvas plus a Step | Assistant panel.
  - The Step tab is a tool form with Basic and Advanced sections, every control type, a source tag and Ask AI per
    value.
  - Add step opens a searchable picker.
  - Ports are labelled; optional ports are dashed; per-sample steps show ×N.
  - The rail holds Review and On the steps.
- **Run**:
  - Sub-pages are Overview · Steps · Outputs · Console.
  - Steps has a Graph | Timeline switch with one tasks panel underneath, and the selected step stays selected
    across both views.
  - The rail lists the runs of this analysis.
  - Sending a run uses the Data tables. There is no form.
- The new theme tokens (#511, "Dark mode and theme tokens") go in `tokens.css`, so light and dark follow.

## Non-goals

- Settings, Forge and Registry restyling (part 2, #513). They render inside the new rail unchanged.
- Cloud storage (#516). The rail keeps a muted placeholder.
- The optional sample sheet (conditions, batches) (#515). It is designed, but not built in part 1; **+ Add column** adds a
  typed-in column.
- Standard references downloaded per machine (#514). The References page shows Standard as "later" in part 1, beside
  From a file.

Everything cut is tracked under #512.

## Anti-goals

- A path stored in `pipeline.yml`, or typed by a person. Invariant 15 holds: the pipeline holds a type, and the
  binding lives with the run.
- A file copied. At level 0 Comeni reads files where they are: their first bytes for measuring, and their paths for
  the run.
- A pairing that fails silently. Every file the rule leaves out is counted and listed, and every exception appears
  in *Check these*.
- A Data page that assumes reads. Tiles, columns and the Compare choices come from what the data measured.

## Constraints

- Hundreds of samples per analysis: stream the reads, keep facts only, summarise for the UI and model, and use no
  caps. The table is virtualised.
- Protection levels are unchanged. At level 0 the assistant may read file names and measured facts. Check
  `services/protection.py` before writing any wording about it.
- The Wiener worker reaches host files only through mounts. The data roots are mounted read-only, at the same
  absolute path, into `mendel-api`, `mendel-worker` and `wiener-worker`.
- No backward compatibility before v0.1.0. Old routes redirect once, and old components are deleted, not kept.

## Approaches

1. **What an analysis is.**
   - **Picked: an analysis is a pipeline draft**, and its data lives in a new `analysis_data` table keyed by
     `draft_id`.
   - Every New analysis already creates a draft (`BuildRoute`), runs already join to drafts by digest, and the data
     stays out of the artifact.
   - Rejected: a new `analysis` identity owning drafts. It adds a second id to every route and a migration of
     existing drafts, for one-to-one data.
2. **How Comeni sees the files.**
   - **Picked: configured data roots** (`COMENI_DATA_ROOTS`, read-only mounts at identical paths) and a server-side
     folder tree limited to them. This is #508's "server-side file browser over allowed roots".
   - Rejected: browser upload. It never yields a host path, so the run could not read the file (#508).
   - Rejected: a per-run bind of chosen paths. It needs the worker to rewrite Docker mounts per run, and widens the
     socket boundary.
3. **Who measures.** Mendel, as today. A scan job reads each file's head from disk, then reuses `samples_of`
   (pairing) and `inspect_sample` (facts). Rejected: measuring in Wiener. Inspection, protection and facts already
   live in Mendel.
4. **The reading rule.**
   - The default is the existing mate-token pairing, tagged RULE.
   - Change the rule takes a pattern with `{sample}` and `{read}` tokens, tagged YOU.
   - The assistant can set the pattern with a tool, tagged AI until Looks right.
   - Rejected: an AI-only rule. It fails silently when no model is configured.
5. **How the run gets its data.**
   - The browser asks Mendel for the run's bindings (each artifact channel answered from the Data tables) and posts
     them to Wiener, the same courier role it has today (`useSubmit.ts`).
   - Wiener refuses an input path outside its data roots, with a coded message.

## One engine, one loop

Data adds no second builder:
- **Facts:** the scan records the facts the samples agree on as MEASURED on the draft, through
  `decisions.observe`, as a sample upload does today (`agent/direct.upload`).
- **Inputs:** the scan sets the input type, through `changes.apply`, as a sample upload does today.
- **Build:** resolution, routing, rules and emission read those facts unchanged, and the #463 agent loop builds
  the pipeline from them.
- **The Data assistant** is the same session and loop as Build's assistant, with three more tools: `read_data`,
  `set_reading_rule` and `apply_fix`.
- **Paths** join only at run time, through the bindings. The engine never sees one.

## Decided by the operator

- Plan 1 covers Welcome/Home, Data, Build and Run; plan 2 covers Settings, Forge and Registry.
- Data has its own sub-pages. The Overview is the top level; Samples, References and Files are separate pages.
- The assistant is an overlay. Nothing assumes reads.
- Run's Steps merges Graph and Timeline.
- Cloud storage is not in the MVP, but leaves room in the rail.

## Left to the builder

- Exact component splits inside each page, and the empty and loading states, following existing `ui/States`.
- The scan's progress transport: polling `GET …/data` while `scan.state == "scanning"` is enough.
- Which existing run components (`Graph`, `Timeline`, `Tasks`, `Console`, `OverviewPanel`) are reused as they are or
  restyled. Prefer reuse.
