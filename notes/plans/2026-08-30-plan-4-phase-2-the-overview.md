# Plan 4 Phase 2 — the Overview

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes, and where a step was
> carried out differently, tick it anyway and record the deviation in the execution table.

**Goal:** `/` becomes the lab's work rather than the product's inventory. What is running, what
is waiting on a person, what the lab has built and whether any of it is ready — and **nothing at
all where there is nothing to say**.

**Architecture:** the page reads three stored things and joins them in the browser. `mendel-api`
lists pipelines with provenance read from the **stored artifact**, never a re-resolve.
`wiener-api` lists runs and gains one aggregate. **The browser is the courier** — `useSubmit.ts`
is already the only place in the product that touches both halves, and this page becomes the
second; neither API learns the other exists. The join key is the **pipeline digest**, which is
content-addressed and therefore the only key that does not require one server to know the other's
identifiers.

**Tech Stack:** Python 3.12 · Pydantic · FastAPI · SQLAlchemy + Alembic · React 19 · TypeScript ·
Tailwind 4 · `@tanstack/react-query`.

**Design source:** the canvas —
<https://claude.ai/code/artifact/4f65e748-9758-4f06-9b87-1a8dc5a34b34>, page 2. Three artboards
(`Overview.dc.html`, `OverviewQuiet.dc.html`, `OverviewFirst.dc.html`) and five annotations
(`ov-scope`, `ov-absence`, `ov-work`, `ov-blocked`, `ov-settled`). **Render the boards with
`.design/_prev.py` before writing a line of JSX** — it is thirty seconds, and it is the only
reason the design session's own three defects shipped fixed.

**Depends on:** Phase 0 (motion, responsiveness, the failed-mutation surface) and Phase 1
(`publishDir`, without which *Results ready* cannot ship).

## Global constraints

- **Absence is absence.** Compare `Overview.dc.html` with `OverviewQuiet.dc.html`: the difference
  is not a different empty state, it is that the NOW band **does not exist**. No card, no
  "nothing is waiting on you", no "the instance is idle". The page is simply shorter. This is the
  whole fix to the bloat complaint, and the instinct to fill an empty region with a reassuring
  sentence is exactly what made the old page read as generated. It applies to **every** block.
- **If every block is empty, the page is the shell plus Work plus New pipeline.** That is a
  legitimate page, not a broken one.
- **This page must not resolve anything.** The 2026-08-19 audit found every registry-touching
  screen cost ~250ms warm and one function was responsible. Read the stored artifact; do not
  rebuild it to draw a bar.
- **Waiting on a person names the values.** *"strandedness and fragment size"*, not *"2 items"*.
  A count is what you write when you have not looked.
- **Every row carries a person**, even while there are no accounts. When accounts arrive there
  will be two overviews — the lab's and your own — and the whole point of building it lab-first is
  that the second one is a **filter, not a second page**. A row that ships without a person is
  what turns that filter into a rewrite.
- **One action, top right: New pipeline.** The same button whether you have none or fifty.
- **`make check` is the gate**, plus the frontend gate `npx tsc -b && npx vitest run &&
  npm run lint` from `frontend/`. No task here touches the six files that require `make verify`.
- **`make client` after every route change.** Never hand-edit `frontend/src/api/` or
  `frontend/src/wiener/api/`.
- **Diagnostic codes:** an API refusal is `MA`, not `MD` — `MD` is reserved for the three pure
  packages. Declare in `comeni_core/diagnostics.yml` and run `make docs`.

---

## Pre-execution notes — checked against the code on 2026-08-30

Five findings. **Three change what a task does**; one is a correction to the design notes and one
is a consequence of Phase 0 that the design session could not have anticipated.

**P2-1 — `pipeline_draft` DOES have an owner column.** `ov-scope` says *"pipeline_draft HAS NO
OWNER COLUMN TODAY. Add it before this page ships."* It does: `PipelineDraft.who`, `String(200)`,
indexed, populated at `create()` from `identity.default_author()`, with a docstring reading
*"`who` is ATTRIBUTION, not authentication, exactly as on `QueueVisit`."* **No migration is
needed.** Correct the annotation's premise in the journal entry at the end rather than silently
skipping the step.

**P2-2 — there is no `GET /drafts` at all.** The build router (mounted at `/api/pipeline`) has
`POST /drafts`, `GET /drafts/{id}`, `PUT /drafts/{id}`, `POST /drafts/{id}/keep` and
`GET /drafts/{id}/bundle`. **The Overview's entire *by pipeline* half has no query behind it.**
This is the largest single piece of backend work in the phase and it is not mentioned anywhere in
the design notes, because the design was drawn against the screens rather than the routes.

