# Performance audit — 2026-08-19

**Why:** the operator asked how responsive the tool is, against a stated budget — *"max like half
a second for normal stuff doing in the browser. it's a tool, not a server"* — and asked whether
the codebase is "filled with excess worst-case-scenario stuff".

**Method:** measure, never reason. Every number here came from running the thing on this machine
against the shipped registry (39 declared files, 12 contracts) and against synthetic registries at
100, 500 and 2000 contracts. Profiles are `cProfile`; latencies are the best of three warm runs,
which is what a second visit feels like.

**Findings continue the audit numbering at A132.** Two guard rounds' worth of numbering (A1–A131)
precede them.

---

## The answer to the question that was asked

**No, the codebase is not filled with inefficiency.** The inefficiency is **concentrated in one
function that everything calls**, and that is much better news:

- the module page's whole graph — *what feeds this, what it feeds, what competes with it* —
  costs **1.9ms at 2000 contracts**
- `candidates.for_field`, the forge's per-hole lookup, costs **0.1ms**
- every route handler is a sync `def`, so FastAPI runs it in a threadpool and **nothing blocks
  the event loop**

One function is responsible for essentially all of it.

---

## Where the time goes today

Warm request latency, three drafts in the workspace:

| ms | endpoint |
|---|---|
| 0 | `/api/health` |
| **7** | `/api/questions` |
| **253** | `/api/contracts` |
| **249** | `/api/sources` |
| **253** | `/api/contracts/{id}` |
| **263** | `/api/contracts/{id}/drift` |
| **246** | `/api/registry/types/{id}` |

And the split:

```
layers.load           244.0 ms   <- every request redoes this
digest_of_directory     4.6 ms   <- the cache key costs almost nothing, today
```

`/api/questions` is 7ms for one reason: phase 4 happened to cache `ops.check` on the registry
digest, so the queue is the only screen that already avoids the reload.

---

## A132 — every registry-touching request re-loads the whole registry · **critical**

`contracts.listing`, `sources.catalogue`, `module_page.read`, `ops.drift` and the type lookup each
call `layers.load` fresh. Measured at **244ms**, and it is ~100% of each endpoint's time.

Nothing caches it. Phase 4 cached `ops.check`'s *result* on the digest and phase 5 reused that
cache, but the `Layers` object underneath — the thing that costs 244ms to build — is rebuilt per
request.

---

## A133 — each declared file is parsed 5.6 times per load · **critical**

```
declared files in the registry          39
YAML parses per layers.load()          217
=> each file is parsed 5.6× per load
```

`stack()` runs once per `DeclaredKind`, and for each kind it walks every file and calls
`declared_kind(p)` — which **parses the file** to read its `declares:` line. Five kinds means five
bucketing passes over every file, plus the real parse of the files that matched.

The bucketing is the same question every time and the answer cannot change within one load.

**A naive memo does not work**, and finding that out is worth recording: consumers *mutate* the
parsed dict — `declared_kind` pops `declares:` — so a shared cached value is consumed by its first
reader. The fix is structural (bucket once, hand each kind its bucket), not a `lru_cache`.

---

## A134 — libyaml is installed and unused · **critical**

```
libyaml (CSafeLoader) available: True
  pure-python SafeLoader   0.691 ms/file
  CSafeLoader              0.051 ms/file    ->  13.6× faster
```

`comeni_core.yaml_strict` subclasses `yaml.SafeLoader`, the pure-Python parser. `CSafeLoader` is
present on this machine and unused.

**Correctness, checked before proposing it** — this is a pure package and A31 lives here:

- the duplicate-key refusal **survives** the swap, with its line numbers intact:
  `'priority' twice, lines 2 and 3` under both loaders
- **53 declared files** — the registry, every vendored `meta.yml`, and `diagnostics.yml` — parse
  to **identical objects** under both
- digests are computed over file *bytes*, so nothing pinned moves

Measured effect on the whole load: **244ms → 49ms**, from changing one base class.

---

## A135 — 86% of the test suite is YAML parsing · **critical**

Profiling 341 tests (`mendel-api` + `mendel-forge`):

