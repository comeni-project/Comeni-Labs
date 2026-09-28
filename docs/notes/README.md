# Working notes

**Provenance, not documentation.** These pages record how the project got here. They are dated,
they were true when written, and they are not maintained against the code.

If you want to know what is true *now*, that is [`docs/`](../). If you want to know *why*
something works the way it does, that is [`docs/design/`](../design/).

## What is here

- **[`now.md`](now.md)**: what is true now, consolidated from the journal. **Start here.** It is
  the one page in this directory that is kept current, by [`compaction.md`](compaction.md), and
  `make doc-paths` checks every path it names.
- **[`journal/`](journal/)**: one entry per working session, not yet compacted.
  `journal/archive/` holds the compacted ones.
- **[`compaction.md`](compaction.md)**: how the journal becomes `now.md`.

Plans, specs and audit rounds used to live here and were removed on 2026-09-02; plans and specs
now live in `docs/superpowers/`.

## The one rule

**Entries are append-only.** A correction goes in `now.md` or a later entry, never by editing an
earlier one; compaction moves an entry into the archive without editing it.

That is the whole reason this directory can be trusted while `docs/` needs checking: a status
page silently goes stale and you cannot tell how stale. A dated entry never claimed to be
current — it claimed to be true on a date, and it still is.

## What this is not

Not a place to look things up. Nothing here is link-checked, and `make links` skips this
directory on purpose: an entry legitimately names files that a later change removed, and holding
provenance to the present tense would defeat the point of keeping it.
