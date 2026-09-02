# Browsing contracts — Plan 3A phase 4

**Status:** written 2026-08-18, against the code phases 0–3 landed.
**Implements:** [`docs/design/forge-review.md`](../../design/forge-review.md) §7's first two
paragraphs — the contracts list and the module page. **Drift is phase 5** and this spec
deliberately stops short of it.
**Extends:** [`2026-08-18-the-interface.md`](2026-08-18-the-interface.md) §4.1c, which names the
claims an implementation can quietly drop here.

---

## 1. What phase 4 is for

Phases 0–3 are all about work that is *open*. Nothing in the interface shows what has **landed**,
and the forge maintains as well as creates — a curator needs to read a contract they approved
last month against the module it describes.

At the end of phase 4 you can browse every contract in the registry, filter by how it stands
against its source, and open one to read it beside the module — including the two facts the
design says nothing else surfaces.

**What phase 4 is not:** no drift screen, no accepting a diff, no editing. Read-only stays
read-only.

---

## 2. What exists, and what does not

Checked, not remembered.

| Exists | Where |
|---|---|
| `ops.check(CheckRequest) -> CheckResult(checked, skipped, drift)` | `mendel_forge/ops.py:452` |
| `CheckResult.skipped` is a **list of contract ids**, not a count | measured |
| `Drift(contract_id, field, registry_says, source_says)` | `ops.py:446` |
| `ModuleSpec.parse(main_nf) -> ModuleSpec` with `.emits: list[str]` | `mendel_compiler/modulespec.py:107` |
| `conformance.module_path(contract, module_root)` | `conformance.py:70` |
| `rules.decisions[].decides.of` — the **role** a tier-3 rule targets | measured |
| `digest_of_directory(path) -> Digest` | `comeni_core/artifact/digest.py:86` |
| `registry.all()`, `contract.consumes/produces/roles/container/provenance` | measured |

| Does **not** exist | Consequence |
|---|---|
| per-contract drift status in the database | `source_check` holds counts only |
| any digest on `Layers` | the cache key must be computed, not read |
| anything storing pipelines | *"how many pipelines pin it"* cannot be answered |
| a contracts route or page | phase 4 is all of it |

**Measured:** `ops.check` against this registry takes **0.40s for 12 contracts**, reporting
`checked=10, skipped=2, drift=0`. The two skipped are `comeni/` contracts with no adapter — the
`unverifiable` facet is non-zero on day one, exactly as slice 1 discovered.

---

## 3. Decisions

### 3.1 Drift status comes from `ops.check` per request, cached on the registry's digest

**Decided by the operator, 2026-08-18.**

```
GET /api/contracts  ->  ops.check(...)  ->  cached under digest_of_directory(registry_root)
```

0.40s cold, free warm, and a changed registry invalidates the cache by changing its digest. No
new table, and no page that can show yesterday's answer.

**The limit is stated rather than discovered:** at the 5,800 contracts the design says this page
must survive, the cold path is roughly three minutes. That is the first thing to break, it is
written in the journal, and the fix when it matters is the third table this decision declined —
not a smaller check.

**The digest is computed, not read.** `Layers` carries no digest; `digest_of_directory` over the
registry root is what `declared_entries()` already defines a layer to be.

### 3.2 `unverifiable` is a facet, never folded into `matching`

`CheckResult.skipped` names the contracts nothing could re-read. Slice 1 got this wrong once —
12 contracts, 10 checked, and the strip claimed 12 matched — and `CheckResult.skipped`'s own
docstring is why: *a contract nothing checks looks exactly like a contract that agrees*.

Three statuses, and every contract has exactly one:

```
drifted       in CheckResult.drift
unverifiable  in CheckResult.skipped
matching      neither
```

`matching + drifted + unverifiable == total` is a test, not a comment.

### 3.3 The module page's right column ships three of four, and says so

**Decided by the operator, 2026-08-18.**

| Row | Derived from |
|---|---|
| tier-3 rules aiming at its roles | `rules.decisions` where `decides.of` is in `contract.roles` |
| what its inputs come from | contracts producing any `consumes[].type_id` |
| what its outputs feed | contracts consuming any `produces[].type_id` |
| what it competes with | contracts sharing a role, minus itself |
| ~~how many pipelines pin it~~ | **nothing stores pipelines** |

