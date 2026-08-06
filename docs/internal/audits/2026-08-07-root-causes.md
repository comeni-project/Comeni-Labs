# Root causes behind A17–A34

**2026-08-07.** Eighteen findings from round two collapse to **nine root design problems**. This
document is the argument for that collapse, and it is what the Plan 1.9-onward specs are written
against — one spec per root, not one per finding.

Every claim below was re-verified against the code before being written down. Where a claim is
inference rather than execution it says so.

> **Why cluster at all.** Round one closed `Mapping` and `bytes` on the egress boundary. Round
> two immediately found `object`, `Path` and `Any` on the same boundary. Those are not three more
> bugs; they are the third instance of one design decision, and fixing them individually
> guarantees a fourth instance in round three. The unit of work has to be the decision.

| Root | The design problem | Findings | Verified by |
|---|---|---|---|
| **A** | the egress boundary enumerates forbidden shapes | A19, A20, A30 | execution |
| **B** | four kinds of declared data, four hand-rolled loaders | A22, A23, A24, A25, A26 | inspection + execution |
| **C** | generated artifacts are assembled by raw interpolation | A27, A34 | execution |
| **D** | "did it change?" is asked of the IR, not the artifact | A28 | inspection + execution |
| **E** | declared IDs are labels, not domains | A18, A29, A32, *(A16)* | execution |
| **F** | a guard that reimplements its subject | A21 | execution |
| **G** | a file is not readable in only one way | A31, A26 | execution |
| **H** | the AI seam is untyped, and Plan 2 lands on it | A32, A33 | inspection |
| **I** | a guard nobody watched fail may be inert | *(A14)* | four instances |
| — | A17 is deliberately unclustered — see the last section | A17 | execution |

---

## The one sentence, if you read nothing else

**Roots A, D and E are the same mistake wearing three hats: enumerate the bad cases and hope the
list is complete.**

- The egress guard lists forbidden *types* — so `object`, `Path`, `Any` walk through.
- `diff_ir` lists compared *fields* — so edges and profile changes are invisible.
- `TypeId` and `ParamLiteral` are *labels* asserting a domain they do not define — so a patient
  name is a valid type id.

Each is a blocklist standing where the domain is closed enough for an allowlist. The codebase
already knows this and says so out loud, in `tests/test_purity.py`:

> *"an allowlist has no unknown unknowns, and a banlist can only ever forbid what somebody
> thought of, which is exactly how the stdlib transports went unnoticed."*

That reasoning was applied to imports and to nothing else. **Applying it consistently is the
single largest correctness change available**, and it is three specs, not one, because the three
sites have genuinely different closure arguments.

---

## Root A — the egress boundary enumerates forbidden shapes

**Findings:** A19 (`object`), A20 (`Any` inert), A30 (`Path`). Historically A6 (`Mapping`,
`bytes`), A3, C3.

**Verified.** `tests/test_egress.py` holds four negative rules — bare `str`, `Mapping`, binary,
`Any` — and reviewer 1's survey of the guard's own helpers returns *uncaught* for `object`,
`list`, `tuple`, bare `dict`, `type` and `Any`. I independently confirmed `object` carries
`{'patient_id': …, 'ssn': …}` into a `Lockfile` with all 8 tests green, and that
`_mentions(typing.Any, typing.Any)` is `False`.

**Why it is the root and not three bugs.** The rule set grows by one entry per audit and has done
so three audits running. Nothing about the design bounds it: the space of Python annotations is
open, and each new one is legal until someone names it.

**What the spec must decide.**

1. **Allowlist of permitted leaf types**, which both reviewers independently proposed: walk each
   payload to its leaves and assert each is `int`/`float`/`bool`/`None`, a `StrEnum`, a
   `BaseModel` already in the walk, or `Annotated[str, <declared marker>]`; containers only as
   `list[<permitted>]`. Everything else fails and the person adding it edits the list.
