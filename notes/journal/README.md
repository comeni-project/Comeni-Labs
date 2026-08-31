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

> **2026-09-01** is [`2026-09-01-a-channel-gets-a-name.md`](2026-09-01-a-channel-gets-a-name.md)
> — Plan 5B phases 1 to 3, and the live fan-out defect phase 4 has to fix.
>
> **2026-08-18 has NINE entries and alphabetical order lies.** The one to read first is
> [`2026-08-18-the-day.md`](2026-08-18-the-day.md) — five phases of the forge interface, what is
> true, what a fresh reader will wrongly assume, and what is next. `the-shared-question.md` sorts
> last and is that morning's Plan 2.5 entry.
>
> **2026-08-29 has TWO entries.** Read
> [`2026-08-29-walking-the-loop.md`](2026-08-29-walking-the-loop.md) first — the loop walked by
> hand end to end, and the fourteen defects it found — then
> [`2026-08-29-the-screens-redesigned.md`](2026-08-29-the-screens-redesigned.md), which is the
> design session that answers them and carries the canvas the rework builds from.
>
> **2026-08-31 has ONE entry** — [`2026-08-31-the-modules-move-in.md`](2026-08-31-the-modules-move-in.md) — and it is the
> newest. Plan 5A: the modules moved into the registry layer, `vendor/` is deleted, and
> `--registry X` is the whole input to a build.
>
> **2026-08-30 has ONE entry** — [`2026-08-30-the-overview.md`](2026-08-30-the-overview.md) —
> and it covers three phases: the shared floor, `publishDir`, and the front door. It is the
> session where the 2026-08-29 canvas started becoming code.
>
> **When a day has several entries, name the entry point here.** A directory listing cannot say
> which of nine is the summary, and "most recent" below means *most recent by date*, not by
> filename.

**Newest first, and stop when you have enough.** Each entry is written so the top third —
where things stand, what is next — is sufficient for most sessions. The rest is there for
when you need to know *why* something is the way it is.

If an entry disagrees with the code, the code is right. Say so in a new entry.

## Writing one

At the end of a session that changed anything a future session needs to know:

```
notes/journal/YYYY-MM-DD.md
notes/journal/YYYY-MM-DD-evening.md    # a second session the same day
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

> **This table stopped being maintained on 2026-08-13, and twenty-four entries are missing from
> it** — every 2026-08-14 through 2026-08-19 session, including all nine phases of Plan 3A.
> Noticed on 2026-08-19 while adding the 3B row. **Until it is backfilled, read the directory
> listing rather than this table**; the newest row below is not the newest entry.
>
> It is the drift A33/A71/A72 are about, in the file whose first section explains why a status
> file goes stale. A table of entries is a count of entries by another name, and nothing counted
> it. The entries themselves are fine — they are dated and append-only, which is the property
> that was being bought. What was lost is the *reading order*, which is the only thing this
> table was for.

| Date | Session |
|---|---|
| [2026-08-31](2026-08-31-the-modules-move-in.md) | **Plan 5A — the modules move into the layer.** All four phases; `vendor/` deleted, 16,024 lines. `--registry X` is the whole input, and **three checks now exist that could not before** — conformance over every contract, the hand-edit check, and a layout lint, all running in comeni-registry's own CI. **The measurement that mattered was not a test**: 12 verified before and after, because `MD0100` is a diagnostic and losing every module would have been a green suite with every contract quietly downgraded. **The plan's stated merge order was impossible** — neither repository can go first, and `ENGINE_REF` pinning a pushed commit is what breaks the cycle |
| [2026-08-19 night](2026-08-19-plan-3c-the-builder.md) | **Plan 3C — Mendel's builder.** Nine phases. Layout computed in Python so the canvas is as deterministic as the `.nf`; the graph flows **downward** and the plan assumed sideways. **The checkpoints found three defects the suite structurally cannot** — a container-only 500, a zero-height canvas jsdom cannot see, and two worktrees fighting over port 5173. The provenance bar was counting steps and understating |
| [2026-08-19 later still](2026-08-19-plan-3d-the-forge-answerable.md) | **Plan 3D, all six phases.** The forge was unusable and it was not a looks problem: seven `type_id` holes per tool, each offering the whole vocabulary alphabetically — the right type ranked first in **1 of 30** holes, now **25 of 30**. `suggested` had every consumer and no producer. Sources + Contracts became one Tools board; eight words finally have definitions |
| [2026-08-19 later](2026-08-19-the-front-door-redesigned.md) | The front door redesigned after the operator looked at it. **The hero is a real `pipeline.yml` excerpt** — a tier-3 decision citing a DOI beside a tier-4 one saying *please review*. Wordmark names the site; the Registry box and Lookup panel deleted |
| [2026-08-19 Plan 3B](2026-08-19-plan-3b-landing.md) | The front door — `/` is a landing page, not a redirect. Certainty drawn as stroke; the page counts and links, never lists. **The `Mendel` nav tab became `Builder`, caught by reading the finished page** |
| [2026-08-13 evening](2026-08-13-evening.md) | Everything merged; the rule-drafter spec, rule-format limits (#38/#39) and Plan 2's corrections. **Design audit stream 2 died mid-run — artifacts survive, findings do not** |
| [2026-08-13](2026-08-13.md) | Plan 1.12 — round four's criticals closed (A55–A59, A70); thirteen findings carried as issues. **The last audit-driven plan; Plan 2 is next** |
| [2026-08-11](2026-08-11.md) | Round four — A55–A75, four critical; A55 is code execution through a shareable `pipeline.yml`. **A14 did not close** |
| [2026-08-10 evening](2026-08-10-evening.md) | Plan 1.11 — A38–A54 closed, each with a watched ledger row; A14 stays open |
| [2026-08-10](2026-08-10.md) | Round three — A38–A54, four critical. The fixes became Plan 1.11 |
| [2026-08-09 evening](2026-08-09-evening.md) | Plan 1.10 complete — `pipeline.yml` is the artifact and `PublishBundle` is retired |
| [2026-08-09](2026-08-09.md) | Plan 1.10 specified and planned; two of twelve tasks done |
| [2026-08-08](2026-08-08.md) | Plan 1.9 — A17–A35 closed; A36 and A37 new; golden files never moved across nine parts |
| [2026-08-07 evening](2026-08-07-evening.md) | Round two's eighteen findings reduced to nine roots, all specced; Plan 1.9 written |
| [2026-08-07](2026-08-07.md) | Plan 1.8 — A1–A13 and A15 closed; A14 and A16 open, and A14 is critical |
| [2026-08-06 evening](2026-08-06-evening.md) | The audit landed; Plan 1.8 half executed, stopped mid-plan deliberately |
| [2026-08-06](2026-08-06.md) | Plan 1.7 — publish, upgrade, replay, the registry split; a forgeable layer digest and seven other defects |
| [2026-08-05 evening](2026-08-05-evening.md) | Plan 1.6 merged; "Plan 2.5" renamed to Plan 1.7 and the running order finally justified |
| [2026-08-05](2026-08-05.md) | Plan 1.6 — conformance checking; three contracts were lying about their modules |
| [2026-08-04 evening](2026-08-04-evening.md) | Plan 1.5 — the spine runs and counts correctly; conformance researched, Plan 1.6 written |
| [2026-08-04](2026-08-04.md) | measurements plan merged; repo made public; v1 scope questioned |
