# Working notes

**Provenance, not documentation.** These pages record how the project got here. They are dated,
they were true when written, and they are not maintained against the code.

If you want to know what is true *now*, that is [`docs/`](../). If you want to know *why*
something works the way it does, that is [`docs/design/`](../design/).

## What is here

**[`journal/`](journal/)** — one entry per working session. What was built, what broke, what was
decided, and what the next session should know. Newest first; start there.

That is currently all of it. Plans, specs and audit rounds used to live here too and were removed
on 2026-09-02 — they had grown into a second, contradictory account of the system, and answering
"what does this do" from them was slower than reading the code.

## The one rule

**Entries are append-only.** A correction goes in a later entry, never by editing an earlier one.

That is the whole reason this directory can be trusted while `docs/` needs checking: a status
page silently goes stale and you cannot tell how stale. A dated entry never claimed to be
current — it claimed to be true on a date, and it still is.

## What this is not

Not a place to look things up. Nothing here is link-checked, and `make links` skips this
directory on purpose: an entry legitimately names files that a later change removed, and holding
provenance to the present tense would defeat the point of keeping it.