**P2-3 — `RunArtifact.pipeline_digest` is declared and never written.** It exists on the model
with the right type (`String(71)`, nullable) and a repository-wide grep finds no assignment. It is
the **join key** this page needs twice — *run count per pipeline* and *vs usual* — and it is the
only candidate that keeps `execution-boundary.md` §9's rejection of a Mendel→Wiener API intact.
Writing it is Task 2 and it is cheap: the uploaded bundle contains the `pipeline.yml` whose digest
Mendel already computes.

**P2-4 — Phase 0 hid the forge, which empties half of `/api/attention`.** `whats_open()` returns
`forge` calls pointing at `/forge/tools` and `/forge/queue`, and `Attention.mendel` is hardcoded
`[]` with a docstring reading *"Nothing stores pipelines, so the page renders no Mendel block at
all."* **Both halves of that are now wrong**: the forge's destinations are unreachable from the
frame, and pipelines have been stored since Plan 3E. So the front door's *needs you* changes
meaning — from *open forge questions* to **open tier-4 values in the lab's pipelines**, which is
what invariant 6 says must always be flagged and what the artboard actually shows. The forge half
is **not deleted**; it stops being rendered, because a call to action pointing at a hidden screen
is worse than no call at all.

**P2-5 — `board_summary()` already folds durations in Python and says why.** Median and p95 have
no portable SQL spelling across SQLite and Postgres, and a fortnight of runs is hundreds. The
`GROUP BY artifact_id` the notes ask for is therefore **a second fold in the same function**, not
a percentile expression — follow that function's existing argument rather than reopening it.

---

## Task 1 — `GET /api/pipeline/drafts` — the query the page has no answer without

**Deliverable:** a list of the lab's pipelines with everything the *by pipeline* table needs, and
nothing that requires resolving.

- [x] Add `list_drafts()` to `packages/mendel-api/src/mendel_api/services/drafts.py`, ordered by
      `updated_at` descending, paginated.
- [x] Each row carries: `id`, `name`, `who`, `updated_at`, whether it has been **kept**, the
      digest of the kept `pipeline.yml`, the step count, and the **provenance counts**
      (settled / measured / open).
- [x] **Provenance comes from the stored artifact.** `keep()` already writes a `pipeline.yml`
      under `settings.draft_root`; read it and count. **Do not call the resolver.** If a draft has
      never been kept there is no artifact and the provenance is **absent, not zero** — a bar of
      three empty segments claims a pipeline with nothing open, which is the opposite of the
      truth.
- [x] Add the route to `routes/build.py` following that file's shape — a declared out model, an
      `operation_id`, a one-line `summary`. Remember the router's prefix: the path is
      `/api/pipeline/drafts`.
- [x] Name the open values. A pipeline with two tier-4 settings must return *which two*, by name,
      because the page says *"strandedness and fragment size"* and a count is what you write when
      you have not looked. Cap the list and say how many were not named.
- [x] Add `test_the_listing_never_resolves` — patch the resolver's entry point to raise, and
      assert the listing still answers. **Watch it fail** by computing provenance from a rebuild.
      Record in [`../audits/guard-ledger.md`](../audits/guard-ledger.md).
- [x] Add `test_an_unkept_draft_has_no_provenance` — absent, never three zeroes. Watch it fail.
- [x] Measure it. The budget is the one the 2026-08-19 audit set: nothing on this page may cost
      what the registry screens cost. Record the warm number in the docstring, as
      `attention.whats_open()` already does.
- [x] `make client`.

---

## Task 2 — write the join key

**Deliverable:** `RunArtifact.pipeline_digest` stops being a declared column with no value in it.

- [x] In `packages/wiener-api/src/wiener_api/services/artifacts.py`, read the `pipeline.yml` out
      of the uploaded bundle and record its digest on the `RunArtifact` row at upload time.
- [x] Use the digest **Mendel already computes and writes into the artifact**, not a fresh hash of
      the bytes. Two spellings of "the digest of this pipeline" is two answers to one question,
      and the whole value of the key is that both halves agree without talking.
- [x] If the bundle carries no readable `pipeline.yml`, leave it `None`. A wrong key is worse than
      an absent one, and the column is already nullable.
- [x] Backfill is **not** in scope. Existing rows keep `None` and the page shows those runs under
      *every run* without a pipeline. Say so in the model docstring.
- [x] Add `test_an_uploaded_artifact_records_which_pipeline_it_is`. **Watch it fail** — it fails
      today, against the code as it stands, which is the cleanest possible watch.

