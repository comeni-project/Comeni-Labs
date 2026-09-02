# Plan 3B — the landing page

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement
> this plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax,
> and **tick each one as it completes**. Do **not** farm the tasks out with
> `subagent-driven-development`; subagents are for review and design only.

**Goal:** `/` becomes a front door — what this is, what the registry holds, and what needs a
person — instead of a redirect to the queue.

**Architecture:** One endpoint over four services that already exist, returning *sections* so 3C
adds one rather than reshaping it. One screen, built from the existing token system, whose
signature is the product's own governing idea: **certainty is drawn, not labelled.**

**Spec:** [`notes/specs/2026-08-19-the-landing-page.md`](../specs/2026-08-19-the-landing-page.md)
— §1 is the one that matters, because an Overview page was already designed and cut.

**Design:** [`docs/design/dashboard.md`](../../design/dashboard.md) §2 governs both halves
and is followed exactly. **No new tokens, no seventh type size.**

**Preceded by:** Plan 3A, complete — nine phases, on `plan-3-slice-1`. This branches from it.

## Global Constraints

- **Work in the worktree** `.worktrees/plan-3b-landing`, branch `plan-3b-landing`.
- **The landing page counts and links. It never lists items.** Spec §1. The moment it renders a
  question row or a drift row it is competing with the destination that owns it, and it becomes
  the Overview page `forge-review.md` §3 already cut.
- **No new design tokens and no seventh type size.** `dashboard.md` §2 governs both halves; the
  set reached seventeen sizes once, all picked by eye, and a hero is exactly where the eighteenth
  gets invented.
- **An absence is not a zero.** Nothing stores pipelines, so there is **no Mendel section** rather
  than *"0 pipelines need review"* — the same discipline as `pipeline_pins: None` and
  `checked_at: null`, both of which earlier phases got wrong first.
- **No claim the code does not support.** This is the surface most likely to drift into
  *"validated"* or *"compliant"*; `CLAUDE.md` says never to claim IVDR/CLIA/CAP/ISO 15189, never
  to say "anonymised", and the v1 criterion is unmet.
- **Every operation carries an `operationId`, a tag and a summary**, held literally in
  `packages/mendel-api/tests/test_openapi.py`.
- **`frontend/src/api/` is GENERATED** — `make client` — never hand-edited.
- **`npm run build` is the frontend gate**, not `npx vite build`: `tsc -b` uses the project
  references and catches what `tsc --noEmit` does not. Phase 8 found six errors that way.
- Ruff line length 100; `npx oxlint src` and `npx vitest run` clean.
- **Verify with `make verify`**, reading the exit code *before* filtering.

---

## The design direction, decided before any code

**The brief pins the visual direction and it is followed exactly.** `dashboard.md` §2 is already
opinionated and subject-derived — deep botanical green from Mendel's peas, amber for measured,
coral for undecided, a serif display the design calls *"its one real risk"* because it reads
scholarly rather than startup. Inventing a second identity for the front door would be the
templated move, not the bold one.

**The freedom is in the signature, and the signature is the product's own governing idea:**

> Certainty is a property of how a thing is drawn, not a label attached to it.
> — `dashboard.md` §1

So the front door's memorable element is the **registry's standing drawn in the certainty
language it will meet again on the canvas**: each row of what the registry holds carries a rule
whose stroke says how well-founded it is.

| what | stroke | why that stroke |
|---|---|---|
| contracts that match their source | **solid**, `--pea` | checked against the module and agreeing |
| unverifiable | **dashed**, `--ink-3` | nothing could re-read them; a contract nothing checks is not a contract that agrees |
| drifted | **gapped**, `--undecided` | it was true and now is not |
| tier-3 rules | **dashed**, `--measured` | a rule is only as good as the measurement behind it |
| tools nobody has drafted | **no rule at all**, just the count | the line is not drawn yet |

**This is not decoration and it is not a chart.** It encodes the same thing the canvas encodes,
so a visitor who later opens a pipeline has already been taught to read it — which is the
strongest justification a signature element can have. `forge-review.md` cut a badge-per-node for
the same reason: *drawing incompleteness as incompleteness is the point.*

**Where the boldness is spent, and where it is not.** One element carries it. The rest of the
page is quiet: a sentence, a standing block, three destinations, and — when there is any — what
needs a person. No gradient, no hero number, no motion beyond what already exists.

