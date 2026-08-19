# 2026-08-19 (later still) — Plan 3D: making the forge answerable

## Where things stand

**Plan 3D is complete**, all six phases, on `plan-3d-forge` — branched from `plan-3b-landing`,
which is branched from `plan-3-slice-1`. **None of the three is merged or pushed.**

The operator's verdict was that the forge is *"really unintuitive"* and *"unusable"*, and that
the landing page was built before the rooms it points at. Both were right. What the spec found by
**walking the loop as a user** rather than reading the code is that it was **not a looks
problem**.

Verify with:

```bash
make verify                                      # 1395 + 5 counts + 75 guards, exit 0
uv run pytest packages/mendel-forge/tests/test_candidate_ranking.py -v
cd frontend && npx vitest run && npm run build   # 78 tests, tsc -b green
```

## The number this plan exists for

`forge draft nf-core:samtools/faidx` opens eleven holes, seven of them `type_id`, and each
offered **the entire twenty-two-type vocabulary in alphabetical order**. For a port literally
called `fa`, emitted by `SAMTOOLS_FAIDX`, the interface presented `genome.fasta` and
`measurement.rrna_fraction` with equal prominence.

Measured over the 30 ports of the 12 landed contracts, which are ground truth for exactly these
modules:

| ranking | correct type ranked first |
|---|---|
| alphabetical — **what shipped** | **1 of 30 · 3%** |
| port == the type's last segment | 19 of 30 · 63% |
| + port is any segment | 22 of 30 · 73% |
| + the tool's own name shares a segment | **25 of 30 · 83%** |

**Signal 3 is not a refinement, it is what makes two of these answerable at all.** A port called
`index` is `alignment.bai` on `samtools/index` and `genome.index.star` on `star/genomegenerate`;
the only thing separating them is which tool is being drafted. Signals 1 and 2 alone rank the
wrong one first for both.

`candidates.for_field` had already computed the one ranking signal it possessed — which contracts
carry each type — and then **sorted by name and threw it away**.

## What changed this session

| commit | what |
|---|---|
| `c8f4e49` | the measurement harness, before the heuristic |
| `68a86ef` | rank type candidates by the port that is asking |
| `58ef6b0` | the port a hole is about reaches its candidates |
| `20b5082` | the producer `suggested` never had |
| `d5a72e5` | `priority_because` asks a question instead of naming itself |
| `ddd338d` | `GET /api/tools` — one board for every tool |
| `2a061bf` | one Tools page for every stage of a tool's life |
| `2680c0c` | a status board that answers *is everything okay* |
| `468a0de` | say what the words mean |
| this one | the front door, against the screens that now exist |

## Decisions made, and why

### `suggested` had every consumer and no producer

**The find that made phase 1 cheap.** `OpenQuestion.suggested` crosses the API, is keyed on by
`aggregate()`, sorted on by the queue's ordering, highlighted by `Question.tsx` and switches
`QueueRow`'s label from *Ask* to **Confirm** — and every `suggested=` in the repository was in a
test. It was `None` in production, so the Confirm branch was unreachable and the *Ask before
Confirm* ordering its own comment describes was a no-op.

Everything downstream was built, tested in isolation, and left without an input.

### The plan told me to ship a defect, and running it is what caught it

`suggested = candidates[0]` is what the plan said. Rendering a real `samtools/faidx` draft showed
it labelling `sizes`, `fai`, `gzi` and `versions_samtools` **Confirm** and offering
`alignment.bai` for all four — those port names say nothing about a type, so every candidate
scores 0 and the order is the alphabet.

**The change would have turned a screen that honestly said *Ask* into one inviting a person to
accept the alphabet.** That is the tier-4 mistake in a different costume: invariant 6 flags an
ambiguous decision *even at high model confidence*, for exactly this reason.
`candidates.suggestion()` now returns the top value only when `_fit` scored it above zero.

### Two signals both measured zero, and they were treated differently

- **The input-namespace signal was deleted.** 0 gain (25/30 either way), *and* structurally
  unusable where it was wanted: at draft time every `consumes[N].type_id` is still an open hole,
  so there is nothing to read.
- **Prefix matching (`fa` → `genome.fasta`) was kept.** Also 0 on the corpus — because the corpus
  is twelve **landed** contracts and the case it fixes is an **undrafted** tool. `samtools/faidx`
  is not in the registry; without it every candidate tied at 0 and alphabetical order returned
  `alignment.bai`.

**A corpus of landed tools cannot measure the tools the forge exists to draft.** That is a limit
of the measurement rather than a licence, and both docstrings say which is which so the next
person weighs it instead of inheriting it.

