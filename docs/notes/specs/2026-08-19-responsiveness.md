# Responsiveness — Plan 3A phase 7

**Status:** written 2026-08-19, against measurements rather than against reading.
**Implements:** [`notes/audits/2026-08-19-performance-audit.md`](../audits/2026-08-19-performance-audit.md),
findings A132–A145.
**Budget, stated by the operator:** *"max like half a second for normal stuff doing in the
browser. it's a tool, not a server."*

**This phase did not exist until an audit said it should**, and it renumbers what follows:
compose and prod becomes **phase 8**, and 3A is nine phases rather than eight. That is written
here rather than quietly absorbed — a phase list that grows needs a reason on the record, and the
reason is that the tool is 250ms per screen and nobody had measured it.

---

## 1. What phase 7 is for

Every registry-touching screen costs **~250ms warm**. The engine costs 1.47s for a build of which
83% is YAML parsing. The fast test suite is 3.5 minutes of which a projected 86% is the same. And
the browser refetches everything on every navigation because the query client was constructed with
no options.

At the end, a screen answers in about **10ms**, navigation does not refetch, `mendel build` is
under half a second, and the test suite is a fraction of what it was.

**What phase 7 is not:** not a rewrite, not a database, not an index. Issue #43 decided declared
data is files; nothing here reopens that. The fix is that the layer is currently walked five
times and each file read about six times, with the slow parser.

---

## 2. What the audit measured

| | |
|---|---|
| `layers.load` | **244 ms** — ~100% of every registry-touching endpoint |
| declared files in the registry | **39** |
| YAML parses per load | **217** — each file **5.6×** |
| `CSafeLoader` vs `SafeLoader` | **13.6×**, and libyaml is installed |
| the test suite | **86%** YAML parsing (101.5s of 117.6s over 341 tests) |
| one walk + one bucketing pass | **7.3 ms** — and it runs five times |
| `mendel build` | **83%** YAML parsing (1.23s of 1.47s) |
| `diagnostics.yml` | **95 KB**, parsed at import, **69.5 ms**, on every CLI call |
| `new QueryClient()` | `staleTime: 0`, `refetchOnWindowFocus: true` |
| caching a `Layers` | **10.6 MB** at 2000 contracts |
| the module page's graph at 2000 contracts | **1.9 ms** — not a problem |

---

## 3. Decisions

### 3.1 Make it fast in the pure packages; cache only at the API

Two mechanisms are available and they are not equally safe.

**Fixing the waste** — one walk instead of five, with the fast parser — is a pure improvement: same
inputs, same outputs, no lifetime to reason about, no staleness to get wrong. It is worth **244ms
→ ~20ms**, a 12× win.

**Caching** buys the last ~20ms → ~5ms and introduces a question the other fix does not: *when is
this stale?*

So they go in different places:

- **`comeni-core` and `mendel-resolver` get the speed and no cache.** Every caller benefits —
  the CLI, `mendel build`, and the 1346-test suite, which is the biggest single beneficiary and
  the one a cache would serve worst, because tests mutate registries in temporary directories.
- **`mendel-api` gets the cache**, keyed on the registry digest, beside `services/checked.py`
  which already does exactly this for `ops.check`. A request boundary makes the lifetime obvious.

**No cache goes in a pure package.** Invariant 10 is that determinism is a test, and a
module-level mutable store keyed on anything but content is how that stops being true. The
measured cost of holding that line is ~20ms rather than ~5ms in the CLI, which nobody feels.

### 3.2 `yaml_strict` uses libyaml when it is there, and refuses duplicates either way

```python
try:
    from yaml import CSafeLoader as _Base   # libyaml; 13.6× faster
except ImportError:
    from yaml import SafeLoader as _Base    # pure Python, same behaviour
```

**The fallback is not decoration.** PyYAML can be installed without libyaml, and a loader that
raises `ImportError` on such a machine would trade a performance problem for an availability one.

**A31 is the reason this needed checking rather than doing**, and it was checked:

- the duplicate-key refusal **survives**, with its line numbers intact — `'priority' twice, lines
  2 and 3` under both bases
- **53 declared files** — the registry, every vendored `meta.yml`, and `diagnostics.yml` — parse
  to **identical objects** under both
- digests are over file *bytes*, so nothing a `pipeline.yml` pins can move

The duplicate-key check lives in `construct_mapping`, which is Python on both paths; only the
tokeniser is swapped. That is why it survives, and the test asserts it under whichever base is
active rather than assuming.

### 3.3 `stack()` walks and buckets the layer once, not once per kind

`stack()` runs per `DeclaredKind` and, for each, walks every file and calls `declared_kind(p)` —
which parses the file to read one line. Five kinds, so **five walks and five bucketing passes**
over every file, before `kind.parse` parses the ones that matched.

**Bucket once**: walk the layer a single time, call `declared_kind` once per file, and hand each
kind the bucket it asked for. `stack()` takes the bucket instead of computing it.

**Measured, and it corrects this spec's own first draft**, which claimed each file would then be
parsed exactly once:

```
CSafeLoader only, structure unchanged      49.3 ms
one walk + one declared_kind pass           7.3 ms      <- of which ~4/5 is pure repetition today
```

Five of those passes is ~36ms of the 49ms. Removing four gets the load to **~20ms**.

