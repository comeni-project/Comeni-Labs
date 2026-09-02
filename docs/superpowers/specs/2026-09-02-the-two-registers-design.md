# The two registers — a design for the documentation

**Date:** 2026-09-02
**Status:** approved, not yet implemented
**Supersedes:** the `guides/` · `reference/` · `concepts/` · `design/` split

---

## 1. The problem

The documentation was trying to do two jobs at once — **describe the code** and **teach
somebody to use the platform** — and those jobs clash. A page serving both hedges between two
readers and commits to neither, which is why the surviving pages read mechanically. The opener
of `guides/running-the-stack.md` is the specimen:

> Everything the command line does, plus the parts it cannot: a visual pipeline builder, a live
> run monitor, and a review queue for new tools. This brings it all up on your machine.

Two sentences, two readers, no purpose stated. A reader cannot tell what the page is *for*.

There is a second failure underneath it. **The docs lost the mission.** They lead with the
command line, with Mendel, with mechanism — the exact framing error `CLAUDE.md` names at the
top — because the CLI is what was easiest to describe accurately. Accuracy was never the
problem; orphaning was. Every page was true and no page said why it existed.

Most of the old documentation was deleted for this reason. Twenty-one pages survive, kept
because they hold facts that would otherwise be lost, **not because they are the right shape**.

### 1.1 Two measurable symptoms

- **`make links` passes while a dozen links lie.** Five links are genuinely broken (all to the
  deleted `concepts/privacy-and-egress.md`). Roughly a dozen more were repointed at the wrong
  live file to make the checker green: `README.md` sends *Watching a run* to
  `running-the-stack.md`; `guides/README.md` sends `driving-the-forge.md` to
  `writing-a-contract.md`. The checker cannot tell a resolved link from a truthful one.
- **Two pages advertise files that do not exist** — `measuring-your-data.md` appears in
  `docs/README.md` and `guides/README.md` as plain text with no link.

---

## 2. The product, as it will be

Written down here because the documentation is being written *to this*, and a fresh session
needs it in one place. Recorded from the operator, 2026-09-02.

**Current state: pre-MVP.** There is no AI anywhere in the product. The forge exists as
mostly-dead deprecated code awaiting its own rework. The repository is being reorganised —
tests, documentation, layout — which is the work this spec belongs to.

### 2.1 The analysis loop

**Build.** You assemble a pipeline by hand on the canvas, **or** you tell an agent what you
have and what you want. Two doors into one builder; the agent is the innovation.

**The agent** has memory that grows over time. It drives the API rather than writing code, and
it sets down the YAML save file — it does not author the pipeline itself. It works the
four-tier ladder, and when it meets a new tier-3 pattern it can decide a rule and propose it
into the bank.

**Run.** Once the parameters are filled, the pipeline is handed to Wiener and run via Nextflow:
locally, on Kubernetes, or on a cloud service — AWS first.

**Watch.** The run streams telemetry back to the platform. Wiener's agent reads the warnings,
the errors and the console throughput, and monitors the run. When something breaks it finds a
reason, writes a short report, and **proposes a fix** — which a human accepts or declines, and
re-runs.

### 2.2 The registry loop

**Sources** of tool information — nf-core today, pegi3s later (a live collaboration, so it must
be supported). Each source has a **deterministic extractor** that pulls out everything provable
about a tool from its own documentation. **An AI fills the gaps** to complete a new module.
**A human assists throughout**, in a dedicated visual surface where they can edit, review
changes, and maintain the registry and its drift against upstream over time.

**This is core, not an appendix. With no tools, the rest does not exist.**

### 2.3 The unity — one idea, applied twice

| | proves what it can from | hands back | filled by | approved by |
|---|---|---|---|---|
| **builder** | declared data | typed **ambiguities** | agent or person | a human |
| **forge** | a tool's own source | typed **holes** | agent or person | a human |

