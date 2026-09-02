# 2026-08-19 — Plan 3B: the front door

## Where things stand

**Plan 3B is complete**, on `plan-3b-landing`, branched from `plan-3-slice-1`. `/` is a
landing page rather than a redirect to the queue, and `GET /api/attention` is the one endpoint
behind it.

Verify with:

```bash
cd frontend && npx vitest run          # 74 pass
cd frontend && npm run build           # tsc -b, green
make verify
uv run python -c "from mendel_api.services.attention import whats_open; print(whats_open())"
```

The page has four blocks, in the order of a person's questions:

1. **what this is** — one sentence, for a stranger arriving at a public repository
2. **what needs you** — one row per call, worst first
3. **what is here** — what the registry *holds*, with certainty drawn as stroke
4. **where to go** — three destinations, named for the work each holds

## What changed this session

| commit | what |
|---|---|
| `f21f79a` | `feat(api): what needs a person` — `services/attention.py`, `routes/attention.py`, `Urgency`, `Call`, `Standing` |
| `af63a36` | `feat(frontend): the front door` — `home/Home.tsx`, `home/Standing.tsx`, the redirect removed, `Home` tab added |
| this one | the `Mendel` → `Builder` tab rename, the journal, the indexes |

## Decisions made, and why

### An Overview page was designed and cut, and this is not that page

`docs/design/forge-review.md` §3 records an Overview screen **cut** for answering the same
question as the Queue, and §4 calls the Queue "the only home". That is the strongest argument
against building this at all, and the spec (`notes/specs/2026-08-19-the-landing-page.md` §1)
answers it rather than ignoring it.

**The discipline that makes it defensible: this page counts and links, it never lists an item.**
The moment a contract id or a question subject renders here, it has become the page that was
cut. `test_never_lists_a_question_a_contract_or_a_drift_row` holds that literally, and both the
service docstring and the component docstring say why, because the reason is what gets forgotten.

### Certainty is drawn, not labelled — the signature element

`dashboard.md` §1: *certainty is a property of how a thing is drawn, not a label attached to
it*. The canvas draws a tier-3 node's rail dashed and a tier-4 node's gapped. `Standing.tsx`
reuses exactly that language for the registry itself — solid pea for a contract that agrees with
its module, dashed ink-3 for one nothing can re-read, dotted coral for one that drifted, dashed
amber for a rule reading measured data, no line at all for an undrafted tool.

A visitor who later opens a pipeline has already been taught to read the strokes. That is the
strongest justification a signature element can have, and it is why this is a set of rules and
not a chart. **No legend** — `forge-review.md` cut the builder's five port shapes because *"an
encoding that needs its legend on screen at all times is a lookup with extra steps"*; each row
says in words what it is, and a reader who ignores the stroke loses nothing.

**No new tokens.** `tokens.css` is byte-identical — `git diff --stat` on it is empty. Every
colour and size on the page already existed.

### An absence is not a zero

`Attention.mendel` is `[]` and the page renders **no Mendel section at all**, with one sentence
saying the builder is not built yet. `0 pipelines need review` would claim that pipelines were
looked at. Same discipline as `pipeline_pins: None`.

It is a *section* rather than a filter on a flat list, and the test of the design is that 3C
gains Mendel's items without changing shape.

### `Urgency.rank` is declared, not derived from member order

Fourth time this project has needed the note. `Urgency` is a `StrEnum`, so `sorted()` compares
the strings and answers blocking, idle, waiting — alphabetical order reading as consequence.
`Band.rank` shipped that way once and put cosmetic work above routing.

### An undrafted tool is `idle`, not a deficiency

The three urgencies are *what it costs if it waits*, not *how likely it is to matter*. Drift is
`blocking` because it breaks something that already works; an open question is `waiting` because
somebody is held up; an undrafted tool is an opportunity, and rendering it in the same visual
register as drift would be the wrong sentence entirely. Today's real screen has zero of the
first two, so the empty state — *"Nothing is waiting on you. There are 2 tools nobody has
drafted, if you want somewhere to start."* — is the screen that actually ships.

### The `Mendel` tab became `Builder`, and reading the finished page is what caught it

Not in the plan. The rendered page's own title is **Mendel**, and the nav carried a greyed-out
`Soon` tab also called **Mendel** — so the front door read as *the whole product is not built*.
The tab points at a **screen**; the product is the site. `router.test.tsx`'s disabled-destination
list moved with it, and its comment records why so the next rename is deliberate too.

This is the argument for Task 3 Step 1 existing at all: nothing in the type system, the tests or
the lint could have found it, and it is the first thing a visitor sees.

### The argument for this page is only as good as 3C

Spelled out because it is the condition under which this page should be **cut**, not a caveat.
The Overview was cut for answering the Queue's question. This one survives on the claim that
*what is this* and *what does this hold* are questions no destination answers — and on the claim
that a second half is coming whose work belongs beside the forge's.

**If 3C's Mendel half turns out to be a second queue**, then this page's "what needs you" block
is a router between two inboxes, which is the Overview's failure with an extra step. Cut it then,
the way the Overview was cut, and say so in a later entry. What would keep it even then is block
3 — *what is here* — which is the half no inbox has.

## What is next

1. **The operator's manual pass.** `plan-3-slice-1` (34 commits) and this branch are both
   unpushed and unmerged, waiting on it. That was the plan.
2. **3C — the Mendel builder.** Two named prerequisites, neither started: orchestration has to
   come out of argparse, and the DAG needs a layout.
3. **The journal index backfill** — see Traps.

## Open questions

- **The wordmark says `Forge` on every screen, including Home.** It was right when `/`
  redirected into the forge and every destination was a forge screen. It is now the brand block
  on a page that is not the forge, and 3C will add a half that is not either. Left alone
  deliberately: it is an identity decision, not a bug, and the operator has not been asked.
- **`Standing` carries `roles` and `measurements` and the page renders neither.** They are
  cheap, honest and currently unused — kept because a front door that cannot say how large the
  closed vocabulary is has to re-derive it later, and dropped fields are harder to re-add than
  unused ones are to render. If they are still unrendered after 3C, delete them.

## Traps

- **`notes/journal/README.md`'s entry table stopped on 2026-08-13.** Twenty-four entries are
  missing from it, including every 3A phase and this one, so *the newest row in that table is six
  days stale while the directory is current*. This entry adds its own row and a marker; the
  backfill itself is not done, because writing 24 accurate one-line summaries means reading 24
  entries and that is not 3B's work. **Read the directory listing, not the table**, until it is
  fixed. It is exactly the drift A33/A71/A72 are about, in the file that warns about drift.
- **The page's own source contains the string `0 pipelines`** — in a comment explaining why the
  page must never render it. A grep for the forbidden phrase over the source is a false positive;
  grep the rendered output. The compose guard has the same shape for the same reason.
- **`whats_open()` calls four services and each one loads the registry.** It is 24.5ms warm only
  because phase 7's `@lru_cache` on the registry digest makes the second through fourth loads
  free. Add a fifth service that loads outside that cache and the front door — the first screen
  anybody sees — is where it shows up. `notes/audits/2026-08-19-performance-audit.md` A138 is
  where that stops being true.