2. **Structural rather than tested.** The deeper question: should this be a test at all? A test
   runs after the fact. `EgressPayload.__init_subclass__` could reject an illegal field at class
   definition, making an illegal payload an import error rather than a test failure — and making
   the boundary a property of the type, which is the move Plan 1.8 made nine times over ("a guard
   in a caller is a guard the next caller forgets"). Cost: errors at import time are harder to
   read, and the existing four tests are good documentation of specific past defects.
3. Whether the four negative rules stay as regression documentation once the allowlist exists.

**Deferring costs:** every field added to any payload before this lands is unchecked, and
publication is the door with no undo.

---

## Root B — four kinds of declared data, four hand-rolled loaders

**Findings:** A22, A23, A24, A25, A26. Historically A5, A15, A12, A7.

**Verified by inspection.** Four independent classmethods:

| loader | signature | recursive | takes layer names | records displacement |
|---|---|---|---|---|
| `Registry.load` | `(layers, vocab, names)` | `rglob` | yes | `ShadowRecord`, module-key only |
| `RuleTable.load` | `(layers, registry, vocabulary, measurements, names)` | `glob` | yes | `displaced_layer` dict |
| `Vocabulary.load` | `(layers)` | `glob` | **no** | **no** |
| `MeasurementRegistry.load` | `(layers)` | `glob` | **no** | **no** |

Each reimplements: find files, parse, stack in order, last-wins, and *optionally* record what was
displaced. Invariant 11 says all four stack; two of four have any notion of which layer they came
from.

**Why it is the root.** A5 and A15 were "add provenance to a loader", done twice, differently —
and A22 proves the second one incomplete, because `router._choose` never reads what
`RuleTable.load` records. The defect is not that a loader was missed; it is that *there is no
such thing as a loader* in this codebase, only four functions that happen to do a similar job.
A25 (name collision) and A26 (glob divergence) are the same absence seen from other angles: no
shared notion of layer identity, no shared notion of what a layer contains.

**This is the root where "later it will be impossible" is literally true.** The forge adds kinds
of declared data. Every kind added before this lands is a fifth, sixth, seventh independent
implementation of stacking.

**What the spec must decide.**

1. **The abstraction's shape.** Something like `layered_load(kind, layers)` where each kind
   supplies only *parse one file* and *key one entry*; the mechanism owns ordering, displacement
   recording, positional layer identity, recursion, and file-coverage. Then "all four stack and
   all four record" is one implementation with one test.
2. **Layer identity becomes positional, not nominal** (A25). `layer_of` maps to an *index*; the
   name is looked up for rendering only. Alternatively `layers.load` refuses a stack with
   duplicate names — smaller, and the A9 precedent favours refusing over resolving.
3. **How provenance reaches the consumer.** A22 is a *reader* problem, not a recorder problem:
   the fact existed and `router._choose` did not read it. Whatever the mechanism records must be
   impossible to route around — which probably means the resolved thing carries it, not a
   side-table the caller must remember to consult.
4. **A surface for displaced declarations that are not selections.** A23 and A24 displace a
   *measurement* and a *vocabulary type*; neither is an `IRNode` or a `ParamBinding`, so
   `ResolvedValue.displaced_layer` has nowhere to live. Reviewer 2 proposes
   `PipelineIR.displaced_declarations`, carried into the bundle as `shadowed` is.
5. **Extension versus replacement.** An overlay adding a state is not an overlay changing an
   `entry_channel`. Displacement-not-origin (Plan 1.8's rule) needs restating per kind.

---

## Root C — generated artifacts are assembled by raw interpolation

**Findings:** A27 (`reason` → Groovy), A34 (`nf_process` → Groovy, and every identifier).

**Verified by execution.** `main.nf.j2` has six interpolation points; exactly one
(`value.rendered`) passes through `_render_literal`. The other five —
`node.process`, `node.include`, `node.id`, param `name`, the entry-channel `expression`, and
`call` — are raw registry data. I injected Groovy through `nf_process` on an unverified contract
and watched it land at script scope, and the same newline propagated into `node.id`, into
`params.<node>_<name>`, and into the CLI's own stderr, corrupting the overlay-reroute notice that
Plan 1.8 added.

**Why it is the root.** A27 alone reads as "escape one prose field". A34 shows the actual shape:
**the emitter trusts every string the registry gives it**, and one of the six holes happens to be
prose. Fixing `reason` leaves five.

**What the spec must decide.**

1. **Escape at the emitter, bound at the type, or both.** Reviewer 2 argues both, and I agree:
   the emitter must not depend on clean input, and the boundary must not depend on a careful
   emitter. Bounding `Text` (no control characters, bounded length) closes A27 at the three
   sources that converge on it — model, bundle, registry — in one change.
2. **Identifiers are a different problem from prose.** `nf_process` and a param name are Groovy
   *identifiers*; the fix is a character-class check at the contract model, not escaping. This is
   Root E arriving in a new place — `nf_process: str` is a label with no domain.
3. **`entry_channel` is deliberately unbounded Groovy** and must stay so; a lab bringing its own
   type is a designed feature. So the spec must say what makes it *legitimately* different from
   the other five, and A24 says the answer is that its replacement must be reported, not
   forbidden.
4. **Whether conformance's `unverified` fallback is the real defect.** A34 is only reachable
   because a contract with absent module source is emitted rather than refused. That is a
   deliberate decision recorded in CLAUDE.md; it may still be wrong.

---

## Root D — "did it change?" is asked of the IR, not the artifact

**Finding:** A28.

**Verified.** `diff_ir` compares `contract_id`, param values, and the selection's tier and
reason. Not edges, profile, shadowed, unverified, `from_layer` or `displaced_layer` — several of
which the emitter reads. Demonstrated twice with `main.nf` demonstrably different while the tool
printed *"no changes: this pipeline re-resolves identically"*.

**Why it is the root, and why it is Root A again.** `diff_ir` enumerates the fields it knows.
Every field added to the IR — Plan 1.8 added four — is a new blind spot, silently.

**What the spec must decide.** Reviewer 2's proposal is strong and I think it is right: **compare
the emitted bytes for the verdict, and let `diff_ir` explain it.** `mendel upgrade` already
re-emits, and federation §4.1 promises byte-identical Nextflow — so byte comparison *is* the
promised property, cannot go stale as fields are added, and turns `diff_ir` from evidence into
commentary. The spec should still extend `diff_ir` to edges and tier, because "the pipeline
changed" without "here is how" is not useful to a reviewer.

---

## Root E — declared IDs are labels, not domains

**Findings:** A29 (`type_id`), A18 (the guard matches a spelling, not a type), A32
(`candidates: list[Any]`). Open: A16 (`chosen` carries three kinds of value).

**Verified.** `resolve.py` mentions `vocab` **zero** times; nothing validates a goal's declared
types against the vocabulary, and a patient name reaches a `PublishBundle` as a `type_id`.
`test_construction.py` matches the literal string `"DataProfile"` with no alias resolution.

**Why it is the root.** `Annotated[str, "type-id"]` says *somebody named this*, not *this is a
declared type*. The egress guard then treats "carries metadata" as "has a domain" — which is A3's
finding word for word, still true, and now true in three more places. A18 is the same error in a
guard rather than a type: it checks a *spelling* because there is no type to check.

**What the spec must decide.**

1. **Validate `type_id` against the vocabulary in `resolve()`**, not in `mendel build` — A2's
   lesson exactly, since `upgrade` reads a stranger's bundle. An undeclared type is already a
   user error worth a message; closing the channel is a side effect of doing the obvious thing.
2. **Whether declared IDs become types rather than aliases.** The heavier option: `TypeId` is a
   value object validated on construction against a loaded vocabulary. Interacts with A16, which
   wants `DecisionRecord.chosen` discriminated by kind.
3. Whether A3's `HumanParamValue` blocklist survives at all once domains exist, or is deleted as
   the stopgap it says it is.

---

## Root F — a guard that reimplements its subject

**Finding:** A21 — found independently by both reviewers.

**Verified.** The test builds its forgery from `sha256(b"alpha")`; the code hashes
`sha256(_FILE + content)`. Reverting the fix leaves 12 green.

**Why it is a root and not a typo.** Neither commit is wrong. `6c4fe14` added domain separation
and silently disarmed the guard protecting `8d27cf4`. **A test that hard-codes its subject's
internals has an expiry date nobody wrote down**, and this is a class: any guard constructing an
input the way production constructs it will drift the same way.

**What the spec must decide:** factor `_entry_hash(name, content)` so the test and the
implementation call the same function — and then sweep for other guards that re-implement rather
than call.

---

## Root G — a file is not readable in only one way

**Findings:** A31 (duplicate YAML keys), A26 (`.yaml` invisible).

**Verified.** 7 `yaml.safe_load` call sites, none strict; a second `priority:` 200 lines below
the first wins silently, and the digest then pins the parsed model, so it is *consistent* with
what runs and warns nobody that the file has two readings.

**Why it is the root.** Plan 1.7 landed the rule *a hash over concatenated fields means nothing
unless each field can be read only one way*. This is that rule one level up, applied to the file
rather than the digest. It matters most exactly where the project has invested: federation's
curated tier is a named human signing off on a diff hunk.

**What the spec must decide:** one `comeni_core.yaml_strict.load()` used by all 7 call sites,
refusing duplicate keys; whether anchors and aliases are also refused (a hypothesis, untested);
and whether unclaimed files in a layer are an error, which is the A26 half and belongs with
Root B.

---

## Root H — the AI seam is untyped, and Plan 2 lands on it

**Findings:** A32, A33.

**Verified.** `Ambiguity.candidates: list[Any]`, `Ambiguity.context: dict[str, Any]`, and
`Ambiguity` has **no `model_config`** — so no `extra="forbid"`. Both shapes are ones the egress
guard bans; it never sees them because `Ambiguity` is not reachable from an `EgressPayload`.

**Why it is a root.** `AmbiguityResolver.resolve(ambiguity)` *is* the call a model adapter
implements. The typed door and the object actually handed across it are different objects, and
`AmbiguityRequest` cannot even carry what `context` holds — so an adapter must improvise, which
is the one thing a declared boundary exists to prevent.

**Fix before Plan 2, not during it.** This is the cheapest of the nine and the only one that
gets more expensive the moment Plan 2 starts.

---

## Root I — a guard nobody watched fail may be inert

**Finding:** A14, open, critical.

Round two added five instances: A20 (`Any`), A21 (digest), A30 (`Path`), A19 (`object`), A18
(construction). All five were found by reverting; none by reading.

**Not a code fix.** Its closure condition is a protocol: every guard in `tests/` has a recorded
revert that was watched failing. Round two covered roughly 40% and said so. **This root's spec is
a checklist and a schedule, not a design.**

---

## A17 is deliberately unclustered

`ctypes` defeats both purity guards and delivered a serialised `PipelineIR` over a real socket.

It is tempting to file this under Root A as "another blocklist entry", and that would be wrong.
Invariant 1's static half **cannot** be an allowlist for `mendel-compiler` — the compiler must
run Nextflow, so it needs `subprocess`, and the file already argues that "an honest banlist is
better than a dishonest allowlist" for exactly this package. The runtime half is an allowlist of
watched *events*, and FFI raises different events rather than escaping the shape of the rule.

So A17 is a genuine gap in a defence that was honestly described, not a design error. Its fix is
two entries — `ctypes` on the banlist, `ctypes.dlopen`/`dlsym`/`call_function` on the watch list —
plus a rewrite of CLAUDE.md's claim to mention FFI, since Plan 1.8's wording ("two partial guards
whose union is the claim") does not anticipate it.

**It gets its own small spec** rather than being absorbed, because absorbing it would imply the
purity guards share a root cause with the egress guard, and they do not.