This is not an analogy imposed by the documentation. `comeni_core/review/` is the shared type:
`Question`, with `Hole` and `Ambiguity` as its two sides. The forge asks about a contract it is
drafting; the resolver asks about a pipeline it is building.

**The consequence for the docs is one sentence that covers the whole product:**

> Nothing here is produced by a model unsupervised. Everything is derived where it can be
> proven, and where it cannot, the gap is typed, addressed, bounded to a set of legal answers,
> and shown to a person.

That sentence, or a descendant of it, belongs on the front page and at the head of both
`Start here` and `Registry`. It is what nothing else does.

---

## 3. The two registers

The core mechanism of this design. Every page is written in exactly one of two registers, and
the register is a property of the **book**, not of the author's mood.

### 3.1 Vision register — `Start here`, `Handbook`, `Registry`

Written **in the present tense, to the vision of §2**, with a marker wherever reality has not
caught up.

Writing user documentation for what does not exist is deliberate and is the operator's
instruction. The justification: it makes the documentation the **specification the product is
built against**, and it stops the docs re-acquiring a CLI shape simply because the CLI is what
currently works. The risk — that this reproduces the false-claim problem cleaned up on
2026-09-02 — is contained by §3.3, which makes the marker discipline enforceable by a command
rather than by remembering.

### 3.2 Accuracy register — `Internals`

Written **to what exists**. No vision markers except where a design record is explicitly
describing future work.

**But it must not lose the mission**, because that is where the documentation went wrong. The
mechanism is one line at the top of every Internals page naming which part of §2 it serves:

```markdown
> *Serves: **build**. This is the engine that turns a goal into a pipeline.*
```

Not provenance, not history, not an argument — one line, and it is checked (§3.4).

### 3.3 The marker convention

A Material admonition with a fixed, greppable first line:

```markdown
!!! warning "Not built yet"
    The agent does not exist. Today you assemble the pipeline on the canvas by hand.
    Tracked in Plan 3.
```

Three rules:

1. The title string is exactly `Not built yet`. `grep -rn "Not built yet" docs/` is the removal
   list.
2. The body says **what happens today instead**. A marker that only says something is missing
   leaves the reader stranded.
3. The body names a plan or an issue. A marker naming nothing cannot be scheduled or retired.

### 3.4 `make docs-status` — the enforcement

A new script, `tools/docs_status.py`, and a `make docs-status` target. It:

- scans `docs/` for every `Not built yet` marker
- **fails** on a marker whose body names no plan or issue
- **fails** on an Internals page with no `Serves:` line, and on one naming a step that is not in
  the loop vocabulary
- generates `docs/status.md` — one page listing every marker, its page, and the plan it names

`docs/status.md` is generated and checked in CI, the same shape as
`docs/reference/diagnostics.md`. This is the load-bearing part of the design: it means *what is
vision and what is real* is answerable by running a command, rather than asserted in prose that
goes stale. It is the same instinct as `make residue`, `len(DeclaredKind)` and the diagnostics
guard, and it exists because this repository has been burned repeatedly by counts and claims
maintained by hand.

`make docs-status` joins `make check`.

---

## 4. The shelf

One site, four books as top-level tabs. Search runs across all four.

| Tab | Reader | Register |
|---|---|---|
| **Start here** | you have data and a question | vision |
| **Handbook** | you own the analysis | vision |
| **Registry** | you keep the tools | vision |
| **Internals** | you work on Comeni Labs | accuracy |

### 4.1 Why four, and why these

The old split — `guides/` `reference/` `concepts/` `design/` — was Diátaxis, and Diátaxis is
not wrong. It sorts by **what the reader is doing** (learn, do, look up, understand). What was
missing is the prior axis: **who the reader is**. A `reference/` page and a `guides/` page can
share a reader; a bench researcher and a contributor cannot share a page.

So the tabs sort by reader, and Diátaxis survives *inside* each book where it earns its place —
which is why `Handbook` has a Reference section and `Start here` does not.

