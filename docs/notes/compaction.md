# Compaction: how the journal becomes *now*

The journal records what happened. [`now.md`](now.md) records what is true. This page is how the
first becomes the second, so that a new session reads one short page instead of every entry ever
written.

Adapted from Mem0's memory-update pattern: each new fact is compared with what is already stored,
and becomes one of four operations. Borrowed as a discipline, with no store and no tool.

## Two layers

| Layer | What it is | Rules |
|---|---|---|
| **`journal/`** | the raw log: one dated entry per working session | append-only. Written once and never edited. |
| **`now.md`** | the consolidated state: what is true today | organised **by topic, not by date**. Each line cites the entry it came from, e.g. `(2026-09-28)`. At most **150 lines**; `make doc-sizes` holds that. |

`journal/archive/` holds entries that have been compacted. `journal/` itself holds only entries
**not yet compacted**, so its size is how much is pending.

## When

- **When a step or substep of the current task closes** (14.7.2, 14.7.3, …).
- **At the latest when `journal/` holds five entries** not yet compacted.

## How

Take each entry in `journal/`, oldest first. For each fact in it, compare it with what `now.md`
holds and apply exactly one operation:

| Operation | When | Example |
|---|---|---|
| **ADD** | the fact is new | *Gathering exists; gaps are proposals.* |
| **UPDATE** | it refines or supersedes a stored fact | *Scenario 1 reaches the build* replaces *scenario 1 stops at resolving.* |
| **DELETE** | a stored fact is no longer true | *#109: the model can't see its replies* goes. |
| **NOOP** | it is already known | the Ollama context-length gotcha, which is already there. |

Then:

1. `git mv` the entry into `journal/archive/`. It is moved, never edited.
2. Update `now.md`'s *Compacted through* line to the entry's date.
3. Commit both together: `docs: compact the journal through <date>`.

**Keep `now.md` short by writing less, not by raising the limit.** A fact that cannot be said in a
line gets one line in `now.md`, and the archived entry holds the long form. Before a line goes in,
check it against the code if it describes behaviour: *now* is only useful if it is true.

## What is never compacted

- **`CLAUDE.md`.** It holds what stays true between tasks: how to work, the invariants, the
  commands. The day it starts holding *what happened*, it is growing again. `make doc-sizes`
  holds it to 300 lines.
- **Design records** (`docs/design/`) and specs. They are arguments, not state.

## Memory

The same four operations apply to the agent's memory directory
(`~/.claude/projects/<project>/memory/`) whenever a memory is saved: update an existing memory
rather than adding a near-duplicate, delete one that turned out wrong, and add nothing already
known. `MEMORY.md` stays one line per memory.
