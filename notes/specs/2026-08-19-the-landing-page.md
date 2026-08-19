# The landing page — Plan 3B

**Status:** written 2026-08-19, against the code Plan 3A landed.
**Implements:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §3B — *"what needs
you today" across both halves* — and §5's `/attention` row, which is the only line ever written
about it.
**Designs:** nothing designed this. `docs/design/forge-review.md` covers the forge's ten screens
and `docs/design/dashboard.md` covers Mendel's canvas; a home for the whole thing was never drawn.
This spec draws it, so the design's own rules are the authority rather than an artboard.

**Operator's instruction, 2026-08-19:** *"so I can see the landing page and have the website be
more of a 'website'."* That second clause is a requirement, not decoration, and §3.2 is what it
changed.

---

## 1. The thing this spec has to answer first

**An Overview page was already designed and cut.** `forge-review.md` §3 records it plainly:

> Applied backwards the rule already deleted things: an **Overview** page was designed and then
> cut, because it answered the same question as the Queue.

And §4 is titled *"The Queue — the only home"*.

So a landing page is, on the forge design's own account, the thing that was deleted — and
building it without answering that would be undoing a decision by forgetting it.

**The resolution is that they answer different questions.** The cut Overview answered *"what work
is open?"*, which is the Queue's question asked twice. A front door answers two the Queue cannot:

- **"What is this, and what state is it in?"** — the question a person has on arriving, including
  a stranger who typed the URL. This repository is public.
- **"Which half needs me?"** — which becomes real in 3C and is *not yet*, and §3.3 says what that
  means for today.

**And one discipline keeps it from drifting back into the cut page: the landing page counts and
links; it never lists items.** No question rows, no drift rows, no contract rows. The moment it
lists one, it is competing with the destination that owns it, and the Queue stops being the only
home. That single rule is what makes this survive `forge-review.md` §3 rather than contradict it.

---

## 2. What exists to be truthful about

Measured, 2026-08-19, against the shipped registry:

```
contracts        12          contract status  {drifted: 0, unverifiable: 2, matching: 10}
declared types   22          tools            {undrafted: 3, drafted: 0, landed: 10}
roles             9          sources          ['nf-core']
rules             1          open questions   0
measurements     12
```

Four endpoints already answer all of it: `/api/health/registry`, `/api/questions`,
`/api/contracts`, `/api/sources`.

**Two of those numbers are the interesting ones, and a landing page that hid them would be
decoration**: `rules 1` — the tier-3 rule table has a single entry, and tier 3 is the
differentiator — and `open questions 0` with `undrafted 3`, which together say *nothing is
waiting on you, and there are three tools you could start.*

| Does **not** exist | Consequence |
|---|---|
| any `/attention` endpoint | §4.1 |
| any route at `/` but a redirect | `/` has redirected to the queue since phase 0, marked temporary |
| anything storing pipelines | §3.3 — the Mendel half has nothing true to say |
| any identity on the page beyond a nav word | §3.2 |

---

## 3. Decisions

### 3.1 One endpoint, shaped so 3C adds a section rather than changes one

`GET /api/attention` returns **sections**, each a count, a sentence, and where it leads:

```python
class Call(BaseModel):        # something asking for a person
    what: str                 # "3 tools nobody has drafted"
    where: str                # "/forge/sources?state=undrafted"
    count: int
    urgency: Urgency          # blocking | waiting | idle

class Attention(BaseModel):
    forge: list[Call]
    mendel: list[Call]        # empty today, and §3.3 is why that is not a zero
    registry: Standing        # what the registry holds, not what it needs
```

**Sections rather than a flat list**, because the interface spec's test of this design is that
3C *gains* Mendel's items without changing shape. A flat list would make `mendel` a filter on a
field, and the day pipelines exist somebody has to decide what that field is called; a section
that is empty today is a section that fills.

**`urgency`, not a boolean.** Drift breaks pipelines that already run; an undrafted tool is an
opportunity. Collapsing those into *needs attention* is the flattening `Band.rank` already exists
to prevent one screen over, and the landing page sorts by the same consequence order.

### 3.2 It is a front door, not only a dashboard — and that is the operator's instruction