`Registry` is a fourth book rather than a section of `Handbook` for two reasons. It has its own
reader — a curator or domain expert, quite possibly at a collaborating institution rather than
in the lab running analyses. And it is the loop everything else depends on: making it a
subsection would put the product's foundation three clicks down a sidebar.

`Internals` is a book rather than plain repository markdown so that it shares the search index.
A contributor searching *"why is this value tier 2"* should find the concept page and the
resolver's implementation notes in one result list.

### 4.2 Spines

**Start here** — seven pages, short, browser-first. This is the product's argument.

1. What this is — the §2.3 sentence, in a researcher's words
2. Bring it up — Docker, `make dev`, a URL. Three sentences
3. Describe an analysis — by hand on the canvas, or by asking the agent
4. Read what it decided — the reasons, the citations, measured versus asserted
5. Answer what it would not guess — the questions it hands back
6. Run it — local, Kubernetes, cloud
7. When it breaks — the report, the proposed fix, accept or decline

**Handbook** — the same loop at depth, plus understanding and reference.

- The loop in depth
- Running: local, Kubernetes, cloud
- Watching a run
- Diagnosing a failure
- **Understanding what it decided** — the four tiers · how tools get chosen · measuring your
  data · what leaves your machine
- Reference — CLI, diagnostics, glossary, the pipeline and goal schemas

The *Understanding* section is Diátaxis' explanation quadrant, and it earns its place here
because its reader is the one who owns the analysis. A bench researcher meets the tiers as
colours on a screen in `Start here`; the person who has to defend the pipeline reads this.

**Registry** — the forge loop, and the hand-authoring floor beneath it.

- Sources — what a source is, nf-core, pegi3s
- Drafting a tool from a source
- Filling what could not be derived
- Reviewing and landing
- Writing a contract by hand
- Making a choice depend on your data
- Your lab's own layer
- Tool drift over time

The two surviving hand-authoring guides land here, and they are load-bearing rather than
legacy: **hand-authoring is the deterministic floor the forge's output must be legible as.** A
reader who understands a hand-written contract can review a drafted one. That is why they were
worth keeping.

**Internals** — accuracy register.

- Architecture
- The pure packages and their guards
- The four doors
- The tier ladder as implemented
- The registry stack
- Testing
- Releasing
- Design records · pointer to `notes/`

---

## 5. Page shape

Applied from the research (§9). Every page, both registers:

```markdown
---
title: Making a choice depend on your data
description: One sentence. Shown in search results and on section index cards.
---

# Making a choice depend on your data

<!-- The purpose. One or two sentences on what the reader gets, never the mechanism. -->

Your lab knows that reads under 70bp should not go to STAR. Right now that knowledge
lives in somebody's head. A rule is how it becomes something the platform applies for
you, with your citation attached, every time it fits.

<!-- What the page contains. Nextflow's pattern, and it is the single highest-value
     borrowing in this research. -->

This page covers:

- what a rule can decide
- writing one, and what it may say
- what happens when it fires, and when it misses
```

Three rules, each written because the current pages break it:

1. **Purpose before mechanism.** State what the reader gets. `writing-a-rule.md` opens well and
   is the model; `running-the-stack.md` opens with a list of components and is the anti-model.
   The operator's note: *each file should serve a purpose and gradually build to it.*
2. **Say what the page contains.** A bulleted contract, in the reader's terms.
3. **No page explains its own information architecture.** Already `CLAUDE.md` rule 2. Section
   index pages say what is in the section; they do not justify the section's existence.

### 5.1 Splitting hedged pages

Where a topic serves two books it becomes **two pages at different depths**, never one hedged
page. The worked example, and the fix for the specimen in §1:

- **Start here → Bring it up.** "You need Docker. Run `make dev`. Open
  <http://localhost:5173>." Three sentences.
- **Handbook → The stack.** The eleven containers, what runs where, the Docker socket warning,
  the same-absolute-path bind mount trap.

Neither hedges, so neither reads mechanically.

---

## 6. Tooling

