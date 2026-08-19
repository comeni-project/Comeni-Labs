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
| any mounted route in the parent's OpenAPI document | §3.2 — measured: 5 request bodies in the document, none of them the forge's |
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

### 3.2 The served surface is exactly the OpenAPI document, so the mount goes

**The principle first, because it decides this without appealing to security.** `main.py`'s own
description calls the schema *"the contract"* and names its two consumers: `frontend/src/api/` is
generated from it, and an agent driving Mendel reads it. **FastAPI does not merge a mounted
sub-app's schema into its parent**, so anything mounted is a surface that exists and is not in the
contract — invisible to the generated client, invisible to the agent, and typed by nothing.

> **The served surface is exactly the OpenAPI document.** A mount is a hole in the contract rather
> than a route in it.

That rule also rules out the tempting alternative. `include_router(forge_app.router, prefix=…)`
*would* put those routes in the document — and it is **worse**, because it would advertise, type
and document operations that take `registry_root`, `source_root` and `workspace_root`, inviting
exactly the use that should not exist.

**The two transports differ in who chooses the context, and that is the whole of it:**

| | context | audience |
|---|---|---|
| `mendel_forge.http` | supplied per call, in the request body | someone **embedding** the forge |
| `mendel-api` | supplied by `settings` | the **served installation** |

Neither is wrong. Mounting one inside the other is: the served app inherits a strictly more
permissive context model than its own configuration expresses. So a served route is
**`forge op + settings`**, which is exactly what phases 2–6 already do — what was missing is that
nobody named it as the rule, and a stale docstring said the opposite instead.

**And `mendel_forge/http/` goes with it, rather than being left unmounted.**

Keeping it was the first draft of this section — *"still a complete transport, still mountable by
an operator who wants it"* — and that is the sentence that keeps dead code alive. Measured after
the mount is removed:

| | |
|---|---|
| production consumers of `mendel_forge.http` | **zero** |
| files exercising it | its own two test files, and nothing else |
| `fastapi` in `mendel-forge` | an **optional extra**, `http = [...]`, that nothing installs |
| other users of that extra | none — not the root project, not CI, not the Makefile |

Every other reference in the repository is *prose*: docstrings comparing behaviour (*"a coded
refusal is a 422, as `mendel_forge.http` does it"*), and historical notes. Those describe a
convention that outlives the module.

**The contradiction is what settles it.** `docs/guides/driving-the-forge.md` documents mounting it,
with a worked example and no caveat. Removing the mount as unsafe while shipping a guide that tells
an operator to do exactly that is one product disagreeing with itself in two files. Either it is
safe to mount or it is not, and §3.2 has just answered that.

So it is deleted: the module, `tests/test_http.py`, `tests/test_http_model_fill.py`, the `http`
extra, and the guide's *"The same verbs over HTTP"* section. `mendel_forge.http`'s own docstring
named `mendel-api` as the thing that would mount it and own *who is calling, over what, and whether
they may* — that assumed auth would arrive alongside. It did not, and the module has no other
reader.

**What is genuinely lost, stated rather than glossed:** `test_http.py` held CLI-to-HTTP payload
parity — *two transports over one operation cannot drift*. With one transport that property is
vacuous, and it does **not** transfer to `mendel-api`, whose payloads are deliberately different
shapes: `AnswerRequest` is screen-shaped and `FillRequest` is CLI-shaped, which is the point of
§3.1's rule. What does transfer is *a route holds no logic*, and
`packages/mendel-api/tests/test_answer_route.py` already asserts it.

**If an embedding transport is ever wanted again**, the right shape is not this one: it is a
router whose bodies carry no paths and whose context arrives through `Depends`, so it can be
`include_router`-ed into a served app and appear in the document. That is a different module, and
nobody has asked for it.

**Two guards, and the second is the general form rather than a one-off:**

- no mounts on the served app — a mount is by construction outside the document
- no request body field named for a root or a path — the injection this rule exists to prevent

**The security reading is a consequence, not the argument**, and it is worth stating plainly
anyway: as mounted, `POST /api/forge/drafts/land` ran `git commit` in whatever path an
unauthenticated request named. Nothing was deployed and no boundary was crossed. It is much
cheaper to remove now than to find later.

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
