# 2026-10-07 — the rest of the audit, Dev mode walked, and the fix plan

## Where things stand

- **14.7.8.3d is the next step** (#284, under #136): fix everything the 3c walk (#262) and the
  data audit (#270) found, before part 4. Nine parts, each a sub-issue listing the issues it
  closes. **Nothing is started.**

  | Part | Issue | What | Kind |
  |---|---|---|---|
  | A | #285 | Unblock the walk (263) | mechanical |
  | B | #286 | The privacy claim about sample excerpts (281) | decision, then mechanical |
  | C | #287 | Mendel data bugs (271, 277, 278, 280, 283) | mechanical |
  | D | #288 | Wiener run reliability (273, 282) | mechanical |
  | E | #289 | Schema integrity (279, then 274) | mechanical |
  | F | #290 | Decisions as rows (269, 272, 275) | brainstorm → spec → plan |
  | G | #291 | Canvas and walk defects (265, 266) | mechanical, after F |
  | H | #292 | Before real users (276) | decisions → spec → plan |
  | I | #293 | The conversation as a tutor (267) | decisions, with part 4 |

  The smaller findings in 268 and 274 are assigned to parts in each part's issue.
- **Dev mode is walked**, as far as 263 allows. It is a fork on a two-state setting, so it never
  shows a card (264 closed, not planned). It changes only whether a registry gap *stops* the
  walk; in the RNA-seq pipeline the one step with a gap (STAR_ALIGN, `seq_platform`) already
  stops as tier 4, so it changed nothing visible. 263 reproduced with it on.
- **Ollama is stopped** (operator); the models stay in their volume. Dev mode is still on in
  Settings.

## What changed

- `2b3d202b`: the walk and the audit's first two passes, written up.
- Issues 282–293; 264 closed; 268, 274, 275 and 276 extended.

## Decisions made, and why

- **The order of the parts** (operator approved the split): A first, because the walk cannot
  finish under *stop only where needed*; B early, because it is a claim about where patient data
  goes; C–E before the redesign, because they are contained; F before G, because F changes the
  projection G's fixes sit on; F before H, because H versions what F creates.
- **Recorded in the task tree and here, not in `now.md`**: `now.md` is at its cap and takes new
  facts through compaction.

## The audit, last two paths

- **Wiener's ingest** (282). `append` replays the run's whole record as `prior` on every event,
  O(n²) per run, beside a projection it never reads back; `seq` is `max + 1` with no lock, and
  the five-minute heartbeat is a second writer. The route is `async def` with blocking database
  work on one process, which serialises ingests against each other by accident.
- **Settings** are sound: one precedence, each value carries its source and why it is locked.
  But which model a purpose gets is implemented twice (283): `access_for` for the call,
  `where_purposes` for the Privacy page, and they diverge when a chosen connection is removed.

## What is next

1. Compact the journal: six entries are pending, past the threshold of five (`compaction.md`),
   and `now.md`'s *Where the work is* still names 14.7.8.2.
2. Part A (#285): the approach for 263 is on the issue; approved, it is test-first.
3. Part B's decision (#286), then Parts C–E's approaches, batched per part for approval.

## Traps

- **React Query stops polling a hidden tab.** A browser driven by automation after a reboot can
  sit on *Working on it* with the answer already stored; a reload shows it. A person returning to
  the tab gets a refetch on focus, so it is not a product defect.
- **The scratchpad's subfolders can vanish mid-session**; `mkdir -p` before writing an issue
  body, and check the issue list before retrying a failed create.