**Material for MkDocs.** Chosen over mdBook, which was the literal answer to *"a Rust-style
wiki that is local"*.

| | mdBook | Material for MkDocs |
|---|---|---|
| local, no hosting | yes | yes |
| offline from `file://` with search | partial | yes, `offline` plugin, free |
| top-level tabs (four books, one site) | **no** — one flat sidebar | yes, `navigation.tabs`, free |
| toolchain | Rust binary | Python, installs via `uv` |
| Mermaid | plugin | built in |

mdBook would give four isolated books. The tabs are what make it one seamless wiki, which is the
requirement.

**Setup:**

- source stays in `docs/`; `mkdocs.yml` at the repository root
- a `docs` dependency group in `pyproject.toml`, so `uv sync --group docs` is the whole install
- `make wiki` builds to `site/` (gitignored); `make wiki-serve` runs it locally
- features: `navigation.tabs`, `navigation.sections`, `navigation.indexes`, `content.code.copy`
- plugins: `search`, `offline`
- publishing to GitHub Pages later is the same `mkdocs build` with nothing changed

### 6.1 Diagrams

**Yes, Mermaid, and sparingly.** Material renders it natively.

The evidence for it is already in the repository: the backward-chaining tree in
`concepts/routing.md` is the clearest thing in the entire documentation set, and it is a
diagram. Nextflow's diagrams work because they are rare.

Budget for the first pass — four:

1. **The loop** (`Start here → what this is`) — describe → build → run → watch, with the fix
   proposal closing it
2. **The unity** (front page) — the §2.3 table as a diagram: two loops, one `Question` type
3. **The tier ladder** (`Handbook`) — where a value exits, and what each exit commits you to
4. **The stack** (`Handbook → the stack`) — the containers, and the browser as courier between
   two services that do not know about each other

Keep the ASCII backward-chaining tree as ASCII. It works.

---

## 7. Disposition of the twenty-one surviving pages

| Current | Goes to | Treatment |
|---|---|---|
| `docs/README.md` | `docs/index.md` | rewrite — site front page, the §2.3 sentence, four book cards |
| `docs/tutorial.md` | `start/` (7 pages) | **rewrite as the platform loop.** Currently CLI-shaped end to end. Its content survives as the Handbook's CLI reference, not as the spine |
| `concepts/tiers.md` | `handbook/the-four-tiers.md` | keep, retone. Strong page. Add the ladder diagram |
| `concepts/routing.md` | `handbook/how-tools-get-chosen.md` | keep, retone. Keep the ASCII tree |
| `concepts/README.md` | — | delete; replaced by section index |
| `guides/running-the-stack.md` | **split** → `start/bring-it-up.md` + `handbook/the-stack.md` | the §5.1 worked example |
| `guides/writing-a-contract.md` | `registry/writing-a-contract.md` | keep, retone. Add purpose opener |
| `guides/writing-a-rule.md` | `registry/making-a-choice-depend-on-your-data.md` | keep, retone. Best current opener; needs *why a rule exists* first |
| `guides/registry-layers.md` | `registry/your-labs-own-layer.md` | keep, retone |
| `guides/releasing.md` | `internals/releasing.md` | **moves register.** Not a user guide — it is for whoever cuts a tag |
| `guides/README.md` | — | delete; replaced by section indexes |
| `reference/cli.md` | `handbook/reference/cli.md` | keep. **Demoted from spine to appendix** |
| `reference/pipeline-schema.md` | `handbook/reference/` | keep |
| `reference/goal-schema.md` | `handbook/reference/` | keep |
| `reference/diagnostics.md` | `handbook/reference/` | keep — **generated**, see §7.1 |
| `reference/glossary.md` | `handbook/reference/` | keep — **guarded against the frontend**, see §7.1 |
| `reference/contract-schema.md` | `registry/reference/` | keep — follows its authoring guide |
| `reference/rule-schema.md` | `registry/reference/` | keep |
| `reference/vocabulary-schema.md` | `registry/reference/` | keep |
| `reference/measurement-schema.md` | `registry/reference/` | keep |
| `reference/README.md` | — | delete; replaced by section indexes |

