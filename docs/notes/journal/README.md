# Working journal

The raw log: one dated entry per working session. **To know what is true now, read
[`now.md`](../now.md), not this directory.**

- **This directory** holds only entries **not yet compacted**. If it holds none, `now.md` is
  complete.
- **[`archive/`](archive/)** holds entries that have been compacted into `now.md`, unchanged.
- **[`compaction.md`](../compaction.md)** is how an entry moves from here to there: when a step
  closes, or at five pending entries, each fact is folded into `now.md` as ADD, UPDATE, DELETE or
  NOOP.

## Why a journal and not a status file

A status file silently goes stale and nobody can tell how stale. A dated entry never claimed to be
current; it claimed to be true on a date, and it still is. **Entries are append-only.** A
correction goes in `now.md` or a later entry, never by editing an earlier one, and compaction moves
an entry without editing it.

## Writing one

At the end of a session that changed anything a future session needs to know, write
`YYYY-MM-DD-<what-happened>.md` here, covering in this order:

1. **Where things stand**: verifiable claims, with the command that verifies them.
2. **What changed**: with commit hashes, not prose summaries.
3. **Decisions made, and why**, especially the alternatives rejected. This is the part that is
   expensive to reconstruct, and the reason the journal exists.
4. **What is next**, in recommended order, with the reasoning for the order.
5. **Open questions**: things genuinely undecided, so nobody assumes they were settled.
6. **Traps**: what a fresh reader would get wrong.

Do not summarise the code; `ARCHITECTURE.md` does that. **Do not point at an entry by name from
anywhere else**: a named pointer is what went three entries stale in August. Point at `now.md` and
this directory.