*"Have the website be more of a 'website'."* Concretely, three things the forge's screens do not
do, because they are tools and a person is already inside them:

- **Say what this is.** One sentence, in the product's own words: *deterministic pipeline
  construction, where every decision traces to a constraint, a convention, a measurement or a
  flagged judgement call.* A stranger arrives here; the repository is public.
- **Say what state it is in.** The registry's standing — contracts, types, roles, rules — as
  *what exists*, not as *what needs you*. That is the half a dashboard usually omits and the half
  that makes a site feel like a place rather than an inbox.
- **Offer the way in.** The three destinations, named for the work they hold, so the nav is not
  the only way to discover them.

**This is where the "different kind of work" test is actually passed.** *What is this and what
does it hold* is not a question any of the three destinations answers, and it is not the Queue's
question restated.

**What it must not become:** a marketing page. No claims the code does not support, and
`CLAUDE.md`'s list of things never to say applies here more than anywhere — this is the surface
most likely to drift into *"validated"* or *"compliant"*. The v1 criterion is unmet and the page
does not imply otherwise.

### 3.3 The Mendel half is absent, not zero

Nothing stores pipelines. So the landing page shows **no Mendel section at all** rather than
*"0 pipelines need review"*.

This is the same discipline as `pipeline_pins: None` on the module page and `checked_at: null` on
the health strip, both of which the phases before this one got right after getting them wrong:
**a zero is a measurement and an absence is not.** *"0 pipelines need review"* claims that
pipelines were looked at.

In its place, one line saying the builder is not built and what it will hold — which is also the
honest answer to a visitor's *"where is the pipeline part?"*.

### 3.4 Nothing is urgent is a state worth rendering well

Measured today: **0 open questions.** So the first thing anyone sees on this page, right now, is
the empty state — and an empty state is what phases 1–8 kept getting wrong by treating it as a
missing list.

*"Nothing is waiting on you"* is the headline, and beneath it what is *available* rather than
required: three tools nobody has drafted, one rule where the design expects many. Design §7's
copy rule says empty states direct rather than apologise, and this is the largest empty state in
the product.

### 3.5 `/` stops redirecting, and the queue stays the forge's home

Phase 0 made `/` redirect to `/forge/queue` and called it temporary in writing. It becomes a real
route.

**The nav gains `Home` and the Forge entry keeps pointing at the queue.** Nothing about the
forge's own navigation changes — `forge-review.md` §4's *"only home"* is about the forge, and it
stays true: inside the forge, the queue is where you live.

### 3.6 It reuses the existing design system and adds nothing to it

Six type roles and nine spacing steps from `dashboard.md` §2. **A landing page is exactly where a
seventh size gets invented** — a hero wants to be bigger than anything else on the page — and the
interface spec already names that as the drift the tokens exist to prevent, after the set reached
seventeen sizes all picked by eye.

If the largest existing role is too small for a front door, that is a change to the token set with
its own argument, not a one-off.

---

## 4. The surface

| Method | Path | operationId | Over |
|---|---|---|---|
| `GET` | `/api/attention` | `whatNeedsYou` | the four services already built |

```
/                          DESTINATION — the front door. No longer a redirect.
```

One request, not four: the page asks one question and the join belongs where the data is —
the same argument `sources.catalogue` already makes.

---

## 5. What this does not settle

**Whether the landing page survives 3C.** Its whole justification is that it answers a question
no destination does; if the Mendel half turns out to be a second queue, the honest move is to
re-read `forge-review.md` §3 and consider cutting this the way the Overview was cut. Written down
now, while it is cheap to say.

**Whether `urgency` has the right three levels.** `blocking` / `waiting` / `idle` is a guess
shaped by the queue's five-rung order, made before anything has been triaged by a person.

**Auth, and what a stranger sees.** The repository is public and this page is the front door, but
nothing here is authenticated and nothing here is exposed — auth has been deferred since the
interface spec §9 and this does not change that. What it does change is that the *first* screen is
now the one most worth thinking about when auth lands.

**Whether one endpoint stays one request.** Four services back it today and each is cheap after
phase 7 — the whole page should be one ~10ms call. If a fifth section ever needs something slow,
the answer is to make it fast rather than to split the page into four requests.
