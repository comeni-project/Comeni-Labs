# Audit round two — Plan 1.8's fixes, and what they did not cover

**2026-08-07.** Scope: `plan-1.8-closing-the-audit` @ `3ce8119`, which is `main` plus Plan 1.8.
Method: [`2026-08-07-round-two-brief.md`](2026-08-07-round-two-brief.md) — **revert and watch, not
read**.

Two independent reviewers with no session context, one per half of the brief, plus coordinator
verification of every claim before it was recorded here. Findings keep their numbers
permanently; round one is [`2026-08-06-plan-1-to-1.7-audit.md`](2026-08-06-plan-1-to-1.7-audit.md)
and holds A1–A16.

> **Verdict.** The loop does not exit. Eighteen findings, seven critical. Plan 1.8's fixes
> themselves hold — every one was reverted and every one failed loudly — but **A15's fix is
> half-applied**, five more guards are inert in A14's sense, and two paths execute arbitrary
> Groovy from data a laboratory installs. Round one closed `Mapping` and `bytes` on the egress
> boundary; round two immediately found `object`, `Path` and `Any`. That is not three more bugs,
> it is the third instance of one design decision, and
> [`2026-08-07-root-causes.md`](2026-08-07-root-causes.md) is where that argument lives.

| # | What | Severity | Root | Found by |
|---|---|---|---|---|
| A17 | `ctypes` defeats both purity guards, and exfiltrates for real | critical | — | reviewer 1 |
| A18 | the construction guard is defeated by an import alias or `model_construct` | important | E | reviewer 1 |
| A19 | a field typed `object` carries arbitrary data through every egress rule | critical | **A** | reviewer 1 |
| A20 | `test_no_payload_carries_an_untyped_container` cannot fail | critical | **A** | reviewer 1 |
| A21 | the layer-digest forgery guard passes against the forgery it names | important | F | **both** |
| A22 | a rule-pinned reroute is unrecorded, and the IR asserts the wrong layer | critical | **B** | reviewer 2 |
| A23 | a measurement overlay silently changes what the pipeline measures | critical | **B** | reviewer 2 |
| A24 | a vocabulary overlay silently replaces a type's entry channel | important | **B** | reviewer 2 |
| A25 | two layers sharing a name defeat both the A5 and A15 records | important | **B** | reviewer 2 |
| A26 | three loaders are non-recursive and `.yaml` is invisible to all four | important | **B**/G | reviewer 2 |
| A27 | a decision's `reason` is emitted unescaped; registry data executes Groovy | critical | **C** | reviewer 2 |
| A28 | `mendel upgrade` reports "no changes" when the emitted pipeline changed | important | **D** | reviewer 2 |
| A29 | free text rides into a `PublishBundle` through `Goal.have[].type_id` | critical | E | reviewer 2 |
| A30 | `pathlib.Path` is invisible to every rule in the egress guard | important | **A** | reviewer 2 |
| A31 | a duplicate YAML key is accepted silently, last one wins | important | G | reviewer 2 |
| A32 | the `AmbiguityResolver` seam is untyped — the object Plan 2 hands a model | important | E/H | reviewer 2 |
| A33 | four smaller observations at the AI seam | minor | H | reviewer 2 |
| A34 | `nf_process` injects Groovy through an unverified contract; every emitted identifier is unescaped registry data | critical | **C** | coordinator |
| A35 | a vocabulary overlay *replaces* a type's states instead of extending them | important | **B** | coordinator |

Roots are the clusters in [`2026-08-07-root-causes.md`](2026-08-07-root-causes.md). A17 is
deliberately unclustered — see there.

---

## Critical

### ⬜ A34. `nf_process` injects Groovy through an unverified contract

`templates/main.nf.j2`, `emit.py`, `contract.py:168`

Found while re-verifying A27's cluster, as the hypothesis reviewer 2 framed and did not run.
**It holds, and it is broader than A27.**

`main.nf.j2` has six interpolation points and exactly one is guarded:

```
10:  include { {{ node.process }} } from './{{ node.include }}'
15:  // tier {{ … }}: {{ value.reason }}
16:  params.{{ node.id }}_{{ name }} = {{ value.rendered }}      ← only `rendered` is guarded
22:      {{ name }} = {{ expression }}
26:      {{ call }}
```

`ModuleContract.nf_process` is a plain `str`. Conformance (M0101) compares it to the vendored
module and refuses a mismatch — **but only when module source exists.** CLAUDE.md states the
fallback: *"Where module source is absent the contract is marked `unverified` on the IR rather
than trusted."* So an overlay contract pointing `nf_include` at a path that is not vendored is
emitted unchecked.