**Copy, per `dashboard.md` §7:** name things by what a person recognises, and let an empty state
direct rather than apologise. Today's page opens on **0 open questions**, so the empty state *is*
the design.

---

## Task 1: What needs a person

**Files:**
- Create: `packages/mendel-api/src/mendel_api/services/attention.py`,
  `packages/mendel-api/src/mendel_api/routes/attention.py`,
  `packages/mendel-api/tests/test_attention.py`
- Modify: `mendel_api/main.py`, `tests/test_openapi.py`

**Interfaces:**
- Produces: `Urgency` (`BLOCKING`, `WAITING`, `IDLE`); `Call(what, where, count, urgency)`;
  `Standing(contracts, matching, unverifiable, drifted, types, roles, rules, measurements, sources, undrafted)`;
  `Attention(forge, mendel, standing)`; `GET /api/attention` → `whatNeedsYou`.

**Measured today**, and the page has to be honest about all of it:

```
contracts 12   types 22   roles 9   rules 1   measurements 12
status    {drifted: 0, unverifiable: 2, matching: 10}
tools     {undrafted: 3, drafted: 0, landed: 10}    sources ['nf-core']
questions 0
```

- [x] **Step 1: Write the failing tests**

```python
# packages/mendel-api/tests/test_attention.py
"""What needs a person, across both halves.

**Counts and links, never items.** Spec §1: an Overview page was designed and cut once because
it answered the Queue's question, and the discipline that keeps this from becoming that page is
that it never renders a row. These tests hold the shape that makes it possible.
"""

from mendel_api.services import attention
from mendel_api.services.attention import Urgency


def test_it_reports_what_is_open_without_listing_it():
    got = attention.whats_open()
    for call in got.forge:
        assert call.count >= 0
        assert call.where.startswith("/forge/"), "every call leads somewhere that owns it"
        assert call.what, "a count with no sentence is a number nobody can act on"


def test_the_mendel_half_is_absent_rather_than_zero():
    """Nothing stores pipelines, so there is nothing true to say. `0 pipelines need review`
    would claim that pipelines were looked at — the same falsehood as `0 of 0 emit channels`
    and `0 match their source`, both of which shipped once and were corrected."""
    assert attention.whats_open().mendel == []


def test_drift_outranks_an_undrafted_tool():
    """Drift breaks pipelines that already run; an undrafted tool is an opportunity. The
    landing page sorts by the same consequence order the queue does."""
    assert Urgency.BLOCKING.rank < Urgency.IDLE.rank


def test_the_standing_says_what_the_registry_holds():
    """Not what it needs — that is the other half of the page. This is the half that makes the
    front door a place rather than an inbox."""
    standing = attention.whats_open().standing
    assert standing.contracts == 12
    assert standing.types == 22
    assert standing.matching + standing.unverifiable + standing.drifted == standing.contracts
    assert standing.sources == ["nf-core"]


def test_an_undrafted_tool_is_an_invitation_not_a_warning():
    """Measured: three vendored tools have no contract. The page offers them as available work
    rather than as a deficiency, which is what `idle` means."""
    got = attention.whats_open()
    undrafted = [c for c in got.forge if "draft" in c.where]
    assert undrafted, "nothing is undrafted — this test is now vacuous"
    assert all(c.urgency is Urgency.IDLE for c in undrafted)
```

- [x] **Step 2: Run them and watch them fail**

- [x] **Step 3: Write the service**

```python
# packages/mendel_api/services/attention.py
"""What needs a person, and what the registry holds.

**Sections, not a flat list.** The interface spec's own test of this design is that 3C *gains*
Mendel's items without changing shape — a flat list would make `mendel` a filter on a field,
and the day pipelines exist somebody has to decide what that field is called.

**Counts and links, never items.** Spec §1. The Queue owns questions, Contracts owns drift,
Sources owns what can be started; this page says how much and points. An Overview page that
listed rows was designed and cut once for answering the Queue's question, and rendering one row
here is how that decision gets undone by forgetting it.
"""
```

with `whats_open()` reading `checked.result()`, `contracts.listing()`, `sources.catalogue()`,
`queue.read()` and `registry.stack()`.

**Measured rather than assumed, and the first draft of this plan said ~10ms:**

```
warm, all four            24.5 ms
  contracts.listing        9.4 ms
  sources.catalogue        6.3 ms
  queue.read               4.5 ms
  registry.stack           4.6 ms
```