`docs/notes/` is untouched, stays raw markdown on GitHub, is excluded from the built site, and
is linked once from Internals. It is provenance, not documentation, and it is already excluded
from `make links`.

`docs/superpowers/` — including this spec — is excluded from the site for the same reason. Both
exclusions go in `mkdocs.yml` under `exclude_docs`, so a file that is not in a book is not
silently published.

### 7.1 Constraints any move must respect

Three pages are held to the code by existing checks. Moving them without updating the checkers
breaks CI.

- **`reference/diagnostics.md` is generated** from `comeni_core/diagnostics.yml` by
  `tools/generate_diagnostics_doc.py`. Update the output path.
- **The five schema pages are held to their Pydantic models** by `tools/check_reference.py`,
  which fails on a documented field the model lacks, a model field the page misses, or a CLI
  verb nobody wrote down. Update its paths. **Do not weaken it** — it was written on 2026-09-02
  because all five pages disagreed with their models.
- **`reference/glossary.md` is held to the frontend** — the eight terms are rendered through
  `<Term>` and a test asserts the two lists match in both directions.

`tools/check_links.py` needs its roots updated, and §8 hardens it.

---

## 8. Fixing the link rot

`make links` currently passes over a documentation set with a dozen dishonest links, because a
dead link was repointed at whatever live file was nearest.

Three changes, in the migration:

1. Fix the five genuinely broken links — all to `concepts/privacy-and-egress.md`, which was
   deleted. **It needs rewriting**, see §10; the SECURITY.md link makes it not optional.
2. Repair every repointed link so the destination matches the link text. Where the destination
   does not exist yet, the link is removed and the text becomes a `Not built yet` marker.
3. **MkDocs' own strict mode replaces most of the checker.** `mkdocs build --strict` fails on
   any unresolved internal link, and it understands the nav, which `check_links.py` does not.
   Keep `check_links.py` for `.github/`, `.design/` and the root, which are outside the site.

---

## 9. What the research established

Three projects, three models, and the corrections they force on the assumptions this work
started from.

**Nextflow is not split.** `docs/` in the nextflow repository *is* docs.seqera.io/nextflow —
the same `.mdx` files, built by Seqera's site generator. One source of truth. What is split is
the audience *inside* the folder: `reference/`, `guides/`, `tutorials/`, `developer/`,
`migrations/`, plus roughly thirty-five topic pages at the root. Every page carries `title` and
`description` frontmatter and opens by telling the reader what they will get. **This is the
model this design follows.**

**Hono is split.** `honojs/hono` holds almost no documentation — CONTRIBUTING, CODE_OF_CONDUCT,
MIGRATION. hono.dev is a separate repository, `honojs/website`, built with VitePress. Rejected:
a second repository for documentation is overhead this project does not need, and it would put
the docs further from the code that must not drift from them.

**Rust is the shelf**, and it is where the four-book structure comes from. Not one site — a
shelf of books, each with a declared audience, all built with mdBook: The Book (learn), Rust by
Example (do), The Reference (normative), std docs (generated), the Error Index (one entry per
diagnostic), the rustc dev guide (contributors). The mapping is close enough to be useful:

| Rust | Here |
|---|---|
| The Book | `Start here` |
| The Reference | `Handbook → Reference`, `Registry → Reference` |
| **Error Index** | **`reference/diagnostics.md` — already exactly this, already generated** |
| rustc dev guide | `Internals` |
| std API docs | nothing yet; `check_reference.py` is a half-step toward it |

**What makes Rust's documentation good is not tone.** It is that each book knows who is holding
it, so no page has to hedge. That is the finding this whole design rests on.

---

## 10. What is missing and must be written

Beyond retoning what survives. Ordered by how badly it is needed.