Reproduced on the unmodified tree, no bundle editing and no model:

```yaml
id: lab/evil/sorter@1.0.0
nf_process: "LAB_SORT }\nprintln 'INJECTED VIA nf_process AT PARSE TIME'\ninclude { LAB_SORT"
nf_include: modules/lab/nowhere/main
priority: 99
```

```
$ uv run mendel build --goal examples/rnaseq-goal.yml --registry registry --registry lab --out out
5 modules, 1 requiring review

$ sed -n '11,13p' out/main.nf
include { LAB_SORT }
println 'INJECTED VIA nf_process AT PARSE TIME'
include { LAB_SORT } from './modules/lab/nowhere/main'
```

**And it propagates.** `node.id` is `nf_process.lower()`, so the newline also reached
`params.{{ node.id }}_{{ name }}` and the CLI's own stderr — the overlay-reroute notice added by
Plan 1.8 Task 7 printed the injected line and mangled its own output:

```
println 'injected via nf_process at parse time'
include { lab_sort (module) = lab/evil/sorter@1.0.0: from 'lab', displacing 'comeni-registry-examples'
```

A guard added to report untrusted data was itself corrupted by that data.

**Why this is not A27 with a different field.** A27 is prose reaching a comment. This is an
*identifier* reaching a declaration, and identifiers are the load-bearing text in the emitted
file. Fixing `reason` alone leaves five interpolation points open. The root is that the emitter
trusts every string in the registry, not that one field was forgotten.

---

### ⬜ A27. A decision's `reason` is emitted unescaped, so registry data executes Groovy

`templates/main.nf.j2:15`, `emit.py`

`_render_literal` escapes quotes and refuses control characters in *values*. Prose is not a
value and does not pass through it. A newline in `reason` ends the `//` comment and everything
after it is script-scope Groovy, executed by Nextflow at parse time.

Three sources feed `reason`, none of them the compiler's:
`Resolution.reason` from the resolver port (**a model, in Plan 2**), `DecisionRecord.reason`
replayed verbatim from a bundle on disk, and a rule's or decision's `cite:` in any installed
overlay.

Verified by the coordinator against a hand-edited bundle:

```
$ uv run mendel upgrade --bundle inj/pipeline.bundle.json --out inj2
no changes: this pipeline re-resolves identically     ← A28, in the same run

$ sed -n '15,17p' inj2/main.nf
// tier 4 (required): looks like a justification
println 'INJECTED GROOVY AT SCRIPT SCOPE'
//
```

Reviewer 2 additionally executed it — a file written to disk by `nextflow run -preview` — and
reproduced the same from a rule's `cite:` alone, with no bundle editing. The injected Groovy is
valid, so `nextflow lint` in `make static` does not object.

**Round one recorded this area under *Clean — attacked and held*.** That claim was tested against
`_render_literal` and is true of values. It is not true of the file.

---

### ⬜ A22. A rule-pinned reroute is unrecorded, and the IR asserts the wrong layer

`mendel_resolver/router.py:170-171`, `resolve.py:231-232`

A15's fix builds `RuleTable.displaced_layer` for every decision key — `param:` and
`producer_of:` alike. `_resolve_param` reads it. **`router._choose`, where a `producer_of:` rule
actually selects a module, never does.** Confirmed by inspection: `router.py` references
`registry.layer_of` only, and `_displaced_layer()` asks which layer the winning *contract* came
from.

So when an overlay rule reroutes to a contract that lives in the base layer, the IR records
`from_layer: registry`, `displaced_layer: None` — not merely omitting the reroute but asserting
its opposite.

```
rules.displaced_layer = {'producer_of:alignment.bam': 'registry'}   ← the fact is held
aligner chosen        = nf-core/hisat2/align@2.2.2                  ← the overlay won
selection.from_layer  = registry                                    ← the artifact lies
overlay_reroutes()    = []
```

**Why the guard missed it.** `tests/test_audit_regressions.py::_stacked` gives its overlay a
`param:` rule and a rival *contract*, never a `producer_of:` rule — so the A15 test asserts over
the one of two decision kinds that works. A14's shape, in a fix written the same day.

---

### ⬜ A23. A measurement overlay silently changes what the pipeline measures

`comeni_core/measurement.py:114-134`

