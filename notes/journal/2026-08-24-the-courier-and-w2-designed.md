# 2026-08-24 — the courier, and W2 designed before it is built

**Read this first if you are picking the project up.** The previous entry,
[`2026-08-24-wiener-w1.md`](2026-08-24-wiener-w1.md), is W1's handoff and still true. This is what
happened after it, in the same day: W1 merged, the last gap between the two halves closed, and W2
was designed, specced, planned and audited **without a line of it being built**.

## Where things stand

- **`main` holds everything.** `wiener-w1` merged as [#84](https://github.com/comeni-project/Comeni-Labs/pull/84);
  the courier merged as [#85](https://github.com/comeni-project/Comeni-Labs/pull/85). No plan
  branch is carried.
- **The whole product runs from one `docker compose up`.** Draw a pipeline in the builder, keep
  it, gate it, send it to Wiener, run it, watch it.
- **W2 is spec + plan + audit, not started.** Everything below is paper.

## What exists that did not this morning

**The Mendel→Wiener courier — A179, closed.** `GET /api/pipeline/drafts/{id}/bundle` serves a kept
artifact as a zip and the builder's *run* tab posts it to Wiener. **The browser is the courier and
neither API learns the other exists**, which keeps `execution-boundary.md` §9's rejection of a
Mendel→Wiener API intact rather than bending it into an environment variable.

Three decisions in it are worth not re-litigating:

- **The Nextflow is re-emitted from `pipeline.yml`, not copied.** A gate writes `main.nf` into the
  draft directory as a *side effect of running*, so copying would make the bundle's contents
  depend on whether somebody had gated, and an un-gated draft would ship a directory with no
  workflow in it.
- **Four entries, by allowlist.** A draft directory accumulates `work/` and `.nextflow.log`. Same
  argument `declared_entries()` makes about a registry layer.
- **Two clicks, not one.** Uploading is what *discovers* the parameters — the artifact declares
  its own holes and Wiener reads them out — so `ArtifactStored` carries `declared` and the form is
  the artifact's own shape rather than a `samplesheet` field somebody chose.

Verified end to end through nginx, not only in tests: draft → keep → bundle (86 entries, fixed
timestamps) → upload → submit → **a run that finished with four tasks succeeded**.

## Two defects found by wiring a button to real state

Neither was findable by a test written to pass, and both are the W1 pattern repeating.

- **The gate tab showed nothing.** `useGate` held the run id in `useState`, and `GatePanel`
  renders a `Gate` inside itself — so the toolbar and the panel were **two independent gates**.
  Press the toolbar button and the tab had no progress, no state and no output, with nothing
  broken to find. The state moved into the query cache, which every observer shares.
- **A 401 was retried three times and then printed as `/api/runs → 401`.** Now a distinct error
  class, not retried, and both screens that meet it offer a field to paste the token into.

## W2, designed in the right order for the first time

**Nine artboards were drawn and corrected before the spec was written**, which is a new order here
and it worked. [`docs/design/w2-mockups/`](../../docs/design/w2-mockups/) — published as a canvas at
<https://claude.ai/code/artifact/b36d76fb-0025-4a6a-9f10-400bcc10de10>, each board with the
argument for it on a note beside it. The artboards are live HTML, so the hover states work.

Eleven decisions were put to the operator and answered. Two of them the operator got right against
my recommendation, and both corrections are the useful part:

- **Exception-only row density was rejected.** I proposed showing a resource comparison only when
  it exceeded a threshold. *An exception threshold at 80% is a magic number nobody sourced*, and
  this project refuses an unsourced value everywhere else — a `why:`-less value wearing a UI
  costume. **For a scientific tool the reader decides what is anomalous.**
- **The hover chips were killed.** A first interaction pass revealed `console` and `tasks` chips on
  a row hover; they *covered the read/written column* and pointed at two of the four tabs sitting
  directly above the table. The shortcuts moved to right-click, where a shortcut belongs.

The spec is [`../specs/2026-08-24-w2-reading-a-run.md`](../specs/2026-08-24-w2-reading-a-run.md);
the plan is [`../plans/2026-08-24-wiener-w2.md`](../plans/2026-08-24-wiener-w2.md) — 15 tasks, 87
steps, 7 checkpoints.

## The audit — A191 to A200

Run against the code **and the live database**, before a line was written. Two findings are worth
carrying beyond W2.

**A191 — the Tasks tab cannot sort on a resource.** `run_task.attempts` is a JSON blob, so
filtering by process is an indexed query and *ordering by memory* would mean loading 5,000
documents. Three derived columns fix it. It is the same lesson `CLAUDE.md` already records about
ranking at scale being `ORDER BY`.

**A200 — BLOCKING, and it is the operator's.** The artboards show `sample_07` on every task row.
**Nothing in the fold can name a sample**: `TaskTrace` admits `tag`, `name`, `hash` and `workdir`,
every one marked `LabString`, and `fold()` keeps none of them.

That is not an oversight — and a guard written in W1 predicted this exact day:

> `test_the_fold_is_where_the_lab_strings_stop`: *"Adding `script` to `TaskState` — which somebody
> will want for the console one day — reopens the path, and this fails rather than the leak
> shipping."*

W2 is that day. §8's claim that no lab string can become a span attribute is **structural** today
because they are not in the fold at all; the obvious fix downgrades it to a rule somebody must
remember. Four options are in the plan with their costs; the recommendation is that `wiener-api`
reads them from `run_event.payload` at query time and `wiener-core` never sees one — **and that it
is measured at Checkpoint 1 rather than argued.**

## What a fresh reader gets wrong

- **"The screens are built."** Not one line. Nine artboards and a 937-line plan; `/runs/{id}` is
  still W1's console.
- **"The mockups are the product's CSS."** `docs/design/w2-mockups/build.py` is a design tool and
  nothing imports it. Its hover layer must be re-typed into `frontend/src/tokens.css` from the
  spec — A196.
- **"`--hover` works."** It is referenced five times in `frontend/src/build/` and **defined
  nowhere**. Five hover states have been dead CSS since Plan 3C, which is most of why the builder
  feels inert. W2 defines it; nothing else has.
- **"The events endpoint pages."** It pages **once**, at `limit=200`, and then subscribes. Reload
  mid-run on anything larger and you silently get the first 200 events and a hole. Never noticed,
  because the largest real run is five tasks.
- **"W2 is Wiener's."** §13 puts the builder's rail in it, which is Mendel's screen. The reason is
  that the courier made draw → keep → gate → run one journey and splitting it across slices would
  ship half a sequence. It is scope creep with a stated reason and the operator can cut it.

## What is next

**Execute the W2 plan**, with `superpowers:executing-plans`, task by task.

**Answer A200 first** — Tasks 5, 9 and 11 are blocked on it and Task 1 is not, so Phase W2A can
start while it is being decided.

**Still true from W1 and unchanged:** nobody has looked at the run screens in a browser; the forge
needs testing and rework; and W3 is the AI, after W2.