### Sources and Contracts were one query at two stages

A tool moves undrafted → drafted → landed. Both screens carried a `Facets` rail with **the same
docstring, written twice independently**, which is the clearest possible sign nobody had noticed.

The row is what actually changed, not the count of screens. It was `status | id | roles` at 57px,
spending 180px on a field that helps nobody choose a tool. It is now a mark, the tool, and
`consumes → produces` — or `11 open`, or `draft →`.

**The join is a union, not a lookup**, and the plan did not anticipate that: `sources.catalogue()`
walks what a source can *discover*, so iterating it would silently drop any contract whose module
is not in `vendor/`. Those are exactly the rows a person most needs, because they are the ones
nothing can re-read.

### The board answers *is everything okay* before it lists anything

Vercel's pattern. Three screens never answered it: Sources said what could be read, Contracts
what existed, the Queue what was open, and a person held all three and did the arithmetic.

**Reading the finished board found a duplication no test could.** Its figures sat directly above
a chip row reporting the same five numbers in a different order. The chips were **deleted rather
than moved** — a figure that sets the filter which produces it is one thing doing one job.

### Nothing defined the words

Eight appear on screen and nothing in the product defined one: contract, type, role, measurement,
drift, hole, band, proposal. `?` opens the glossary from anywhere; `<Term>` defines a word in
place. Held in step with `docs/reference/glossary.md` in **both directions**, the diagnostics
guard's shape.

**`<Term>` gained an `of` prop while being used.** A figure says `drifted`, a status says
`unverifiable`, the entry is `drift`. Without it, either the glossary dictates the copy or the
copy cannot be linked — and a glossary dictating an interface's words is the wrong way round.

### The front door stopped answering the board's question

`Standing` said *10 agree with their module · 2 have no source that can re-read them*, which is
now exactly what the board says, better, on the screen where you can act on it. **Two places
answering one question is how a number goes stale in one of them, and the front door is the one
nobody would have corrected.**

It narrowed to what no working screen answers: how much vocabulary exists. A stranger asks *what
does this thing know*; a curator asks *is anything wrong*. The board owns the second now, so this
owns the first cleanly instead of half of each.

**The undrafted row went too**, for a different reason: it said the same number as *What needs
you*, two blocks above, on one screen. Between an inventory line and a call to act on the same
fact, the call wins. `undrawn` therefore has no row today — **the strokes serve the content, not
the reverse**.

## What is next

1. **The operator's manual pass.** Three branches, none pushed. `make dev`, then `localhost:5173`.
2. **3C — the Mendel builder.** Two named prerequisites, neither started: orchestration out of
   argparse, and DAG layout.
3. **[#77](https://github.com/comeni-project/Comeni-Labs/issues/77)** — discovery reads
   `vendor/modules/`, so the catalogue total renders `—`. The board is shaped for the ~1,600 it
   will become.

## Open questions

- **`Forge` is still a nav item beside `Queue` and `Tools`**, and `Builder` sits beside it
  disabled. With two sections the workspace row and the section row have collapsed into each
  other. Spec §8 named this and it is still undecided.
- **The registry lookup has no home.** Deleted with the nav box in 3B; the Tools row now shows
  type ids, which is its natural host.
- **`roles` is rendered nowhere** since the contracts list went. It is what routing matches on,
  so it belongs on the module page rather than in a list — unverified.

## Traps

- **A test can go vacuous rather than red, and that is worse than failing.**
  `test_a_status_that_is_not_one_is_refused_rather_than_ignored` asserted `/api/contracts?
  against=broken` is a 422. Deleting the listing route did not fail it — the request now matches
  the greedy `/contracts/{id:path}` with an empty id and 422s with `'' is not in this registry`.
  **A greedy `{id:path}` swallows its own parent path**, so removing a sibling route cannot be
  checked by status code alone.
- **`test_an_undrafted_tool_is_an_invitation_not_a_warning` was keyed on a URL** and broke the
  moment the link moved — correctly, because a test matching `"sources" in call.where` is testing
  the router. It matches `state=undrafted` now.
- **A `<Navigate>` redirect replaces the whole location with a *fixed* query.** `/forge/sources`
  and `/forge/contracts` still resolve, but `?against=drifted` was being discarded — so the front
  door's *1 no longer agrees → open* landed on every landed tool. A redirect keeps an old link
  working; it is not somewhere new links should point.
- **`make verify` exited 2 twice, and both times it was lint with 1395 tests passing.** Run it
  unpiped. Piping to `tail` shows a wall of green over a non-zero exit, which is the mistake 3B
  made.