---

## Task 3 — `vs usual`, and the resource sentence

**Deliverable:** one aggregate in Wiener that makes the board's best number possible, here and in
Phase 5.

- [x] Add `durations_by_pipeline(session, lab_id, *, days)` to
      `packages/wiener-api/src/wiener_api/repository.py`, grouping finished runs by
      `RunArtifact.pipeline_digest` and returning a median per group.
- [x] **Fold in Python**, following `board_summary()`'s stated argument — a median has no portable
      SQL spelling across SQLite and Postgres, and the window is hundreds of runs. Do not reopen
      that decision; cite it.
- [x] A group with fewer than a floor of runs returns **no median**. *Usually 38m* over two runs
      is not a usual, and `rn-board` is explicit that this number earns its place by being a
      judgement rather than trivia.
- [x] Expose it on the existing `GET /api/runs/summary` rather than a new route — it is the same
      question the tiles already ask, at a different grouping.
- [x] The **resource sentence** aggregates across runs and is legitimate at lab scale and
      meaningless at four. Gate it on the same run-count floor, and **keep it a sentence** — the
      moment it becomes a chart on this page it is data slop (`ov-blocked`).
- [x] Add `test_a_median_needs_enough_runs_to_be_one`. Watch it fail.
- [x] `make client`.

---

## Task 4 — `/api/attention` says what needs a person *now*

**Deliverable:** the endpoint answers the question the new page asks, and stops pointing at
screens nobody can reach.

- [x] Stop rendering the `forge` calls. **Do not delete `whats_open()`'s forge half** — the forge
      is hidden, not removed, and the day it comes back the call should come back with it. Gate it
      behind the same decision Phase 0 recorded in `Shell.tsx`, and say so in one comment naming
      the date.
- [x] Fill the `mendel` half. Its docstring currently reads *"Empty today, and that is a section
      rather than a zero. Nothing stores pipelines"* — that has been false since Plan 3E. Rewrite
      it, and populate it from Task 1's listing: a pipeline with open tier-4 values is a
      `Call`, and it **names the values**.
- [x] `Urgency` keeps its three members and its declared `rank`. An open tier-4 value is
      `WAITING`, not `BLOCKING` — nothing is broken, somebody is held up.
- [x] Delete `Standing` from the payload. `ov-settled` puts the registry inventory off this page
      deliberately: *"That is the PRODUCT's state, not YOURS. It is why the old page read as
      slop — information with no question behind it."* Delete the model, the field and
      `frontend/src/home/Standing.tsx` together, in one commit.
- [x] Rewrite `test_the_standing_says_what_the_registry_holds` out of existence and
      `test_the_mendel_half_is_absent_rather_than_zero` into its successor. Both are **deliberate
      deletions**, not workarounds.
- [x] `make client`.

---

## Task 5 — retire the constraint that says this page may not exist

**Deliverable:** the old discipline is removed on purpose, with the argument written down.

`docs/design/forge-review.md` §3 records an Overview page **designed and cut** because it answered
the same question as the forge Queue, and two tests hold the rule that `/` counts and links and
never renders an item:
`frontend/src/home/Home.test.tsx::"never lists a question, a contract or a drift row"` and
`packages/mendel-api/tests/test_attention.py::test_it_reports_what_is_open_without_listing_it`.

**The operator has ruled that constraint dead** (`ov-settled`). The instruction is explicit:
delete or restate the tests deliberately — do not work around them, and do not leave them failing.

- [x] **Restate** rather than delete. The new page renders **pipelines and runs, never a contract,
      a question subject or a drift row.** That is a narrower rule than the old one and it is
      still a real one — it is what stops this page becoming the forge Queue a second time. Both
      tests become assertions of the narrower rule.
- [x] Add a dated paragraph to `docs/design/forge-review.md` §3 recording that the constraint was
      lifted on 2026-08-30, by whom, and what replaced it. The file is the reason anybody would
      hesitate; leaving it unamended means the next reader re-litigates this.
- [x] Watch the restated tests fail: render a contract id on the page and confirm each goes red.

---

## Task 6 — the page

**Deliverable:** `/` is the lab's work.

Render the boards first. Build top to bottom; each block **does not render** when it has nothing.

- [x] **NOW** — renders only if something is running **or** something is waiting on a person.
      Not a card saying nothing is happening. Not a zero.
- [x] **Work** — one block with a by-pipeline / by-run toggle, defaulting to **by pipeline**,
      because *what do we have and is any of it waiting on us* is the question someone opening
      the front door has, and by-run is the follow-up.
