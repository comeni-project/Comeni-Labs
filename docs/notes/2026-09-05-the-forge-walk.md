# Walking the forge by hand

**What a test cannot do.** Task 13 asks for the loop to be driven end to end, and three of its
boxes need a person: a browser, a real model, and eyes on a screen beside the drawing it came
from. `packages/mendel-api/tests/test_full_cycle.py` does the half a suite can — catalogue →
scaffold → answered holes → approval → a git commit → a layer that loads back — and this page is
the other half.

It is a checklist, not a tutorial. `docs/handbook/the-stack.md` is how to bring the stack up.

---

## Before you start

```bash
make dev                 # the whole stack, plus Vite on :5173
make ai-up               # the local model server. Downloads nothing
make ai-pull MODEL=qwen2.5-coder:14b
```

Put the two lines `make ai-up` printed into `.env`, then:

```bash
docker compose up -d --force-recreate ai-worker
curl -s localhost:8000/api/health/ai
```

You want `configured: true`, `model_available: true`, `worker_available: true`. If any of those
is false, the table in `the-stack.md` says what to do about it — come back when they are not.

---

## 1. An nf-core adaptation, with the model

Open `http://localhost:5173/forge`.

- [ ] The source cards show real counts, and the bar's segments add up to *adaptable*.
- [ ] Follow one segment. The catalogue opens filtered to exactly what the number said.
- [ ] Search for `samtools/sort`. Press **Adapt**.
- [ ] The work queue shows it in the AI lane, then queued behind it if something else is running.
- [ ] Open it. The stage track moves; the activity list gains rows; **nothing streams a thought**.
- [ ] When it reaches review: the graph draws each port, and a port the model proposed is
      outlined blue where one read from the source is solid.
- [ ] Click a proposed port. The panel shows the field, its reason, and the evidence it rests on.
- [ ] Open **Files**. `main.nf` says *copied unchanged* — an nf-core module is upstream's.

## 2. A PEGiS adaptation, by hand, with one revision and one question

PEGiS ships no Nextflow, so this is the case where the forge writes a module — the opposite
half of the last box above, and the reason both sources are walked.

- [ ] Adapt a PEGiS tool. Open it when it reaches review.
- [ ] **Files** now says `main.nf` was *written by the forge*.
- [ ] Ask one question in the chat rail. The turn appears **immediately**, marked queued.
- [ ] The answer cites something. Click the citation; the evidence opens.
- [ ] Press **Request changes**, say what is wrong, send it back. You stay on the page.
- [ ] A second revision arrives. The revision number goes up and the previous candidate is kept.
- [ ] Approve it. The dialog lists exactly the files that will be written, names you, and will
      not submit without a reason.

## 3. The registry actually took it

```bash
cd .run/registry && git log --oneline -1 && git status
```

- [ ] A commit on a `forge/…` branch, **authored by you** — not by `worker:<something>`.
- [ ] The tree is clean.
- [ ] `grep approved_by <the contract>` names you.

```bash
uv run mendel conformance --registry .run/registry
uv run mendel lint --registry .run/registry
```

- [ ] Both pass. A contract that lands and will not load is a publication that produced nothing.

## 4. A pipeline resolves through it

Write a goal that wants what the new contract produces, then:

```bash
uv run mendel build --goal <that goal> --registry .run/registry --out /tmp/walk
grep -A3 "<the new contract id>" /tmp/walk/pipeline.yml
```

- [ ] The step is there, with a `why:` naming why it was chosen.
- [ ] `uv run mendel build ... --gate stub` passes. Docker, ~900s cold — this is the narrowest
      gate that proves the emitted Nextflow runs, and it is the last thing the v1 criterion
      rests on.

## 5. The pages beside the drawings

**Reading annotations is not visual validation** — 2026-09-01 cost three rounds learning that.
`.design/_compare.html` puts an artboard and a screenshot in one viewport, which is what found
a translucent panel drawn opaque, an envelope at half width, and a squashed timeline.

```bash
uv run python .design/_prev.py --glob 'Forge*.dc.html'
```

- [ ] `/forge` beside `ForgeOverview`
- [ ] `/forge/catalogue` beside `ForgeCatalogue`
- [ ] `/forge/work` beside `ForgeWork`
- [ ] an adaptation mid-generation beside `ForgeAdaptation`
- [ ] one in review beside `ForgeReview`, `ForgeReviewCode` and `ForgeReviewParams`
- [ ] the request-changes dialog beside `ForgeReviewChanges`

Look for the four things a text comparison cannot see: **fill** (a panel that should be
translucent), **width** (something drawn at half its box), **chrome** (a header the drawing does
not have), and **height** (a band squashed to nothing).

---

## What this walk is allowed to find

Everything. The point of driving it by hand is that the suites are green and have been green
through four tasks — what they are blind to is appearance, the browser, and any seam that only
exists once two containers are running. Write down what you find; the journal entry is where it
goes.
