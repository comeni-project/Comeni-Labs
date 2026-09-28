# Documentation compaction: a short brief, a true *now*, and rules that keep it that way

**Date:** 2026-09-28 · **Status:** design, awaiting the operator's review
**Issue:** #118 (under 14.11 #130, Task 14 #119)

---

## 1. Why

Measured on 2026-09-28:

| What | Size | Problem |
|---|---|---|
| `CLAUDE.md` | **1,441 lines**, loaded into every session and every subagent | *Current state* is 466 lines of plan-by-plan history; *Invariants* is 212, mostly argument |
| dead paths in `CLAUDE.md` | **29** references to `docs/design/*`, `notes/specs`, `notes/audits`, `notes/plans`, `notes/README` | nine design docs were deleted on 2026-09-02 (`83c873d`) and the invariants still cite them as their rationale |
| journal | 13 entries, 2,490 lines, never compacted | each entry restates state the next one supersedes |
| plans | 5 files, 5,873 lines | finished plans sit beside live ones |
| worktrees | **12**, mostly for merged branches | full copies of the repo that every search can land in; the only surviving copies of the deleted design docs are in `.worktrees/plan-3e-builder` |

`make links` passed throughout, because it checks Markdown links and `CLAUDE.md` cites paths in
backticks.

## 2. What success looks like

- `CLAUDE.md` is **≤ 300 lines** and a working brief, with **zero dead paths**.
- `docs/notes/now.md` exists, is ≤ 150 lines, and is the only history a session must read.
- `docs/notes/journal/` holds only entries not yet compacted; compacted ones are in `archive/`.
- Every invariant's argument is in `docs/design/invariants.md`, and none is lost.
- Two checks in `make check` keep all of this true.
- The stale worktrees are gone.
- **Nothing true is thrown away.** Anything removed is either in the new files, in an archive, or
  named as dropped with its reason in a commit message.

## 3. Decisions (operator, 2026-09-28)

| Question | Decision |
|---|---|
| What `CLAUDE.md` is for | **A working brief, about 250 lines** |
| Where the invariants' arguments live | **One new `docs/design/invariants.md`**, from today's `CLAUDE.md`; the 2026-09-02 deletion stands and old docs are cited by commit |
| What happens to a compacted journal entry | **Moved to `docs/notes/journal/archive/`** |
| Stale worktrees | **Remove the merged, clean ones**; keep and name any with uncommitted work |
| Keeping it from bloating again | **A path check and a size budget**, both in `make check` |
| The tool for the rewrite | **`claude-md-management:claude-md-improver`**: its audit first, its rewrite held to this spec |

## 4. What goes where