- [x] **The same table shape for both**, with columns that differ by object.
      By pipeline: *makes · provenance bar · run count · last outcome · owner* — readiness.
      By run: *started by · when · outcome · took · results* — history.
      **Cards for one and a table for the other was the tell** (`ov-work`); do not reintroduce it.
- [x] **Do not leak run information onto a pipeline card.** *"last run 2d ago · M. Silva"* on a
      pipeline row was the actual bug behind the two blocks reading as one list rendered twice.
- [x] The **provenance bar** is one stacked bar **per pipeline** — settled / measured / open —
      never one per value. It is a proportion of one whole, which is the only chart shape that
      earns a place on a page with four rows. Reuse `frontend/src/build/Provenance.tsx`'s tier
      mapping rather than writing a second one; **tier 3 is not counted as settled**, and that
      component's docstring says why in the sentence you should not have to rewrite.
- [x] **The person slot.** `submitted_by` is hardcoded `"operator"` at submit and `Run.submitted_by`
      is therefore a constant. Operator's decision, 2026-08-30: **keep the slot, ship no filter.**
      The column exists in the layout and renders as visibly not-yet-real, so accounts arrive as a
      filter rather than a re-layout; the `who` filter is **not** built, because `rn-board` and
      `ov-scope` both forbid shipping a filter that filters nothing. Pipeline rows use
      `PipelineDraft.who`, which is real.
- [x] **Results ready** — renders only if a run has published outputs, which Phase 1 made
      possible. Link to them.
- [x] **The resource sentence** — renders only once there are enough runs to aggregate honestly.
- [x] **The first-run state is its own composition** — one question, one field. Not this page with
      everything hidden, and not onboarding cards. `OverviewFirst.dc.html` is the board.
- [x] Join pipelines to runs **in the browser**, on the pipeline digest. Write the comment
      `useSubmit.ts` already has: this is the second place in the product that touches both
      halves, and it is deliberate that neither server knows about the other.
- [x] Delete `frontend/src/home/Standing.tsx`. Review `frontend/src/home/Artifact.tsx` — if the
      excerpt it renders is not on the new composition, delete it too. A component with no caller
      is a component that rots, and `Shell.tsx` already made that argument when it deleted `Soon`.
- [x] Add `it("is shorter when nothing is happening")` — the `Overview` / `OverviewQuiet`
      difference, asserted: with nothing running and nothing waiting, the NOW band is **absent
      from the DOM**, not present-and-empty. Watch it fail against a rendered empty card. This is
      the phase's central guard and the one most likely to be quietly regressed.
- [x] Add `it("names the values waiting on a person")` — assert the setting names appear and no
      bare count stands in for them.

---

## Task 7 — the handoff

- [x] Write `notes/journal/2026-08-30-the-overview.md`: what shipped, what the design notes got
      wrong (P2-1 and P2-4 especially), what was found by running it rather than by a test, and
      what the next phase inherits.
- [x] Update `CLAUDE.md`'s journal pointer **in this commit**. It went three entries stale before
      anybody noticed and the file now carries a line saying so.
- [x] Add the Plan 4 rows to [`../README.md`](../README.md)'s ordered table.

---

## Execution record

**Executed 2026-08-30**, on `worktree-plan-4-phase-0` (phases 0–2 share a branch, as
`wiener-w1` carried phases 0–3). `make check` green at **1686 passed** with a database up;
frontend gate green at **284 tests in 51 files**, `tsc` clean, lint unchanged at its five
pre-existing warnings. `make links` clean.