Roughly **18ms of that is `digest_of_directory` computed four times** — each service keys its own
cache on it, at 4.6ms a call. Inside the half-second budget by twenty times, so it is recorded
rather than fixed: the two ways to remove it are duplicating what `listing` and `catalogue`
compute (which is the second-answer mistake phases 4 and 6 exist to avoid) or threading a digest
through four call sites for 18ms. **Neither is worth it at this size**, and audit A138 already
records that the digest stops being cheap at 5,800 contracts — that is where this is paid for
properly, not here.

**`Urgency.rank` is declared, not derived from the member order** — the third time this project
has needed that note, after `Band.rank` shipped alphabetical and `Impact.rank` and `State.rank`
were written to avoid it.

- [x] **Step 4: The route**

```python
@router.get("", operation_id="whatNeedsYou", summary="What needs a person, across both halves")
def attention() -> Attention:
    return service.whats_open()
```

Mounted at `/api/attention`; the tag goes in `main.py`'s `TAGS` and the operation in
`test_openapi.py`'s literal list.

- [x] **Step 5: `make client`, run the API suite, commit**

---

## Task 2: The front door

**Files:**
- Create: `frontend/src/home/Home.tsx`, `frontend/src/home/Standing.tsx`,
  `frontend/src/home/Home.test.tsx`
- Modify: `frontend/src/app/router.tsx`, `frontend/src/app/Shell.tsx`

- [x] **Step 1: Write the failing tests**

Six behaviours, and three of them are things the page must **not** do:

```tsx
it("says what this is, in one sentence", ...)
it("draws the registry's standing", ...)
it("leads with what needs a person when something does", ...)
it("directs rather than apologises when nothing does", ...)   // today's real state
it("never lists a question, a contract or a drift row", ...)  // spec §1, the discipline
it("says the builder is not built rather than showing it as empty", ...)  // spec §3.3
```

The fifth is the one worth writing carefully: assert that no element carries a question's
`subject` or a contract's id — a page that renders one row has become the page that was cut.

- [x] **Step 2: Run them and watch them fail**

- [x] **Step 3: Build the standing block — the signature**

The certainty language from the direction above, in SVG or CSS borders using only existing
tokens. Each row: a rule, a count, a label, and a link to the destination that owns it.

**A legend is not allowed.** `forge-review.md` cut the builder's five port shapes for exactly
this — *"an encoding that needs its legend on screen at all times is a lookup with extra steps"*.
Two strokes are readable without one; if a third is needed, that is a sign the encoding is too
clever and should be cut back rather than explained.

- [x] **Step 4: Build the page around it**

Four blocks, in this order, because it is the order of a person's questions:

1. **what this is** — the product's own sentence, display face, used once
2. **what needs you** — the calls, worst first; or the empty state, which is today's real screen
3. **what the registry holds** — the standing block
4. **where to go** — the three destinations, named for the work they hold

Keep it under ~180 lines; the standing block is already its own component.

- [x] **Step 5: `/` becomes a route, and the nav gains Home**

`router.tsx`: replace `<Navigate to="/forge/queue" replace />` with `<Home />`. **Delete the
redirect and its comment** — that comment says the landing page is 3B and a placeholder would be
thrown away, and leaving it beside a real home is the stale-sentence problem in miniature.

`Shell.tsx`: a `Home` tab first. The Forge entry keeps pointing at the queue — `forge-review.md`
§4's *"only home"* is about the forge and stays true.

`router.test.tsx` asserts `/` no longer redirects.

- [x] **Step 6: The frontend gate**

`npm run build && npx oxlint src && npx vitest run`. **`npm run build`, not `npx vite build`.**

- [x] **Step 7: Commit**

---

## Task 3: See it, then write it down

- [x] **Step 1: Look at it**

`make dev`, then `http://localhost:5173/` and `http://localhost/`. **Both**, because phase 8
made dev serve the prod path too and this is the screen most worth checking in both.

Then break something and look again: draft a tool so a question appears, and manufacture a drift
in `.run/registry`, so the page is seen with work on it as well as empty. **Today's registry has
0 open questions, so the empty state is what ships unless it is deliberately exercised.**

- [x] **Step 2: Check it against its own rules**

- no row from any destination is rendered
- no new token, no new type size — diff `tokens.css` and confirm it is untouched
- no Mendel section, and one line saying why
- nothing claims more than the code does

