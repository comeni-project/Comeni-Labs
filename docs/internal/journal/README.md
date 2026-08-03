# Working journal

One entry per working session, dated, **append-only**. A new session — human or agent —
reads the most recent entry first and is productive in five minutes.

## Why a journal and not a STATUS.md

A status file has one job and one failure mode: it silently goes stale, and nobody can
tell how stale. This repository has already been bitten by exactly that — `CLAUDE.md`
claimed "C2 and C3 are open and block Plan 2" for a day after both were fixed, and there
was no way to know without reading the audit.

A dated entry cannot go stale, because it never claimed to be current. It claimed to be
true on a date, and it still is. Corrections go in a *later* entry, never by editing an
earlier one — the same discipline as `audits/` and for the same reason.

## Reading it

**Newest first, and stop when you have enough.** Each entry is written so the top third —
where things stand, what is next — is sufficient for most sessions. The rest is there for
when you need to know *why* something is the way it is.

If an entry disagrees with the code, the code is right. Say so in a new entry.

## Writing one

At the end of a session that changed anything a future session needs to know:

```
docs/internal/journal/YYYY-MM-DD.md
```

Cover, in this order:

1. **Where things stand** — verifiable claims, with the command that verifies them
2. **What changed this session** — with commit hashes, not prose summaries
3. **Decisions made, and why** — especially the alternatives rejected. This is the part
   that is expensive to reconstruct and the reason the journal exists.
4. **What is next** — in recommended order, with the reasoning for the order
5. **Open questions** — things genuinely undecided, so nobody assumes they were settled
6. **Traps** — what a fresh reader would get wrong

Do not summarise the code. `ARCHITECTURE.md` does that and is maintained. The journal is
for the things that are not in the code: intent, sequencing, and what was ruled out.

## Entries

| Date | Session |
|---|---|
| [2026-08-04](2026-08-04.md) | measurements plan merged; repo made public; v1 scope questioned |