**The page was rendered and looked at in all three states** — active, quiet, first-run — served
from a production build against fixtures. That is the step this project keeps skipping and later
regretting, and it found three defects a green suite could not.

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | Yes, plus a finding that changed the shape of the answer | **The provenance bar cried wolf.** Counting raw tier 4 reported *five* things needing a person on the canonical spine where **one** does — a hand-drawn graph records every step as `tier: 4, source: human`, and `MD0220` says `source: human` is exactly what CLEARS a review. The artboard's three bands were drawn against resolver-built pipelines, where that case never arises. `Provenance` now reports five numbers, and `by_person` / `by_model` stay apart because the 4→5 schema bump exists so an agent-assembled pipeline does not read as one a person drew by hand. Measured warm at **35.5ms** for 21 pipelines (12 kept), against the ~250ms the 2026-08-19 audit flagged. |
| 2 | Yes | `RunArtifact.pipeline_digest` stopped being a declared column with no assignment. `content_digest()` rather than the tree digest, because the tree covers the vendored `modules/` and re-vendoring one would make the same pipeline look like a different pipeline. A test fixture had to be added — the existing `a_bundle`'s `pipeline.yml` is `schema_version: 5`, which is not a `Pipeline`, and two tests compare digests against a literal copy of those bytes. |
| 3 | Yes | `durations_by_pipeline` folds in Python following `board_summary`'s stated argument rather than reopening it, and a group below a floor returns **no median** — *usually 38m* over two runs is one figure wearing the clothes of a distribution. |
| 4 | Yes, and it corrected a sentence that had been false for a plan and a half | `Attention.mendel`'s docstring read *"nothing stores pipelines"* — false since Plan 3E, when drafts became Postgres rows. The forge half is **computed and not rendered** rather than deleted: a call pointing at a screen the frame offers no way into is worse than no call, and the day the forge returns so does it. |
| 5 | **Restated, not deleted** — which is what `ov-settled` asks for | `forge-review.md` §3 said this page may not exist; the operator lifted it. §3 now records the lift *and* the narrower rule that survives: `/` may render pipelines and runs, never a contract id, a question subject or a drift row. `test_the_standing_says_what_the_registry_holds` was deleted and replaced with an assertion that the field is **gone**, because a block that made the page look fuller is exactly the kind of thing that comes back. |
| 6 | No — the palette migration was added, on the operator's decision | The plan assumed the existing tokens. All 24 artboards are dark and the canvas settled **Observatory**, and the operator chose to migrate the whole product first. **A large decision and a small diff**: `tokens.css`, one `@theme` mirror, nothing else — because not one component names a colour anywhere. That held by convention and is now a guard checking all three spellings (hex, `rgba(`, Tailwind hues). `dashboard.md` §2 records what it supersedes: *deep botanical green, Mendel's peas* does not survive, and `--pea` keeps its **name**. Light is re-homed to `[data-theme="light"]`, not deleted. |
| 6 | And three defects that only rendering could find | The `flow` marker had `grow`, so it filled the entire remainder — claiming *everything not yet done is running right now* when 9 of 24 done means 15 remain and a handful are in flight. The running row was titled by its **run id** rather than its pipeline. And the elapsed time, which the artboard makes the second-largest thing on the band, was missing entirely. |
| 6 | And one deliberate absence with a reason | The **resource sentence** does not render. It needs reserved-vs-used aggregated across runs, and *reserved* lives in `run_task.attempts` as JSON rather than a column — the **same** projection phase 4 does for the envelope. Absence is absence; it is named in the journal rather than faked. |
| 7 | Yes | Journal, `CLAUDE.md` pointer (updated in this commit, as the file demands), `notes/journal/README.md`, and the three index rows. |

## The first-run prompt, and why it is disabled rather than absent

`OverviewFirst`'s primary affordance is a prompt box, and **it cannot work**: turning a sentence
into a `Goal` is **door 1**, which invariant 3 declares and nothing implements — there is no
adapter on the build path at all until Plan 3's tier-4 resolver.

Operator's decision: **draw it, disabled, with the reason underneath.** The case for omitting it
is `Shell.tsx`'s — a control going nowhere silently is worse than one that admits it — and a
disabled control that states its reason is neither. What must never happen is it appearing to
work, or the model producing a *pipeline* rather than a *goal* the person corrects.

## What this phase deliberately does not do

- **"Changed underneath you" is not built.** It needs `mendel upgrade --dry-run` per pipeline
  against the current registry, which is expensive and **must not run in a request** — it is a
  worker job on a schedule with the result stored, and the page reads a table. Operator's
  decision, 2026-08-30: **its own phase, after the Runs screens.** The block simply does not
  render, which is the same absence rule as everything else on the page. What makes it worth
  doing later, recorded so it is not lost: every pipeline pins its contracts by digest, so we can
  say what a re-resolve *would* move before anyone runs it, and nothing else in this space can.
  *A no-op upgrade is a real and useful answer* — show it, when it exists.
- **No scope switch.** `ov-scope` puts *lab / mine* in the shell beside the lab name, not on the
  Work toggle — two different questions, two different controls. There are no accounts, so there
  is nothing to switch between and a control with one option is decoration. What this phase owes
  the future is only that **every row carries a person**, and Task 6 pays that.
- **No registry inventory, no chart over fewer than ~50 rows, no "welcome back", no tips, no
  onboarding cards, no recently-viewed, and no "What the words mean" modal.** All named in
  `ov-settled`. Explanation attaches to the **term** — a help toggle that arms hover cards — never
  a glossary read in advance.
- **No `Registry` nav section.** Same reasoning as Phase 0 Task 1.