| Page | Why | Register |
|---|---|---|
| **What leaves your machine** | `concepts/privacy-and-egress.md` was deleted and **five links point at it, including `.github/SECURITY.md`**. The four doors, the typed payloads, and why *anonymised* is never the claim. `CLAUDE.md` invariants 14 and 15 are the source | vision, but every claim accurate |
| **Describe an analysis** | The centre of the product and there is no page for it. Both doors: the canvas, and the agent | vision, marked |
| **When it breaks** | The fix-proposal loop — report, propose, accept or decline, re-run. Nothing describes it | vision, marked |
| **Sources** | What a source is, nf-core, pegi3s. The registry loop has no front page | vision, marked |
| **Drafting a tool from a source** | The forge loop end to end. `driving-the-forge.md` was deleted | vision, marked |
| **Measuring your data** | Advertised in two index pages with no link. Turning *I think the reads are 150bp* into a measured fact — and it is what makes tier 3 mean anything | vision |
| **Running on Kubernetes / AWS** | Named in the vision, profiles emitted but not launched | vision, marked |
| **Answer what it would not guess** | Tier 4 from the user's side. `concepts/tiers.md` explains the ladder but never what a person *does* | vision |
| **Tool drift over time** | The maintenance half of the registry loop | vision, marked |
| **The pure packages and their guards** | Invariant 1, the two partial guards and why the claim is their union. Only in `CLAUDE.md` | accuracy |
| **Architecture** | `ARCHITECTURE.md` moves in and gains a `Serves:` line | accuracy |

---

## 11. Non-goals

- **Not rewriting `docs/notes/`.** Provenance, append-only, out of the site.
- **Not a second repository.** The Hono model is rejected; §9.
- **Not publishing anything.** Local-only is the requirement. GitHub Pages remains available
  later at no change to the source.
- **Not weakening `check_reference.py` or the glossary guard** to make a move easier; §7.1.
- **Not documenting the current forge implementation as if it were the vision.** The `Registry`
  book describes the forge loop in the vision register; `Internals` records that the current
  code is deprecated pending rework and that `make forge-rework` is the list.

---

## 12. Risks

**Vision-register pages become false claims.** The whole design leans on §3.4. If
`make docs-status` is not built, or is built and not put in `make check`, this reproduces the
problem the 2026-09-02 rework was called in to fix. **Build the checker in the same change as
the first marked page.**

**Documenting screens nobody has walked.** The current state notes record that nobody has looked
at the builder since Plan 5B phase 1, that W2's browser checkpoints are owed, and that the scope
override has no control on the canvas. Writing `Start here` and `Handbook` from routes and React
source will produce pages that describe screens which do not behave as written — the failure the
run-page journal entry names twice: *reading finds wrong strings; it does not find wrong
pictures.*

**Mitigation, and it is not optional: the platform-facing pages are written while driving the
platform in a browser.** Expect this to find product defects. That is a cost and a benefit, and
it should be budgeted as both.

**Four books is more surface than one.** Each additional book is a sidebar somebody must keep
true. Accepted, because the alternative — hedged pages — is the defect being fixed.

---

## 13. Order of work

Not an implementation plan; that is the next artifact.

1. **Scaffolding.** `mkdocs.yml`, the `docs` dependency group, `make wiki` / `make wiki-serve`,
   the four empty books with index pages. Nothing moves yet.
2. **`tools/docs_status.py` and `make docs-status`**, in `make check`. Before any marked page
   exists — §12.
3. **Move and retone what survives.** The §7 table, respecting §7.1. Fix the links, §8.
4. **Split `running-the-stack.md`**, the §5.1 worked example, as the first page written to the
   new shape.
5. **Write the missing pages**, §10 order — *What leaves your machine* first, because
   `.github/SECURITY.md` points at nothing.
6. **Walk the platform in a browser** and correct every vision-register page against what the
   screens actually do. §12.
7. **Diagrams**, §6.1, last — a diagram of a page that is still moving is drawn twice.