`MeasurementRegistry.load` takes no layer names and is last-wins on `found[measurement_id]` with
no record. A `Measurement` carries `meta_key`/`meta_values`, which `meta_for()` feeds into the
emitted `meta` map — the channel by which a measured fact reaches an nf-core module.

An overlay declaring one extra translation flipped the library's strandedness:

```
ov1/main.nf:20:  … meta + [single_end: false, strandedness: 'forward'] …
b1/main.nf:20:   … meta + [single_end: false, strandedness: 'reverse'] …
```

The goal declared `reverse`. featureCounts is now told `-s 1` instead of `-s 2` — the exact
wrong-numbers failure `mendel explain M0107` describes and `tests/test_counts.py` asserts
against. Exit 0, no `OVERLAY`, no `SHADOW`, no `REVIEW`.

Proved at emission level. **Not** proved at counts-matrix level: reviewer 2 did not run the slow
lane, and says so.

---

### ⬜ A29. Free text rides into a `PublishBundle` through `Goal.have[].type_id`

`comeni_core/marks.py`, `mendel_resolver/resolve.py`

`TypeId = Annotated[str, "type-id"]` is a label with no domain, and **nothing validates a goal's
declared types against the vocabulary** — `resolve.py` does not mention `vocab` once (verified:
zero occurrences). `router._have_satisfies` only compares, so a `have` entry that satisfies
nothing is never looked up and never rejected. `Constraints.required_states[].type_id` is the
same.

```yaml
have:
  - type_id: "PT-4471023 Jane Doe, BRCA1 c.5266dupC, /data/patients/PT-4471023/S1_R1.fastq.gz"
constraints:
  required_states:
    "notes: patient consented 2026-03-02, MRN 88213": ["free text rides here too"]
```

```
$ uv run mendel publish --goal leak-goal.yml --out leak1
5 modules, 1 requiring review
$ grep -n "PT-4471023\|MRN 88213" leak1/pipeline.bundle.json
17:        "type_id": "PT-4471023 Jane Doe, BRCA1 …",
33:          "type_id": "notes: patient consented 2026-03-02, MRN 88213",
```

Invariant 15 ("no input accepts a sample identifier, filename or path") and invariant 14
("exactly two fields may hold free text") failing together, in the door with no undo. A3's
stopgap was scoped to "fields a person fills in" and then applied to two of them; this is a
third.

---

### ⬜ A19. A field typed `object` carries arbitrary data through every egress rule

`tests/test_egress.py`

The egress type rules are four blocklists — bare `str`, `Mapping`, binary, `Any`. `object` is
none of them, and Pydantic accepts anything into an `object`-typed field. Verified by the
coordinator: `leak_any: object` on `Lockfile` (reachable from `PublishBundle`) →

```
$ uv run pytest tests/test_egress.py -q
8 passed
$ … Lockfile(leak_any={'patient_id':'PT-4471023','ssn':'123-45-6789'}).model_dump_json()
{"leak_any":{"patient_id":"PT-4471023","ssn":"123-45-6789"}, …}
```

Reviewer 1's survey of the guard's own helpers: `object`, `list`, `tuple`, bare `dict`, `type`
and `Any` all uncaught; only `bytes` and `str` caught.

---

### ⬜ A20. `test_no_payload_carries_an_untyped_container` cannot fail

`tests/test_egress.py`

The test calls `_mentions(annotation, typing.Any)`, and `_mentions` searches `__metadata__` for
a **marker object** — correct for `marks.FreeText`, meaningless for `Any`, which is never
metadata but the annotation itself. The predicate is `False` for every annotation that has ever
existed:

```
typing.Any                  _mentions(.,Any) = False
dict[str, typing.Any]       _mentions(.,Any) = False
list[typing.Any]            _mentions(.,Any) = False
```

Found by reviewer 1, independently reproduced by the coordinator before recording.

CLAUDE.md invariant 14 says in terms *"no payload may carry an `Any`-typed field"*; the guard's
own docstring says *"a `dict[str, Any]` would defeat the whole thing"*. Both were enforced by
nothing, and round one's A3 cited this guard as evidence that C3 was closed.

---

### ⬜ A17. `ctypes` defeats both purity guards, and exfiltrates for real

`tests/test_purity.py`, `tests/test_purity_runtime.py`

`ctypes` appears **zero times** in either guard (verified). The static half runs a banlist for
`mendel-compiler` — it cannot be an allowlist, because the compiler needs `subprocess` — and
`ctypes` is not on it. The runtime half watches Python-level audit events (`socket.*`,
`subprocess.Popen`, `os.system`); a libc socket via `ctypes.CDLL` raises `ctypes.dlopen` /
`dlsym` / `call_function`, none of which are watched, and never touches Python's `socket`.

