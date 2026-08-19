# Sources and drafting — Plan 3A phase 6

**Status:** written 2026-08-19, against the code phases 0–5 landed.
**Implements:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §3's phase 6 —
*discover a tool and draft it, without the CLI* — and §4.1's `/forge/sources`.
**Designs:** `docs/design/forge-review.md` §9 lists **Sources** under *Not designed*: "in the
navigation and undrawn". This spec draws it, so §3's rule is the authority rather than an
artboard — *a page earns its place by being a different kind of work, not a different subject*.

---

## 1. What phase 6 is for

Every phase so far works on drafts that a CLI created. Nothing in the interface can start one, so
the loop has a hole in the middle: a curator can answer, decide, browse and resolve drift in a
browser, and must drop to a terminal to make the thing they are about to answer questions about.

At the end you can see what each registered source can read, see which of those tools the registry
already has, and draft one — landing you in the queue with its questions open.

**What phase 6 is not:** no model fill, no landing from the browser (that is `forge land`, and it
stays there for now — §5), no second source adapter ([#65](https://github.com/comeni-project/Comeni-Labs/issues/65)).

---

## 2. What exists, and what does not

Measured by running it, 2026-08-19.

| Exists | Where |
|---|---|
| `ops.sources_() -> SourcesResult(names)` | `mendel_forge/ops.py` |
| `ops.discover(DiscoverRequest(source_root, source)) -> DiscoverResult(refs)` | `ops.py` |
| `ops.draft(DraftRequest(ref, name, …, version)) -> DraftResult` | `ops.py` |
| `mendel_forge.http` — `GET /sources`, `POST /discover`, `POST /drafts` | mounted at `/api/forge` |
| `Shell` renders **Sources** `aria-disabled` with the title *"phase 6"* | `Shell.tsx` |

```
discover over vendor/    0.00s    13 tools, one source (`nf-core`)
of those, in the registry already   10
NOT drafted, and draftable today     3   bedtools/sort, picard/markduplicates, samtools/faidx
```

| Does **not** exist | Consequence |
|---|---|
| any route the browser can call to discover or draft | §3.1 |
| any way to know a tool is *drafted* rather than *landed* | the screen would show a stale list |
| any refusal for drafting over an existing draft | §3.4 — it overwrites, silently |
| a version anything can derive | §3.3 |

---

## 3. Decisions

### 3.1 The frontend does not call the mounted forge transport, and `main.py`'s rule is stale

`main.py`'s docstring says the forge's app is **"mounted, never re-exposed route by route"**, and
that adding our own route would be "a third spelling of the same operation".

**Every phase since 2 has re-exposed forge operations**, and for a reason the docstring did not
anticipate: `ops.DiscoverRequest` carries `source_root: Path`, `DraftRequest` carries three paths.
A browser calling `POST /api/forge/discover` must therefore **choose filesystem paths on the
server** — which `settings.py`'s own docstring forbids in one line: *a second place that decides
where the registry lives is a second answer to that question.*

So `/api/questions/answer` wraps `ops.fill`, `/api/contracts/{id}/drift/accept` wraps
`ops.accept`, and phase 6 adds two more of the same shape. The rule these follow is not *never
re-expose*; it is:

> **A route re-exposes a forge operation to supply the paths, and adds nothing else.** No branch,
> no reshaping, no second answer to what a draft is.

The docstring is corrected to say that rather than left describing a rule the code stopped
following three phases ago — which is A33's shape, and it is a *sentence* rather than a guard, so
it drifts exactly the way that finding predicts.

### 3.2 The mount is removed

`app.mount("/api/forge", forge_app)` puts an **unauthenticated** app on the served origin that
takes arbitrary `registry_root`, `source_root` and `workspace_root` from a request body — and
`POST /api/forge/drafts/land` runs `git commit` in whatever path it is handed.

That was harmless while `mendel_forge.http` was a library object with a test; mounting it on an
origin a browser reaches is a different thing. And it is **not load-bearing**: nothing in
`frontend/src` calls it, the mounted routes are not in the parent's OpenAPI document, so the
generated client has no types for them and cannot have.

Three facts, and together they decide it: nothing uses it, nothing can type it, and it accepts
paths. **It is removed, and `mendel_forge.http` keeps existing** — it is still a complete
transport with its own tests, still mountable by an operator who wants it, and still what
`test_http.py` compares against the CLI. What changes is that this app stops mounting it by
default.

**This is a security decision and it is stated as one** rather than folded into a refactor.
Nothing else in this repository has had one, and the honest version is: no boundary was crossed,
because nothing was deployed — but an unauthenticated arbitrary-path git commit is the kind of
thing that is much cheaper to remove now than to find later.

### 3.3 The version is asked for, never derived

`DraftRequest.version` defaults to `"0.0.0"` with the comment *"a default that is obviously wrong
beats one that looks right"*, and phase 6 does not improve on that by guessing.

**Measured, and this is why:**

| tool | container | contract |
|---|---|---|
| `nf-core/multiqc` | `multiqc:1.35--c17fb…` | `@1.35` ✓ |
| `nf-core/fastqc` | `fastqc:0.12.1--hdfd…` | `@0.12.1` ✓ |
| `nf-core/samtools/index` | `htslib_samtools:**1.24**--d697…` | `@**1.21.0**` ✗ |
| `nf-core/star/align` | `htslib_samtools_star_gawk:ae438e9a604351a4` | `@1.11.0` — **no tag at all** |
| `nf-core/hisat2/align` | `hisat2_samtools:6ca0ef72b662d5c8` | `@2.2.2` — **no tag at all** |

Two of the thirteen vendored tools have a container with no version in it, and one shipped
contract disagrees with the tag it does have. A field prefilled from the container would be right
about two thirds of the time and would look authoritative every time.

**What the form does instead** is show the container string beside the version field, labelled as
what it is — *the container this module declares* — and let the person read a version out of it or
not. That is evidence, which is what every other answer in this interface is given.

**The stakes are lower than they look, and that is worth stating**: `docs/reference/cli.md` says
contracts are pinned **by digest, not version** — "a contract can be edited without its version
changing". The version is a label a human reads, not a pin anything resolves.

### 3.4 Drafting over an existing draft is refused

`Workspace.save` does `mkdir(exist_ok=True)` then `write_text`. **Drafting onto a name that
already exists destroys it silently** — every answer, every proposal, every decision.

That is survivable in a CLI a person types deliberately. In a form it is one careless click, and
the thing destroyed is the most expensive artifact in the system: a human's answers.

`MF0010` refuses a draft whose name is taken, naming the drafts that exist. Overwriting is not
offered as a flag, because the recovery is *pick another name* and the caller always can.

**This is a defect in `ops.draft` rather than in the screen**, so it is fixed there and the CLI
gets it too. Phase 6 found it; it has been true since forge phase 1.

### 3.5 The list says what has been done with each tool, and that is the whole screen

A bare list of thirteen names is a directory listing. What makes it work is the second column:

| state | means |
|---|---|
| `landed` | a contract with this module key is in the registry |
| `drafted` | a draft in the workspace is for this tool, and it is not landed |
| `undrafted` | neither — this is what you can start |

Sorted **undrafted first**, the same worst-first argument as the queue and the contracts list:
what needs doing goes at the top. `?state=` filters it, in the URL, like every other view.

**`drafted` is derived by reading each draft's `filled["id"]`**, not by matching names — a draft
called `mydraft` for `nf-core:samtools/faidx` must show against that tool, and a name is a label
the person chose.

### 3.6 One screen, and drafting happens on it

By §3's rule, drafting is not a different **kind** of work from browsing what can be drafted — it
is the action that list exists to offer. So there is no `/forge/sources/new`: the row expands into
a name, a version and a button.

The nav's **Sources** entry stops being `aria-disabled`, and that is the fourth and last of the
three destinations to become real.

---

## 4. The surface

### 4.1 API

| Method | Path | operationId | Over |
|---|---|---|---|
| `GET` | `/api/sources` | `listSources` | `ops.sources_` + `ops.discover` + registry + workspace |
| `POST` | `/api/sources/draft` | `draftTool` | `ops.draft`, paths from settings |

One `GET`, because *what can be read* and *what has been done with it* are one question a curator
asks once. Splitting them would make the screen fire two requests to render one list.

The draft body is `{ref, name, version}` — no paths. The response is `DraftResult`, so the screen
can send the person straight to the queue knowing how many questions it opened.

### 4.2 Routes

```
/forge/sources                       DESTINATION — what can be read
  ?state=undrafted|drafted|landed    filter
```

Which is [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §4.1 unchanged, plus the
filter every other destination already has.

### 4.3 What a row carries

The `ToolRef` (`nf-core:samtools/faidx`), its state, and — where it is `landed` or `drafted` — a
link to the contract or to the queue filtered to that draft. An `undrafted` row expands to the
form in §3.6.

---

## 5. What this does not settle

**Landing stays in the CLI.** `forge land` needs a registry checkout it can commit to, and phase
5 already showed what that means in a browser: the default configuration is a submodule at a
detached HEAD and refuses. Landing from the interface is worth doing and it is not this phase —
`POST /api/sources/draft` opens work, and the queue closes it.

**Nothing knows the tool's real version**, and §3.3 is the honest version of that rather than a
fix. A source adapter that reads a version out of `meta.yml` or a `versions.yml` would change
this, and no adapter does today.

**One source.** `nf-core` is the only registered adapter, so the source facet has one value and
the screen must not imply a chooser that does nothing. The `Source` protocol has had two
implementations since day one (`tests/opaque_source.py`), so the shape is right; the second real
one is [#65](https://github.com/comeni-project/Comeni-Labs/issues/65).

**Discovery is a directory walk**, 0.00s over thirteen vendored modules. A source that lists a
container registry is a network call with a completely different cost, and nothing here is
designed for it — which is what makes #65 a phase of its own rather than an adapter drop-in.