```
341 passed in 117.6s (with profiling overhead)
  yaml_strict.load    30,117 calls   101.5s cumulative   = 86% of the run
  layers.load            136 calls    99.7s cumulative
  modulespec.parse       385 calls     7.9s cumulative
```

The full fast suite is 1346 tests at ~3.5 minutes. If the ratio holds — and A132/A133/A134 say it
should — roughly **three of those three and a half minutes are YAML parsing**.

This is the finding with the widest blast radius: it is paid by every developer, on every run,
including CI.

---

## A136 — `mendel build` is 83% YAML parsing · **major**

The product path — the deterministic engine the whole thing rests on:

```
mendel build --goal examples/rnaseq-goal.yml       1.47s total
  yaml_strict.load   245 calls                     1.23s   = 83%
```

Same defect, same fix.

---

## A137 — the frontend is configured to distrust its own cache · **major**

```
frontend/src/main.tsx:9:  const client = new QueryClient();
```

No options, so TanStack Query's defaults apply: **`staleTime: 0`** and
**`refetchOnWindowFocus: true`**. Every navigation refetches, and every return to the browser tab
refetches every mounted query — at 250ms a request.

This is independent of the backend and it is the difference between navigation feeling instant and
feeling like a page load.

**It is safe to fix here in a way it would not be in most apps**, and that is worth saying: every
mutation since phase 2 invalidates precisely the queries it affects — `useAnswer`, `useAnswerAll`,
`usePropose`, `useDecide`, `useAccept`, `useDraft` — so the cache is already correct without
refetch-on-everything propping it up. The defaults are doing nothing but hiding latency behind
more latency.

---

## A138 — the cache key is O(files), so caching stops working at scale · **major**

```
files    digest_of_directory    a stat-only key
   39                 4.6ms              2.9ms
  139                17.0ms              9.5ms
  539                64.1ms             33.7ms
 2039               240.2ms            123.3ms
```

A digest-keyed cache is right at today's size — 4.6ms to skip 244ms is an excellent trade. At the
**5,800 contracts the design says these pages must survive**, the *key alone* is ~700ms, and a
cheaper stat-based key only halves it.

Recorded rather than fixed: the answer at that size is a key that is not O(files) — a watch, a
TTL, or the registry's git HEAD when it is a checkout — and nobody needs it yet. What matters is
that it is written down before somebody measures the cache and concludes caching does not work.

---

## A139 — loading is linear, and the constant is the problem · **moderate**

```
contracts   files   layers.load    ms/file
       12      39         244ms       6.25
      100     139        1056ms       7.60
      500     539        4297ms       7.97
     2000    2039       16363ms       8.02
```

**Linear, not quadratic** — which is the good news, and is why this is moderate rather than
critical. There is no algorithmic bomb; there is a constant of ~8ms per small YAML file, which
A133 and A134 attack directly.

At the design's 5,800 contracts, today's constant gives **~47 seconds per load**.

---

## A140 — the conformance sweep re-parses every module · **minor**

`ModuleSpec.parse` costs **5.9ms** per module, dominated by `_documented`, which parses
`meta.yml`. `ops.check` calls it once per contract: 71ms today, and ~34s at 5,800 contracts.

Mostly the same YAML defect, and it inherits A134's fix for free.

---

## A141 — the services are not the problem · **informational, and deliberately recorded**

The hypothesis behind this audit was that the codebase is full of worst-case inefficiency. It is
not, and recording the negative result matters as much as the positive ones:

| measured | cost |
|---|---|
| the module page's four relation scans, at 2000 contracts | **1.9ms** |
| `candidates.for_field` | **0.1ms** |
| `ops.discover` over the vendored tree | **1.5ms** |
| route handlers declared `async` (which would block the loop) | **none** |
| `queue.read` with three drafts | **6.6ms** |

`ops.show` does not load the registry despite taking a `registry_root`, which is why the queue is
fast. Every one of these is fine and none of them should be touched.

---

## A142 — `diagnostics.yml` is 95KB and parsed at import time · **major**

```python
# comeni_core/diagnostics.py:104
REGISTRY: dict[str, DiagnosticSpec] = _load()
```