Reviewer 1 added a `_telemetry()` to `emit.py`, stood up a listener, and watched a serialised
`PipelineIR` arrive:

```
$ uv run pytest -q tests/test_purity.py tests/test_purity_runtime.py
3 passed in 0.29s
RECEIVED: b"nodes=[IRNode(id='trimgalore', contract_id='nf-core/trimgalore@0.6.10', …"
```

`ctypes.util.find_library("c")` *is* caught — but as `subprocess.Popen`, because it shells out
to a linker. Correct verdict, wrong mechanism; hardcoding the soname removes even that.

**This is the finding that says the fix for A1 was right and incomplete.** Plan 1.8 rewrote the
claim to "the pure packages *do not* reach the network, enforced by two partial guards whose
union is the claim." FFI is outside the union, and the wording did not anticipate it.

---

## Important

### ⬜ A35. A vocabulary overlay replaces a type's states instead of extending them

`comeni_core/vocabulary.py:74`

Found while writing root B's spec. `Vocabulary.load` does
`types[type_id] = frozenset(data.get("states", []))` — an unconditional replace — while
`entry_channel` and `test_data` two lines below replace *only when present*. So merge behaviour
differs **within a single loader**, and the unconditional one is the destructive direction.

The method's own docstring promises the opposite: *"A laboratory adding a state … needs types to
stack the way contracts already do."*

```
base states : ['deduplicated', 'subsampled', 'trimmed']
overlay     : states: [phix_removed]
stacked     : ['phix_removed']              ← the other three are gone
entry_channel survived: True                ← because the overlay did not declare one
```

End to end it is loud but misdirected — exit 1 with an unhandled traceback,
`UnknownStateError: 'trimmed' is not a declared state for 'fastq.reads'`, naming the base
contract that used the state rather than the overlay that removed it. Same presentation class as
A33's symlink case.

Closed by root B's explicit merge policy: default replace, `add_states` to extend, matching the
`add_values` convention measurements already have.

---

### ⬜ A24. A vocabulary overlay silently replaces a type's entry channel

`comeni_core/vocabulary.py:70-79`, `emit.py:135`

Last-wins on `types`, `entry_channels` and `test_data`, no layer names, no record.
`entry_channel` is unbounded Groovy emitted verbatim — deliberately, so a lab can bring its own
type. An overlay therefore replaces how any type enters the pipeline:

```
$ grep -n 'ch_fastq_reads =' ov2/main.nf
20:  ch_fastq_reads = (Channel.of([ [id: 'x'], [ file('/data/lab/secret_cohort_R1.fastq.gz'), … ] ])) …
```

`params.input` — the placeholder invariant 15 rests on — is gone, replaced by hardcoded
laboratory paths, from an installed overlay, with no notice. The paths do **not** reach the
bundle (checked), so this is silent-reroute rather than egress; but `main.nf` is the artifact
people share.

### ⬜ A25. Two layers sharing a name defeat both the A5 and A15 records

`rules.py:173-175`, `router.py:106-118`

Layer identity is a *name*, and names are not unique. `rules.py` suppresses the record when
`prior == layer_name`; `router.py`'s `order.index(winning_layer)` returns the **first** index of
a repeated name, so an overlay's `winner_at` is 0 and nothing can be below it. Both A5's and
A15's records vanish while the overlay still wins — verified for contracts and for rules, with
identical emitted output in both runs and only the notice differing.

The lockfile's own docstring already says this is a day-one collision: *"Task 8 names the public
layer `registry/`, so a lab stacking it over their own `registry/` hits it on day one."*

### ⬜ A26. Three loaders are non-recursive, and `.yaml` is invisible to all four

`vocabulary.py`, `measurement.py`, `rules.py` use `glob("*.yml")`; only `Registry.load` uses
`rglob`. All four match `*.yml` only, so a `.yaml` file is read by nothing while still being
hashed into the layer digest.

```
$ mv B/registry/contracts/lab-star.yml B/registry/contracts/lab-star.yaml
$ uv run mendel build … --out dup7
5 modules, 1 requiring review
$ grep -n 'star/align' dup7/pipeline.ir.json
33:      "contract_id": "nf-core/star/align@1.11.0",     ← the lab's overlay contract vanished
```

An overlay that does nothing is indistinguishable from an overlay that worked. Registry data is
the product; a file in a layer that no loader reads is a failure a registry cannot afford.

