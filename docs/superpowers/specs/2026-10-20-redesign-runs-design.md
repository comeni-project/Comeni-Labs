# Redesign 6 — runs, a run, and a failure

**Issue:** #380 (parent #370). **Status:** built without a question round at the operator's
request (2026-10-20); the calls are the builder's. Branch `redesign-runs`, stacked on part 5.
**Boards:** `.design/hybrid/Runs.dc.html`, `Run.dc.html`, `RunFailed.dc.html`.

## Why

The runs board lists runs by id with an executor and a submitter, under five tiles and a phase
dropdown; a reader looks for *which pipeline* and *did it work*. The run page has the board's
bands already (panels, timeline, steps, tasks) but an older header, lowercase band labels, and a
failure banner below the panels. The boards put the failure first and draw it as a panel that
explains the attempts beside what Nextflow reported.

## What changes

### The runs board (`runs/Board.tsx`)

- **Header:** *Runs* (title) and *N runs, newest first*.
- **Outcome tabs** replace the phase dropdown: *All · Going now · Went wrong · Succeeded ·
  Cancelled* (phases `running`, `failed`, `succeeded`, `cancelled`; *All* is no filter). The
  active tab shows the server's total.
- **The table, by pipeline:** *Outcome* (mark and word), *Pipeline* (the name from Mendel's
  drafts, joined on the pipeline digest as Home does; *unknown pipeline* otherwise), *Run* (id),
  *When* (*3 h ago*), *Detail* (*N of M tasks*; *cancelled at N of M*), *Took* (and *as usual* /
  *+N% vs usual*, as today). No executor, no *started by* (no labs in the MVP).
- **The five tiles and the per-day chart go.** The boards have none; *Went wrong* is a tab, and
  the per-row *vs usual* keeps the one judgement the tiles made useful. The summary query stays
  for that median.
- Not drawn: the boards' filter sidebar beyond the tabs, *Mine*, *Save view*, *Reserved · used*
  and *Results* columns (no per-run data for them on the board), keyboard hints.

### A run (`runs/Run.tsx`)

- **Header:** a breadcrumb *Runs / name*, the name (title), the id, the phase chip, and the
  sentence (what is running, elapsed, where, when it started). Actions on the right: *Open the
  pipeline* (when the run came from one, as `↩ pipeline` does today), *Console*, then *Cancel*
  or *Delete* as today.
- **A failed run opens on its failure**, above the panels.
- Band headings read *Steps* (with *Table · Graph*) and *Tasks*, in the heading role.

### The failure panel (`runs/Failure.tsx`)

A panel with a needs-you border, two columns that stack on a narrow screen. Left: the task and
its tag, the exit code as a chip, what the record says (unchanged wording rules: nothing
guesses a cause), the attempts with their memory asked and peak as bars when the history has
them, and *Open the console at this task*. Right: *What Nextflow reported*, as written.

**Relaunch is not built.** Wiener has one verb, cancel; a relaunch (with more memory) needs a new
verb and its own design, so the board's *Relaunch* buttons are not drawn.

## Testing

Vitest: board tabs set the phase query and show the total; pipeline names from drafts; no
executor or submitter; *unknown pipeline*. Run: breadcrumb and actions; failure above the
panels; band headings. Failure: two regions, the attempts, the console action, the report as
written, and the existing guarantees (no invented cause, a run that failed with no failed
task). Browser with fixtures, 1440 and 390, light and dark.