The fourth renders as *"pipeline pins — not tracked yet"* rather than being omitted. Dropping a
designed claim silently is what §4.1c of the interface spec warns against, and a reader comparing
the page to the design must not have to guess whether it was forgotten.

### 3.4 *"1 of 19 emit channels is declared"* is computed, with the reason beside it

`ModuleSpec.parse(path).emits` is the module's channels; `contract.produces[].name` is what the
contract declares. The design says this is one of two things nothing else surfaces.

**It is not a warning.** A contract may legitimately model a subset — `star/align` emits nineteen
and the spine needs one — so the number is stated with that reason attached, never coloured as a
fault. `notes/specs/2026-08-17-vocabulary-proposals.md` §6 records that nothing distinguishes
*considered and omitted* from *missed*, and this page is where that gap becomes visible rather
than where it gets closed.

**A module that cannot be read reports nothing**, not zero. Rendering *"0 of 0"* for a module
nobody opened is the same class of falsehood as folding `skipped` into `matching`.

**`unverifiable` and "no module file" are different things, and an earlier draft of this section
said they were the same.** Measured:

- `ops.check` skips a contract when **no registered source adapter** can re-fetch the tool's
  truth — the two `comeni/` contracts, because nothing knows how to read a `comeni/` tool.
- `emits_total` is `None` when **the vendored `main.nf` is absent**.

**Every contract in this registry has a vendored module**, so `emits_total` is never `None`
today and the `comeni/` contracts are unverifiable *with* a readable module. The two conditions
are independent and the page must not imply otherwise.

### 3.5 Read-only stays read-only, structurally

No `POST` on any contracts route. Design §7: contracts change through the queue or through drift
resolution, both of which record *why*; a free-text edit surface has nowhere to put the reason.

The router is created without a write verb so that adding one is a deliberate act, the same shape
as `routes/registry.py` from phase 2.

### 3.6 Per-field origin is **not** in phase 4

The design's left gutter stripe shows where each field came from. `contract.provenance` is
per-contract — `approved_by`, `approved_at` — and the forge's per-field `FilledValue.by/how/why`
lives on the **draft**, which is discarded once a contract lands.

**So the data does not exist for a landed contract**, and inventing a per-field origin from a
contract that has none would be a decorative lie. Saying so here is the point; closing it means
either landing the provenance into the contract file or keeping drafts after landing, and neither
is a phase 4 question.

---

## 4. The surface

### 4.1 API

| Method | Path | operationId | Over |
|---|---|---|---|
| `GET` | `/api/contracts` | `listContracts` | `registry.all()` + cached `ops.check` |
| `GET` | `/api/contracts/{id}` | `readContract` | one contract, its module, and what points at it |

`{id}` is a contract id like `nf-core/samtools/index@1.21.0` — it contains slashes, so the route
takes it as a **path parameter with `:path`** and the client encodes it.

### 4.2 Routes

```
/forge/contracts                    DESTINATION — the list
  ?against=drifted|matching|unverifiable
  ?role=<role>
  ?source=<namespace>
/forge/contracts/:id                one module, read only
```

Which is §4.1 of the interface spec unchanged. The nav's `Contracts` entry stops being
`aria-disabled`.

### 4.3 What the list carries

Per row: the contract id, its roles, its source namespace, and its status. Sorted **drifted
first**, then unverifiable, then matching — worst first, the same argument as the queue's
consequence order.

The facets are counts and they do not grow with the registry: three statuses, plus roles and
sources, both of which are small closed sets.

---

## 5. What this does not settle

**Whether the cache should be shared across workers.** It is per-process, so two API workers each
pay the cold cost once. At this size that is invisible; at scale it is an argument for the table
decision 3.1 declined.

**What a contract's per-field origin is.** §3.6 — the data is discarded at landing.

**Whether `unverifiable` should be actionable.** The two `comeni/` contracts have no source
adapter and never will through nf-core; the list marks them and offers nothing. Whether that is a
missing adapter (issue #65's pegi3s work) or a category of contract that is verified differently
is undecided.