**Each file is still parsed twice, not once** — once to bucket it, once by `kind.parse` to build
it — and that is a deliberate stopping point. Getting to one parse means changing `Kind.parse` to
accept pre-parsed data for all five kinds, which threads `(path, data)` through
`ModuleContract.load` and its coded error wrapping. **Measured worth: about 6ms.** It is refused
here and named so nobody has to rediscover the ceiling.

**A memo is not the fix either, and finding that out is why this is stated.** Consumers *mutate*
the parsed mapping — `declared_kind` pops nothing but `ModuleContract.load` pops `declares:` — so
a shared cached value is consumed by its first reader. A prototype that memoised the parse crashed
with *"does not say what it is"* on the second kind. Bucketing has no such hazard: the bucketing
parse is read and discarded, and `kind.parse` gets a fresh one.

**It also fixes A143.** With four of five walks gone, the `pathlib` cost that dominated the
post-YAML profile — ~2,960 `Path` objects per load over 39 files — goes with them. One change,
both findings; a fix that only addressed the parse would have left it.

### 3.4 The performance property is guarded by counting, never by timing

A test asserting *"the load takes under 30ms"* is a flake generator: it fails on a loaded CI
runner and teaches everyone to re-run rather than to look.

**The regressions this phase prevents are countable, and counting is exact:**

- **the layer is walked once per load**, not once per kind — instrument the glob and assert
- **`declared_kind` is called once per declared file**, not once per file per kind — the exact
  number `stack()`'s redundancy inflates, so it is the number that catches a regression
- **`yaml_strict.load` is called at most twice per declared file** — the ceiling §3.3 stops at,
  asserted as a ceiling so the refused refactor stays refused *visibly*
- **the strict loader's base is the C one when libyaml is importable**

Those four are deterministic, run in the fast lane, and fail loudly the day somebody adds a
sixth kind by adding a sixth scan. A number that must equal the file count is a much better guard
than a millisecond budget, and it is the whole reason this section exists.

**One timing assertion is worth keeping and it is not in the fast lane**: the audit's numbers go
in the journal, and re-measuring them is a person's job with the harness the audit used, not CI's.

### 3.5 The frontend trusts its own cache

```ts
new QueryClient({ defaultOptions: { queries: {
  staleTime: 30_000, refetchOnWindowFocus: false, refetchOnMount: false,
}}})
```

**This is safe here in a way it would not be in most applications**, and the reason is the work of
phases 2–6: every mutation already invalidates exactly the queries it affects — `useAnswer`,
`useAnswerAll`, `usePropose`, `useDecide`, `useAccept`, `useDraft`. The cache is correct without
refetch-on-everything propping it up; the defaults were hiding latency behind more latency.

**Why 30 seconds and not infinity:** the registry can change under the tool — the nightly check,
a `forge land` from a terminal, a colleague's commit — and a bounded staleness means a screen left
open catches up on its own. It is a tool, so the window can be generous; it is not a single-user
toy, so it should not be unbounded.

### 3.6 What is measured is written down, including what was not fixed

The audit's numbers are the baseline. The journal records the after-numbers from the same harness,
so the next person has a comparison rather than a claim.

**Explicitly not fixed, and each says why:**

| | |
|---|---|
| **A138** — the digest key is O(files); ~700ms at 5,800 contracts | right at today's size, and the answer at that size is a key that is not O(files). Nobody is near it |
| **A142's second half** — `REGISTRY` is eager at import | 69.5ms → 4.8ms from §3.2 alone. Making it lazy would save the rest and give up the guarantee that an undeclared code is unrepresentable, which is worth more |
| **A144's single-flight gap** — two concurrent cold requests both load | 244ms made that expensive; ~5ms makes it not matter |
| **the image and the bundle** | phase 8, and a local tool loads its bundle once |

---

## 4. The surface

| File | Change |
|---|---|
| `comeni_core/yaml_strict.py` | the loader base, with a fallback |
| `comeni_core/declared/layered.py` | `stack()` walks and parses once |
| `mendel_api/services/registry.py` | a digest-keyed `Layers`, beside `checked.py` |
| `mendel_api/services/{contracts,sources,module_page,lookup}.py` | read the cached stack |
| `mendel_forge/ops.py` | `drift` and `check` take a preloaded stack when given one |
| `frontend/src/main.tsx` | the query client's defaults |
| `tests/test_declared_loading.py` | the three counting guards |

**`ops.drift` and `ops.check` gain an optional stack parameter** rather than the API caching
around them: they load internally today, so a cache outside them would be bypassed by the two
endpoints that matter most. Optional, defaulting to loading, so the CLI is unchanged.

---

## 5. What this does not settle

**Whether 30 seconds is the right staleness window.** It is a guess with an argument, not a
measurement, and it is the one number here that should move once somebody uses the tool for an
afternoon.

**Scale beyond what was measured.** The synthetic registries are 2000 homogeneous contracts; they
stress the loader honestly and do not stress routing, and A145 says routing is fine at that size
with the worst candidate shape available. 5,800 heterogeneous contracts remain unmeasured.

**The CLI's remaining import floor.** `mendel --help` is 350ms; §3.2 removes ~65ms of it and the
other ~285ms has not been broken down.

**Whether the pure packages should ever cache.** §3.1 says no and the cost of that line is ~20ms
versus ~5ms. If a future measurement makes that gap matter, the argument to reopen is invariant 10
and the reopening should be a spec, not a patch.