- [x] **Step 3: `make verify`** — read the exit code before filtering.

- [x] **Step 4: Journal and indexes**

`notes/journal/2026-08-19-plan-3b-landing.md`, plus `notes/README.md` and `CLAUDE.md`. Say
plainly that the Overview page was cut once and why this one is different — **and that the
argument is only as good as 3C**, because if the Mendel half turns out to be a second queue this
page should be cut the way the Overview was.

- [x] **Step 5: Commit**

---

## Execution record — Task 3

| step | carried out as written? | what actually happened |
|---|---|---|
| 1 | **no — read, not seen** | The rendered text was dumped through a jsdom render and read as copy; the API was run on :8150 against a scratch workspace with a drafted tool, so the page was exercised *with work on it* as the step asks. **The visual pass in a browser, at both URLs, was not done and is the operator's** — no screenshot was taken and none could be. Reading the copy is what found the `Mendel`/`Mendel` tab collision, so the step earned itself; it did not earn the half it skipped. |
| 2 | yes, plus one correction | The grep for `0 pipelines` hit the *comment* forbidding the phrase. Checked against the rendered output instead, which is the honest target. |
| 3 | yes, after a caught mistake | The first run was piped to `tail`, so the reported exit code was `tail`'s. Re-run unpiped. The step says *read the exit code before filtering* and the first attempt did exactly what it warns against. |
| 4 | yes | Journal, `notes/README.md` row 17k, `CLAUDE.md`. **Also found: `notes/journal/README.md`'s entry table has been stale since 2026-08-13, missing 24 entries.** Marked in place rather than backfilled — 24 accurate summaries means reading 24 entries, which is not 3B's work. |
| 5 | yes | |

**One change outside the plan:** the nav's `Mendel` tab became `Builder`, with
`router.test.tsx`'s disabled-destination list and comment moved with it. See the journal.

---

## Self-Review

**Spec coverage:**

| spec section | task |
|---|---|
| §1 counts and links, never items | 1 (shape), 2 (the test that holds it) |
| §3.1 sections so 3C adds one | 1 |
| §3.2 a front door, not only a dashboard | 2 |
| §3.3 the Mendel half is absent, not zero | 1, 2 |
| §3.4 the empty state is today's real screen | 2 |
| §3.5 `/` stops redirecting; the queue stays the forge's home | 2 |
| §3.6 no new tokens | the direction section, and Task 3 Step 2 |

**The audit of this plan found three things.**

1. **The landing page is the page this project already deleted.** `forge-review.md` §3 records
   an Overview page cut for answering the Queue's question, and §4 calls the Queue *"the only
   home"*. That is not an obstacle to route around — it is the first thing the spec has to
   answer, and §1 does: the front door answers *what is this and what does it hold*, which no
   destination answers, and the discipline that keeps it there is that it never lists an item.
   **If that discipline slips, this page should be cut rather than defended.**
2. **The page costs 24.5ms warm, not the ~10ms this plan first claimed** — measured, and about
   18ms of it is one `digest_of_directory` per service, four times over. Recorded rather than
   fixed, with both fixes named and rejected at this size. A number written into a plan without
   being measured is exactly what phase 7's audit was about.
3. **The design direction is already chosen, and inventing a second one would be the templated
   move.** `dashboard.md` §2 is subject-derived and opinionated — botanical green from Mendel's
   peas, a serif the design calls its one real risk. The plan follows it exactly and spends its
   freedom on the signature, which is the product's own governing idea rather than a new one.

**Known weak points, stated rather than hidden:**

- **The whole page is justified by a half that does not exist.** Its second question — *which
  half needs me?* — is unanswerable until 3C, so today it rests on the first question alone.
  That is enough, and it is thinner than the interface spec imagined.
- **Today's page is almost entirely its empty state.** 0 open questions, 0 drift. The screen that
  ships is the one hardest to judge, which is why Task 3 Step 1 says to manufacture work and look
  again rather than shipping on the empty view.
- **The certainty stroke is being reused outside the canvas it was designed for.** It reads well
  on a graph where wires inherit it; on a list of counts it may read as decoration. Task 3 Step 2
  is the check, and cutting back to one stroke is the fallback rather than adding a legend.
- **Nobody has clicked any of the nine phases before this one.** This plan's Task 3 Step 1 is the
  first step in the project that is only a person looking at a screen.