Measured:

```
diagnostics.yml           95 KB
  pure-python SafeLoader   69.5 ms    <- paid at IMPORT
  CSafeLoader               4.8 ms    -> 15×
```

**Every CLI invocation pays it, every test process pays it, every worker start pays it.** The
`mendel --help` floor is **350ms** on this machine, and a fifth of it is parsing a diagnostics
catalogue to print a usage string.

A134's one-line fix takes it to 4.8ms without moving the load off import — which is the right
order, because `REGISTRY` being eager is what makes an undeclared code unrepresentable rather
than a lazy failure, and that guarantee is worth more than the remaining 4.8ms.

---

## A143 — after the YAML fixes, the next wall is the same structural defect in the filesystem · **moderate**

Profiling the load **with A133 and A134 applied**, the remaining ~23ms is dominated by `pathlib`:

```
29,600 Path.__init__      over 10 loads   =  ~2,960 Path objects per load, for 39 files
 3,360 Path.walk
 5,900 _select_from
```

`stack()` runs once per `DeclaredKind`, so it **re-walks the layer 5–6 times per load** — the same
scan-per-kind that A133 is about, showing up in the directory traversal rather than in the parse.

This is recorded as its own finding only so the fix is not declared complete when the parse count
drops: **bucketing once fixes both**, and a fix that memoises the parse without collapsing the
walk leaves this behind.

---

## A144 — caching a `Layers` is cheap, which is what makes A132 safe · **informational**

```
   12 contracts    retained  0.2 MB
 2000 contracts    retained 10.6 MB   (peak 16.0 MB)
```

Roughly 5KB per contract, so the design's 5,800 is ~30MB held. A132 proposes keeping one of these
per registry state; on memory grounds that is free, and it is measured here rather than assumed
because "cache the whole registry" is exactly the sentence that deserves a number under it.

**One caveat, not measured:** `lru_cache` offers no single-flight, so two concurrent cold requests
both pay the full load. At 244ms that is a real thundering herd; after the fixes it is ~5ms and
stops mattering.

---

## A145 — routing does not degrade at scale; loading does · **informational**

```
mendel build, 12-contract registry     1.47 s
mendel build, 500-contract registry    5.09 s   of which ~4.3 s is layers.load
```

The synthetic 500 all produce the same type, so `producers_of` returns 500 candidates and the
router has to order every one of them — the worst shape available. It costs **under a second**.

The second half of A141's negative result: the resolver is not where the time goes, at any size
tested.

---

## What the fixes are worth — measured, not projected

| | `layers.load` |
|---|---|
| today | **244 ms** |
| A134 alone — `CSafeLoader` | **49 ms** |
| + A133 — parse each file once | **23.5 ms** |
| + A132 — cache `Layers` on the digest | **~5 ms** |

Which lands as:

| | today | after |
|---|---|---|
| a registry-touching request | ~250 ms | **~10 ms** |
| `mendel build` | 1.47 s | **~0.4 s** |
| any CLI invocation's floor | 350 ms | **~285 ms** (A142) |
| the fast test suite | ~3.5 min | **projected well under a minute** |
| navigating between screens | a refetch every time | **instant** (A137) |

The first two rows are measured. The third is projected from A135's 86%, and is labelled as a
projection rather than stated as a number.

---

## What this audit did not cover

- **Postgres and the worker.** The database holds two small tables and nothing here touched them.
- **The frontend bundle** is 357KB (108KB gzipped) and was not investigated; it is a local tool
  loaded once, and A137 is the frontend cost that is paid repeatedly.
- **Concurrency.** Everything measured is single-request. Sync handlers in a threadpool mean two
  slow requests do not serialise, but nothing here tested that, and A144 names the single-flight
  gap a cache introduces.
- **The CLI beyond its import floor.** `mendel --help` is 350ms and A142 explains a fifth of it;
  what the remaining ~280ms of import is has not been broken down.
- **The synthetic registries are homogeneous** — 2000 copies of one contract with distinct ids.
  They stress the loader honestly and do **not** stress routing, which is where a heterogeneous
  registry would differ.