### ⬜ A28. `mendel upgrade` reports "no changes" when the emitted pipeline changed

`mendel_resolver/diff.py`

`diff_ir` compares `node.contract_id`, `binding.value.value`, and the selection's tier and
reason (verified). It does not compare `ir.edges`, `ir.profile`, `ir.shadowed`, `ir.unverified`,
`from_layer` or `displaced_layer` — several of which the emitter reads.

Two reproductions, both with `main.nf` demonstrably different: A27's injection, and a bundle
published against two layers and upgraded against one. The drift line was correct in the second
case; the *changes* line was a false statement about the product's central claim.

The serious case is edges: `resolve.py` records that wiring `.bai` into featureCounts was "valid
Nextflow, no flag, and `-stub-run` cannot catch it". `mendel upgrade` cannot catch it either.

### ⬜ A30. `pathlib.Path` is invisible to every rule in the egress guard

Not a marker, not a bare `str`, not a `Mapping`, not binary, not `Any` — and it serialises to a
full filesystem path. Reviewer 2 added `built_from: Path | None` to `PublishBundle`, watched the
guard report 8 passed, dumped `"/data/patients/PT-4471023/S1_R1.fastq.gz"` into the door with no
undo, and reverted.

This is the type the project has already had to evict from artifacts twice — A9's symlinks and
A12's `ShadowRecord.winning_layer`.

### ⬜ A31. A duplicate YAML key is accepted silently, last one wins

`yaml.safe_load` keeps the last of duplicated mapping keys. `extra="forbid"` (A10) cannot see
it, because the duplicate is collapsed before Pydantic. The digest then pins the parsed model,
so it is consistent with what runs and gives no warning that the file has two readings. There
are **7** `yaml.safe_load` call sites (verified), none strict.

```
$ sed -n '10p' dupkey/contracts/nf-core/hisat2-align.yml
priority: 0
$ tail -1 dupkey/contracts/nf-core/hisat2-align.yml
priority: 999
$ … layers.load('dupkey').registry.get('nf-core/hisat2/align@2.2.2').priority
loaded priority = 999
```

Round two's own rule — *a hash means nothing unless each field can be read only one way* —
applied one level up: the **file** can be read two ways. This matters most where the project has
invested: federation's curated tier is a named human signing off on a diff hunk.

### ⬜ A21. The layer-digest forgery guard passes against the forgery it names

**Found independently by both reviewers**, which is why it is recorded once here.

`test_a_filename_cannot_forge_an_entry_boundary` builds its forged filename from
`hashlib.sha256(b"alpha")`. Since `6c4fe14` the per-file hash is `sha256(_FILE + content)`, so
the forged name embeds a value the implementation never computes and the digests differ for a
reason unrelated to the property under test.

Reverting the A9-era fix (`_hex(name.encode())` → `name`) leaves **12 passed**. Rebuilding the
forgery with the `_FILE` prefix collides on the reverted code and does not collide on the shipped
code — so the digest is sound and the test that proves it is not.

**Neither commit is wrong; the interaction is.** `6c4fe14` (domain separation) silently disarmed
the guard protecting `8d27cf4` (name hashing).

### ⬜ A18. The construction guard is defeated by an import alias or `model_construct`

`tests/test_construction.py:31` is `if name == "DataProfile"` — a literal string match with no
alias resolution (verified), and it knows one construction spelling. `test_purity.py` builds an
`_imported_names` map for exactly this reason; this guard does not.

```python
from comeni_core.profile import DataProfile as _DP
_DP.model_construct(measurements=[])   # skips validation entirely
```

```
$ uv run pytest -q tests/test_construction.py
1 passed
```

This is invariant 15's guard, whose whole job is that every `DataProfile` passes
`MeasurementRegistry.profile()`.

### ⬜ A32. The `AmbiguityResolver` seam is untyped

`comeni_core/decision.py:19-25`

`Ambiguity.candidates: list[Any]`, `Ambiguity.context: dict[str, Any]`, and `Ambiguity` has **no
`model_config` at all** (verified) — so no `extra="forbid"`. Both shapes are ones the egress
guard bans; the guard never sees them because `Ambiguity` is not reachable from an
`EgressPayload`.

But `AmbiguityResolver.resolve(ambiguity)` is precisely the call a model adapter implements. The
typed door (`AmbiguityRequest`) and the untyped object handed to the adapter are different
objects, and `AmbiguityRequest` has no field for the `type_id`/`required` keys that `_source_for`
puts in `context` — so the mapping is lossy in the direction of "the adapter improvises".