| Content today | Goes to |
|---|---|
| product claim, *say this, not that*, the writing rules | `CLAUDE.md`, tightened |
| invariants (212 lines) | `CLAUDE.md`: **one line per rule**; the argument moves to `docs/design/invariants.md` |
| *Current state* (466 lines) | deleted from `CLAUDE.md`; what is still true goes to `now.md`, and the rest is already in the journal |
| *How to start implementing* | `CLAUDE.md`, rewritten for how we work now (below) |
| tiers, protection profiles, architecture, distribution | `CLAUDE.md`: a paragraph each; the detail is in `ARCHITECTURE.md` or `invariants.md` |
| *Open issues* table | deleted; GitHub is the tracker, and the tree (#119) is linked |
| commands, gotchas | `CLAUDE.md`, trimmed to what is still true |
| compacted journal entries | `docs/notes/journal/archive/` |
| finished plans (`the-wiki-scaffolding`, `forge-mvp`) | `docs/superpowers/plans/archive/` |
| `docs/notes/2026-09-05-the-forge-walk.md` | the journal's archive (it is a dated entry) |

### `CLAUDE.md`'s shape

1. **What this is:** the product claim and the differentiator, and *say this, not that*.
2. **How we work:** the current task and where its tree is (#119); every defect an issue; mechanical
   fixes directly, a rule or protocol question brainstormed with the operator choosing; rules are
   tuned, never forced; executing-plans in one hand, subagents for review and design; tick plan
   steps; stop when an estimate breaks; the writing rules for docs.
3. **Invariants:** one line each, numbered as today, and each linking to its section in
   `invariants.md`.
4. **The system in a paragraph each:** tiers, protection levels, packages, distribution.
5. **Commands.**
6. **Gotchas.**
7. **Where to look:** `now.md` first, then any entry in `journal/` (by the rules, those are the
   ones not yet compacted), the issue tree, `invariants.md`, `ARCHITECTURE.md`,
   `docs/design/authoring-protocol.md`. Never "the newest entry" by name: a named pointer is
   what went three entries stale in August.

## 5. Compaction rules (`docs/notes/compaction.md`)

Adapted from Mem0's memory-update pattern. Borrowed as a discipline, with no store and no tool.

- **Two layers.** The journal is the raw, dated, append-only log, one entry per session.
  `now.md` is the consolidated state: organised **by topic, not by date**, each line true today
  and citing the entry it came from.
- **When:** as a **step or substep closes** (14.7.2, 14.7.3, …), and at the latest when
  `journal/` holds five entries not yet compacted.
- **How:** each entry since the last compaction is folded into `now.md`, fact by fact, as one of:

| Operation | When | Example |
|---|---|---|
| **ADD** | a new fact | *gathering exists; gaps are proposals* |
| **UPDATE** | refines a stored fact | *scenario 1 reaches the build* replaces *stops at resolving* |
| **DELETE** | a stored fact is no longer true | *#109* goes |
| **NOOP** | already known | the Ollama context-length gotcha |

- Then the entry moves to `journal/archive/`, and its date is added to `now.md`'s *compacted
  through* line.
- **Append-only still holds for the raw log.** A compacted entry is moved, never edited.
  Corrections go in `now.md`, or in a later entry.
- **Memory** (`~/.claude/projects/…/memory/`) follows the same four operations when a memory is
  saved, and `MEMORY.md` stays one line per memory.
- **`CLAUDE.md` is never a compaction target.** It holds what stays true between tasks. The day
  it starts holding *what happened*, it is growing again.

## 6. The checks

Both in `make check`, both watched failing against today's files before the cleanup starts.

- **`tools/check_doc_paths.py`:** every backticked token in `CLAUDE.md`, `docs/notes/now.md` and
  `docs/design/invariants.md` that looks like a repository path (contains `/` or ends in a known
  extension, and is not a URL, a glob, a command line or a `module.attribute`) must exist,
  resolved against the repository root and against `packages/*/src/` for Python module paths.
  The failure message lists each dead path with its line.
- **A size budget, `tools/check_doc_sizes.py`:** `CLAUDE.md` ≤ 300 lines, `now.md` ≤ 150. The
  message says *compact, don't raise the limit*, and points at `compaction.md`.

## 7. Order of work

1. **Worktrees.** List all 12 with branch, merged or not, and `git status`. The operator sees the
   list, then the merged, clean ones are removed (`git worktree remove`; branches are kept).
2. **The checks**, written and watched failing: 29 dead paths and 1,441 lines is the *before*.
3. **`compaction.md`**, the rules, before they are used.
4. **The first compaction:** all journal entries and the loose forge-walk note are folded into
   `now.md`, then archived. The rules' first real run.
5. **`invariants.md`:** each argument from today's `CLAUDE.md`, word for word where still true,
   with dead citations replaced by `git show 83c873d^:<path>`.
6. **`CLAUDE.md` rewritten** with `claude-md-improver`, audit first. The new file is checked line
   by line against the old one: every rule, command and gotcha is in the new file, or in
   `invariants.md` or `now.md`, or named as dropped with its reason in the commit message.
7. **Finished plans archived**, links repointed, `make check` green, #118 closed.

## 8. Out of scope

- **`ARCHITECTURE.md` (747 lines)** is only checked for dead paths. Slimming it is a separate
  issue if the walk shows it is needed.
- The handbook (`docs/handbook/`): its own pages are 14.10's job.
- Rewriting anything that is true and in the right place.
