# 2026-08-19 (later) — the front door, redesigned

Corrects nothing in [`2026-08-19-plan-3b-landing.md`](2026-08-19-plan-3b-landing.md) — that
entry is still true about what was built and why. This is what happened when the operator
**looked** at it, which is the half that entry said was theirs.

## The verdict, and what it was right about

> *"home page is extremely ugly"* · *"Comeni Labs, in navbar, always shows Forge, that is not
> true"* · *"the top right Registry searchbar is ugly, unintuitive and useless"*

All three were correct and two of them were **known and shipped anyway**, which is the part worth
recording:

- The wordmark was listed under **Open questions** in the previous entry, described almost
  exactly as the operator described it, and left alone on the grounds that it was "an identity
  decision, not a bug". It was a bug. *Wrong on every screen* is not a matter of taste, and
  filing it as a question the operator would have to raise put the cost on them.
- The Registry box's own docstring argued it was a box rather than a toggle *"because a lookup
  with no id is useless"*. That reasoning stops one step short: a lookup that makes you **retype
  an id you are looking at** is also useless. `forge-review.md` §3 wanted the registry consulted
  *mid-decision*; you consult it by clicking the thing, not by copying it into a corner.

The ugliness was structural rather than cosmetic: four stacked sections of 13px text in a 760px
column, and the largest thing on the page was 26px. That is a **tool** scale — correct for the
forge, wrong for a page whose job is to be understood by a stranger in ten seconds.

## What changed

| commit | what |
|---|---|
| this one | the hero, the wordmark, the deletion of the lookup, `--text-hero`/`--text-lede` |

### The hero is the artifact

**The strongest thing this product can put in front of a stranger is its own output.** The claim
is *nothing was guessed silently*; fourteen lines of a real `pipeline.yml` prove it in a way no
sentence can. `src/home/Artifact.tsx` quotes
`notes/audits/fixtures/pipeline-v1/pipeline.yml` — a real build of the RNA-seq spine — showing
two blocks back to back:

- **tier 3**, amber rail: STAR chosen because a rule matched `read_length >= 70`, citing Dobin et
  al. 2013 by DOI.
- **tier 4**, coral rail: `seq_platform`, *"selected the first of 1 candidates without judgement
  — please review"*.

A product that leads with its own admission of uncertainty is doing the opposite of what a
landing page usually does, and that is the whole differentiator. It is the one real risk in the
design, and it is the one thing on the page a competitor cannot copy without building the engine.

**The line it must not cross** is the discipline the whole page rests on — spec §1, *counts and
links, never items*. An excerpt of the **format** is documentation; a row of the registry's
**current contents** would make this the Overview page that `forge-review.md` §3 cut.
`renders the same excerpt whatever the API says` holds that literally: it renders the page against
two different API responses and asserts the excerpt is byte-identical. **Watched failing** —
swapping the contract id for `Math.random()` fails it.

### Two type sizes, and a fence around them

`--text-hero: clamp(30px, 6vw, 44px)` and `--text-lede: 16px`, in `main.css`, commented as
**front-door only**. `dashboard.md` §2's six roles govern the tool and 26px stays the largest
thing on a working screen; the landing page has a job the tool does not. The comment says that if
either size appears outside `src/home/`, one of the two scales is wrong.

**Nothing else was added.** No new colour, no new radius, no new font. The palette was already
specific — pea green on green-tinted paper, with the tiers' amber and coral — and Georgia reads
as *scientific paper* rather than as a startup, which is the correct register for a tool whose
output cites DOIs. The redesign is entirely a matter of scale, density and hierarchy.

### One visual language, at two scales

The page teaches the tier colours in the hero (a decision's rail is amber or coral) and the
certainty strokes in *What is here* (a line is solid, dashed, dotted or absent). Those are the
same idea at two magnifications, which is why there are two prominent elements and not two
competing ones. `dashboard.md` §1 is the source of both: *certainty is a property of how a thing
is drawn, not a label attached to it.*

### The wordmark names the site

`Comeni Labs`, linking to `/`. It said `Forge · Comeni Labs`, which was true while `/` redirected
into the forge and every destination was a forge screen — and false the moment 3B shipped. The
`Home` tab went with it: the wordmark is the way home on every site, and a nav item duplicating
it is clutter.

### The Registry box and the Lookup panel are deleted

Not hidden — **deleted**, with `Lookup.test.tsx` and the stale comment in `Contracts.test.tsx`,
per the standing instruction not to leave dead code behind a removal. Nothing else in the app set
`?lookup=`, so keeping the panel would have left 102 lines reachable by nothing.

**The capability was worth having and the placement was wrong.** When it returns it should hang
off a type id in a question or a contract — click `alignment.bam`, get the panel. That is one
`git revert` away and belongs to the forge conversation, not this one.

## What is next

**The forge screens.** The operator's closing line: *"after that we can discuss the general forge
design it's really unintuitive."* That conversation has not happened and nothing has been decided
about it. Two things this session already turned up that belong in it:

1. **`Forge` and `Queue` are the same destination** in the nav, one in the workspace row and one
   in the section row. Defensible as *workspace vs. its sections* while Builder is disabled, and
   it reads as a duplicate.
2. **The registry lookup needs a home**, per above.

## Traps

- **The excerpt is a quote and the guard exists because it is tempting not to be.** `tier` is the
  first key under `why:` in the real file. The first draft put the tier badge at the *bottom* of
  each block because it anchored better, which quietly turned a quote into a mock-up. It was
  moved back.
- **`--text-hero` and `--text-lede` are not part of `dashboard.md` §2** and must not leak into
  the forge. The comment in `main.css` is the only thing enforcing that today; there is no test.
- **`getByText(/nf-core/)` on the home page now matches twice** — the quoted contract id and the
  sources note. The assertion was scoped to `/read from nf-core/i` rather than loosened.