**Fix before Plan 2, not during it.**

---

## Minor

### ⬜ A33. Four smaller observations at the AI seam

- **`router._choose`'s tier-4 reason can be false.** It emits `"nothing distinguishes …; chosen
  by id order"` even when A8's fix means the resolver's answer selected instead. Not emitted into
  `main.nf` today, but it is in the IR and the bundle, and A8 was about records contradicting the
  pipeline.
- **`_resolve_param` trusts a non-candidate answer**; `router._choose` and `_source_for` both
  fall back, with comments explaining why. Defensible today (`candidates=[None]` means a tier-4
  parameter has no domain — that is A16) but it is the one site where a model's answer is taken
  on trust, and the asymmetry is undocumented at the site.
- **A symlink in a layer produces a raw traceback.** `layers.load` raises a bare `ValueError`
  which `cli.main`'s except-list does not catch. The refusal is correct; the presentation is a
  stack trace rather than a `mendel:` line.
- **CLAUDE.md invariant 14 is stale.** It says "exactly two fields … may hold free text";
  `FREE_TEXT_FIELDS` now holds four. The guard is the honest one.

---

## Clean — attacked and held

Recorded because the *Not examined* section below is only meaningful next to it.

**Plan 1.8's fixes hold.** Every one was reverted and every one failed loudly, naming the right
thing: A3 (7 parametrised failures), A5/A15 for `param:` decisions, A8 (the two-fixture
`_PicksLast`/`_PicksFirst` design is genuinely correct), A9's symlink refusal, A10, A11, the
`8dbde51` drift guard — the former A14 instance, now genuinely able to fail — the `.pyi`
completeness check, conformance M0101, invariant 8's tie handling (7 failures across two files),
and the static purity scan against a plain `import socket`.

**Determinism holds.** Full `mendel publish` under `PYTHONHASHSEED=1` and `=99999`:
`diff -r` → identical across `main.nf`, `nextflow.config`, `pipeline.ir.json`,
`pipeline.bundle.json`, `mendel.lock.yml`. Every `frozenset` in the pure packages has a sorting
`field_serializer`; `conformance.check` sorts before `ir.unverified` is built.

**`digest_of_directory` is not forgeable on the shipped code** — proved positively, not merely by
the (inert) test.

**Replay rejects a forged answer.** A published bundle patched to `chosen: "PWNED-VALUE"` →
`0 decisions replayed, 1 newly asked`, value absent from `main.nf`, decision still tier 4 and
flagged. Round one's claim re-verified first-hand.

**`_render_literal` contains value-shaped injection** — quotes and backslashes escaped, control
characters refused. A27 and A34 go around it, not through it.

**The egress transitive walk genuinely expands.** 16 nested models reached from 5 payload roots;
a bare `str` two models deep and a `dict` on `Lockfile` were both caught and named. A19, A30 and
A20 are types the walk *visits and cannot classify*, not models it misses.

**`mendel publish` writes after the gate** (A4's fix), and a `str` subclass on a payload is
refused by Pydantic before the guard is reached.

---

## Not examined

- **A14 does not close.** Reviewer 1 recorded reverts for ~40% of guards; reviewer 2 for four of
  roughly forty. Untouched: the whole emission surface (`test_emit`, `test_runnable`,
  `test_gates`), publication and upgrade (`test_publish`, `test_upgrade`,
  `test_registry_drift`), the tier ladder (`test_resolve`, `test_profile`, `test_pinning`,
  `test_replay`, `test_ports`, `test_port_alternatives`), registry loading (`test_registry`,
  `test_vocabulary`, `test_registry_layer`), conformance M0102–M0107, and most of
  `test_audit_regressions`.
- **The slow lane was never run by either reviewer.** `tests/test_counts.py` needs Docker and is
  the only test exercising the v1 criterion — and A23's strandedness flip is exactly what it
  asserts. Proved at emission level only.
- **Hypotheses, not findings.** YAML anchors and billion-laughs expansion as a second
  "read only one way" violation. `Param.default: Any` and `NfInput.literal: Any` in
  `contract.py`, judged contained by `ResolvedValue.value: ParamValue` downstream but not
  constructed.
- **Conformance** (`conformance.py`, `modulespec.py`, M0102–M0107) and **gates** were read, not
  attacked.
- **Frontend, API, forge** do not exist. **Toolchain and C1–C4** excluded by the brief.
