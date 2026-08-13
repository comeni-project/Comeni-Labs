# Tier-3 rule tables and port expressiveness

**Date:** 2026-08-03
**Status:** Approved. Not yet implemented.
**Extends:** [`mendel.md`](mendel.md) §5.1, §6.1–6.3.
**Related:** [`clinical-data-protection.md`](clinical-data-protection.md)
— rules and contracts are registry data, so everything here ships under CC-BY-4.0 and crosses no
egress door.

Two changes to the layer where a domain expert writes things down: the tier-3 rule table, and
what a contract port may require. They share a document because they are the same problem — the
declarative layer is not yet expressive enough to say what practitioners mean — and because both
touch routing.

---

## 1. The decisions

| Question | Decision |
|---|---|
| Rule file shape | Grouped decision tables: one block per decision, rows underneath |
| What a rule may decide | Exactly two targets: a parameter value, or the producer of a type |
| Module rules | **Pin** the producer, recorded at tier 3 with rule and citation |
| Conditions | Bare value for equality, comparison string otherwise. AND within a row |
| Row order | Significant. First match wins |
| Dead rules | Impossible — every rule is validated against the registry at load |
| Layer composition | Whole block replaces, keyed on the decision target, and is recorded |
| Layer ceremony | **None.** A rule file says nothing about layers |
| Port logic | Disjunctive normal form, one level: a list of alternatives, AND within each |
| `state_preferred` | Renamed `prefer`, and finally used — the tiebreak within a matched alternative |
| What a rule may reason about | Declared measurements, not hardcoded `DataProfile` fields |
| Measurement kinds | `integer`, `number`, `boolean`, `enum`. **No `string`** |
| Enum extension | Closed by default; a declaration may opt into `extensible` |
| Measurement versioning | None. The id is the meaning; changes get a new id and `replaced_by` |
| Static typing | Generated stubs — derived, never authoritative, safe when stale |

---

## 2. Why this exists

Five rules ship in `registry/rules/rnaseq.yml`. **Two of them have never once executed**, and
nothing said so:

- `subject: aligner` — `RuleTable.match` is called with parameter names taken from contracts, and
  no contract declares a parameter called `aligner`. The lookup never happens.
- `then: {module: ...}` — `_resolve_param` reads only `then["value"]`. The module form is ignored
  even when reached.

So the canonical tier-3 example from spec §6.2, `read_len >= 70 → STAR`, does not work. Module
selection by measured data — the thing the product is named after — is designed and unbuilt,
while the router picks modules by registry priority alone.

The root cause is that `subject` is an unvalidated free string. Any format that keeps that
property will grow dead rules again, so validation against the registry is the load-bearing part
of this design and the syntax is downstream of it.

Two further gaps close as a consequence:

- **Module choices carry no tier.** Spec §6.1 says every module choice exits at exactly one tier;
  `IRNode` has no tier field, so only parameters are tiered. §7 below fixes this.
- **`state_preferred` is dead.** Declared on `InputPort`, validated at load, never read. §8 gives
  it a job.

---

## 3. The rule file

```yaml
version: 1
decisions:
  - decides: {param: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - when: {strandedness: reverse}     then: 2
      - when: {strandedness: forward}     then: 1
      - when: {strandedness: unstranded}  then: 0

  - decides: {producer_of: alignment.bam}
    because: "read length determines which aligner is appropriate"
    cite: "Dobin et al. 2013, doi:10.1093/bioinformatics/bts635"
    rows:
      - when: {read_length: ">= 70"}  then: nf-core/star/align@1.11.0
      - when: {read_length: "< 70"}   then: nf-core/hisat2/align@2.2.2
```

One block per decision, rows underneath. The three strandedness rules were one concept split
across three entries repeating their subject and citation; a reviewer should read the
justification once and then read the branches. Grouping also lets a reviewer notice a **missing**
branch, which flat rules actively hide.

`because` and `cite` sit on the block and may be overridden per row.

---

## 4. Matching

**Conditions.** `when` maps a declared measurement (§6) to either a bare value, meaning equality, or a
string beginning with a comparison operator:

```yaml
when: {strandedness: reverse}                    # equality
when: {read_length: ">= 70"}                     # comparison
when: {read_length: ">= 70", paired: true}       # AND
```

Supported operators are `>=`, `>`, `<=`, `<`, `==`, `!=`. The nested `{">=": 70}` operator map is
withdrawn; it existed because it was trivial to parse, at the reader's expense.

**All conditions in a row must hold.** There is no OR within a row — that is what additional rows
are for, and keeping it that way is what makes a decision table readable as a table.

**Row order is significant and first match wins.** A row referencing a field the profile has not
measured does not match. When no row matches, the decision falls through to the next tier, which
is the correct and common case: tier 3 has no opinion, so tier 2 or tier 4 answers.

---

## 5. Validation against the registry

`RuleTable.load(layers, registry, vocab)` rejects a table that cannot fire. This is the part that
makes §2's bug structurally impossible rather than merely fixed.

| Check | Failure |
|---|---|
| `{param: X}` | no contract in the registry declares a parameter `X` |
| `{producer_of: T}` | `T` is not a type in the vocabulary |
| `then:` of a `producer_of` block | contract id absent from the registry, or does not produce `T` |
| every key in a `when` | not a declared measurement |
| a comparison on an `enum` | operators other than `==`/`!=` on a non-ordered kind |
| two blocks, one target, one layer | duplicate decision |

**The error message is the feature.** A rule table that will not load must say what the author
can write, not that a lookup failed:

```
registry/rules/rnaseq.yml, decision 2 — {param: aligner}
  No contract in the registry declares a parameter named 'aligner'.
  Registry layers searched: registry/contracts
  Parameters that do exist:  seq_platform, strandedness
```

The last line carries most of the value. Every validation class gets a message of this shape and
a test asserting it names the offending thing.

**A rule table is only valid against a registry that can satisfy it.** Rules and contracts are
coupled data, and the worked example proved it: the short-read row named a HISAT2 contract that
did not exist, so under this design the file would refuse to load. `hisat2/align` and
`hisat2/build` were vendored on 2026-08-03 rather than the row dropped, because a pinned producer
that cannot route is a build failure by design — a short-read rule resolving to an aligner with no
index builder would be a trap rather than a branch.

---

## 6. Measurements are declared data

### 6.1 The problem this solves

`DataProfile` is a Python class with four fields, so `when` can only ever reason about read
length, strandedness, sample count and paired-ness. Adding `organism` means editing `goal.py`:
a change to a pure package, a version bump, a release — something a bioinformatician cannot do
and a curator cannot approve through the forge queue.

So the tier-3 promise is *"rules are data a domain expert adds"* and the reality is *"as long as
they only reason about four things somebody hardcoded"*. The first real rule table written by a
laboratory hits this immediately.

### 6.2 The declaration

`registry/measurements/`, one file per measurement, named by id — the convention `vocabularies/`
already uses.

```yaml
# registry/measurements/strandedness.yml
kind: enum
values: [forward, reverse, unstranded]
description: "Library strandedness determined by the prep protocol"
cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"
edam: "http://edamontology.org/data_3125"      # optional, where a term exists
```

```yaml
# registry/measurements/read_length.yml
kind: integer
minimum: 1
unit: bp
description: "Sequenced read length"
```

**`kind` is closed: `integer`, `number`, `boolean`, `enum`. There is deliberately no `string`.**
This is the load-bearing decision. A free-text measurement is precisely the hole
`tests/test_egress.py` exists to close — `organism: "patient 4471023's tumour"` is a valid string.
A categorical measurement declares its values instead, so there is nowhere for prose to go, and a
rule over an enum can be checked for exhaustiveness in a way free strings would prevent.

### 6.3 Enum extension is per-measurement

Whether an enum may grow is a property of the measurement, because the semantics genuinely
differ. `strandedness` has exactly three values and a fourth is a bug. `organism` can never be
enumerated and a registry that tries is wrong.

Closed is the default. A declaration may opt in:

```yaml
kind: enum
extensible: true
values: [homo_sapiens, mus_musculus]
```

Only then may an overlay contribute `add_values: [ambystoma_mexicanum]`. The effective set is the
union, and each added value records the layer that added it. A closed enum is changed the way
everything else is — by shadowing the whole declaration.

### 6.4 Measurements are not versioned; the id is the meaning

A measurement whose meaning changes gets a **new id**. The old declaration remains forever,
marked `deprecated` with `replaced_by` naming its successor:

```yaml
# registry/measurements/read_length.yml
kind: integer
deprecated: true
replaced_by: read_length_median
description: "Ambiguous between mean and median across samples. Use read_length_median."
```

A rule using a deprecated measurement still loads and warns, naming the replacement.

This is [OBO practice](https://oboacademy.github.io/obook/howto/obsolete-term/) — never reuse an
identifier, keep obsolete terms indefinitely, point at the successor — which the ontologies this
registry already cites have used for two decades. Per-measurement `@version` was considered and
rejected: every rule condition would grow a version, and omitting one would silently mean
*latest*, which is the ambiguity versioning was supposed to remove.

### 6.5 `DataProfile` becomes a validated map

```python
class DataProfile(BaseModel):
    measurements: dict[MeasurementId, MeasurementValue] = {}
```

Keys must be declared; values must satisfy their declaration. A `model_validator(mode="before")`
accepts the existing mapping form, so **no goal file and no existing call site changes**:

```yaml
profile: {read_length: 150, strandedness: reverse}   # unchanged
```
```python
DataProfile(read_length=150, strandedness="reverse") # unchanged
```

Validation needs the measurement registry, which the model cannot hold, so it happens through
Pydantic validation context at a single construction point.

Note that a profile cannot cross an egress door as a map: `tests/test_egress.py` forbids any
mapping in a payload, because a typed key does not prove a *declared* key. A payload carrying
measurements carries a list of declared records instead.

**That single point is enforced, not documented.** `DataProfile` is constructible only through
`MeasurementRegistry.profile(...)`, and an AST test asserts nothing else calls `DataProfile(` or
`model_validate` on it — the third instance of the pattern `tests/test_purity.py` and
`tests/test_egress.py` already use. Without it, a second construction path skipping the context
would produce an unvalidated profile that flows straight into routing, which is exactly the class
of silent failure that left `subject: aligner` dead for months.

### 6.6 Static typing is generated, derived, and safe when stale

Losing `profile.read_length: int` is the real cost. It is recovered with a generated `.pyi` stub
carrying `Literal` overloads, most-specific first:

```python
@overload
def get(self, id: Literal["read_length"]) -> int | None: ...
@overload
def get(self, id: Literal["strandedness"]) -> Literal["forward", "reverse", "unstranded"] | None: ...
```

The same generator emits a `.d.ts` for the frontend, and `mendel-api` serves the declarations so
the dashboard renders profile forms from them — both Plan 3, tracked as
[#3](https://github.com/comeni-project/Comeni-Labs/issues/3) — which means a laboratory's own measurements appear
in the UI without a rebuild, better than the fixed struct it replaces.

Three properties make this safe:

- **Generated artifacts are never authoritative.** Runtime validation against declarations is the
  only truth. A stale stub costs autocomplete, never correctness.
- **Nothing is required to run the generator.** A lab declaring `organism.yml` gets full
  validation immediately and autocomplete whenever someone regenerates.
- **CI fails if regenerating the curated stubs produces a diff**, so rot is loud rather than
  silent.

A mypy plugin was considered and rejected: it would never go stale, but
[pyright does not support plugins by design](https://github.com/microsoft/pyright/blob/main/docs/mypy-comparison.md),
and pyright is Pylance, so most users would get nothing. [PEP 728](https://peps.python.org/pep-0728/)
closed `TypedDict` is a better output format than overloads and is Final for Python 3.15, but mypy
does not implement it yet. It is a future emit target, not a different design — the generator's
output shape is one commit to change because nobody hand-edits it.

### 6.7 Vocabularies must become layered too

`Registry.load` takes layers; `Vocabulary.load` takes a single path. A laboratory declaring a
measurement in its own overlay needs measurements to layer, and by the same argument a laboratory
adding a *state* needs vocabularies to layer. Both become layered, keyed on id, with shadowing
recorded as contracts already do. Small now, awkward later.

## 7. Module pinning, and a tier for every choice

A matching `producer_of` row **pins** the contract that satisfies that type for this build. The
router uses the pin instead of ranking candidates.

`IRNode` gains `selection: ResolvedValue` — the value/tier/reason shape parameters already carry —
so every module choice exits at exactly one tier, which is what spec §6.1 has always claimed:

| How the module was chosen | Tier | Review level |
|---|---|---|
| only one contract can produce the type | 1 structural | `none` |
| a rule pinned it | **3 data-profiled** | `advisory` |
| several candidates, resolved by priority | 2 convention | `none` |
| candidates tied | 4 ambiguous | `required` |

A tier-3 selection carries the rule id and citation in its `reason`, exactly as a tier-3 parameter
does, so the generated `.nf` comment says which paper chose the aligner.

**A pin that cannot route is an error.** If a rule pins STAR and STAR's inputs are unreachable,
the build fails naming the rule and the unsatisfiable input. Falling back to another producer
would mean the rule said one thing and the pipeline did another, silently — the failure this
product exists to remove.

---

## 8. Ports in disjunctive normal form

Today `InputPort.state_required` is a `frozenset` matched by subset test, so a port can only
express AND. Practitioners routinely mean OR — *"a coordinate-sorted BAM or CRAM"* — and have no
way to say it.

A port gains `accepts`: an ordered list of alternatives, each an AND of type and states.

```yaml
consumes:
  - name: bam
    accepts:
      - {type_id: alignment.bam,  states: [coordinate_sorted]}
      - {type_id: alignment.cram, states: [coordinate_sorted]}
    prefer: [indexed]
```

Read as *"coordinate-sorted BAM, or coordinate-sorted CRAM."* The existing
`type_id` + `state_required` form remains as sugar for a single alternative, so no contract has to
change.

**Routing tries alternatives in declaration order** and takes the first that can be satisfied. The
matched alternative is named in the route step, so a decision record can say *why* — which is what
full boolean logic would have cost.

`prefer` replaces the dormant `state_preferred`, and becomes the tiebreak **within** a matched
alternative: among candidates satisfying the same alternative at the same priority, one producing
a preferred state wins. It never causes insertion and never causes failure, matching spec §5.1.

**`prefer` never promotes a later alternative over an earlier one.** Alternative order is the
author's statement of preference between kinds of input; `prefer` discriminates within one kind.
The reason is consistency rather than principle: `rows` in a decision table are ordered and
first-match-wins, and `accepts` is the same structure one layer down. One mental model used twice
is worth more than the expressiveness given up, and if preference could reorder alternatives then
"why did it choose CRAM" would need a paragraph instead of a line.

Making alternatives unordered, with two satisfiable ones demoting to tier 4 under invariant 8, was
considered. It is more consistent with how ties are treated elsewhere, but it would flag red
whenever both a BAM and a CRAM producer exist — noise for a case where authors nearly always do
have a preference, and YAML forces them to write one anyway.

### Full boolean logic was considered and rejected

Arbitrary AND/OR/NOT with nesting would express more, and would cost the thing the product sells.
Today *"why is `SAMTOOLS_SORT` here?"* answers itself in one sentence. Under a general constraint
language it becomes a solver trace, and *"every decision traces to a constraint"* degrades into
*"every decision traces to a solver run"*. Nesting also brings unsatisfiable-combination detection
and an ordering semantics nobody can hold in their head.

One level of DNF covers the cases that actually arise — alternative types, alternative state sets
— and stays explainable in a line. Cross-port conditions (*"needs an index only if the aligner was
STAR"*) are deliberately excluded: those are almost always a missing state in the vocabulary
rather than a missing operator in the language.

---

## 9. Layer composition

`RuleTable.load` takes an ordered list of layers, like `Registry.load`, with precedence from
`--registry` order. A higher layer declaring the same `decides` target **replaces that whole
block** and writes a record naming the target, the winning layer and what it displaced. The CLI
prints these beside the existing `SHADOW` lines.

**A rule file contains no layer metadata of any kind** — no precedence field, no manifest, no
override declarations. An author writes rules and puts the file in a directory. Layering is
positional and belongs to whoever assembles the stack, exactly as it already does for contracts.

Row-level merging was considered and rejected: it would let a lab add one row without restating a
table, but the effective decision would then exist in no single file, and a lower-layer row could
be silently shadowed by an overlapping higher one. Whole-block replacement means a reviewer reads
one block and sees the entire decision. The cost — copying a table to change one row, and then
not receiving upstream improvements to the others — is real, visible, and recorded.

---

## 10. Impact on code

| File | Change |
|---|---|
| `mendel_resolver/rules.py` | `Rule`/`RuleTable` become `Decision`/`DecisionRow`/`RuleTable`; `match()` splits into `value_for(param, profile)` and `producer_for(type_id, profile)`; `load` gains layers, registry and vocab and validates |
| `mendel_resolver/router.py` | consults `producer_for` before ranking; alternatives in declaration order; `prefer` as tiebreak; a pin that cannot route raises |
| `mendel_resolver/resolve.py` | tier-3 branch calls `value_for`; populates `IRNode.selection` |
| `comeni_core/ir.py` | `IRNode.selection: ResolvedValue` |
| `comeni_core/contract.py` | `InputPort.accepts` and `prefer`; existing form kept as sugar |
| `registry/rules/rnaseq.yml` | five flat rules become two decision blocks, both rows live |
| `comeni_core/measurement.py` | new — `Measurement`, `MeasurementRegistry`, layered `load`, `profile()` |
| `comeni_core/vocabulary.py` | `load` takes layers, shadowing recorded (§6.7) |
| `mendel_resolver/goal.py` | `DataProfile` becomes a validated map with a before-validator |
| `registry/measurements/*.yml` | new — the four current fields, declared |
| `tools/generate_types.py` | new — declarations to `.pyi` and `.d.ts`; output is golden-tested |

No package gains a dependency. Nothing here touches an egress door, a model, or the network, and
`tests/test_purity.py` and `tests/test_egress.py` must pass unchanged.

---

## 11. Testing

- **Golden file** — rules YAML in, parsed table out, byte-identical
- **One test per validation class**, each asserting the message names the offending thing and
  lists the valid alternatives
- **Determinism** — same profile, same decision, across repeated calls
- **Tier assignment** — one test per row of §7's table
- **Pin failure** — an unroutable pin raises and the error names the rule
- **Alternatives** — a port accepting BAM-or-CRAM routes from either, and records which
- **The shipped example rules load against the shipped example registry.** One line, and it is
  what makes a dead rule impossible to ship again
- **AST guard** — nothing constructs `DataProfile` outside `MeasurementRegistry.profile`
- **Measurement kinds** — a `string` kind is rejected; an enum rejects an undeclared value; a
  closed enum rejects `add_values`; an extensible one accepts it and records the layer
- **Deprecation** — a rule over a deprecated measurement loads, warns, and names the replacement
- **Generated types** — regenerating the curated stubs produces no diff; a stale stub does not
  affect validation

---

## 12. Open questions

- **Rule provenance.** Contracts carry `provenance` with `approved_by` and `approved_at`. Rules
  carry `cite` but no approval record, and the forge will need one. Deferred to Plan 2, where the
  approval queue exists to write it.
- **If the profile ever crosses an egress door.** Tier-4 resolution plausibly *should* see the
  measurements — "what strandedness is this?" is exactly what you would want a model to know — and
  `AmbiguityRequest` would then carry a measurement map. `tests/test_egress.py` currently forbids
  `Any`-typed and plain-`str` payload fields; it would need teaching that a declared-key,
  declared-value map is acceptable where a free map is not. Nothing crosses today, so this is a
  decision deferred to when it arises, not a gap.
- **Extensible enums and generated types.** An extensible enum's `Literal` union is
  registry-specific, so a laboratory that widens one sees a false type error on correct code until
  regeneration. Acceptable, and the reason generated artifacts are never authoritative.
- **Ranking policies.** Issue #1 proposes that candidate ordering vary by purpose. A named policy
  and a rule-pinned producer both decide the same thing, and the interaction needs settling before
  both exist.
- **Cohort versus sample.** A measurement like `read_length` is per-sample and a rule needs one
  value. Whether that is a mean, a median, or a fan-out is unresolved — see the profiling spec §9,
  where it is the question most likely to change `profile.yml`.

---

## 13. What this format cannot express — written 2026-08-13, before it needed reforming

**Read this before changing the rule format, not while changing it.**

The format in §3 was designed against a registry holding **one** real rule. It has since been
stated that the domain contains *thousands* of tier-3 rules and that most are abstract — which
is the reason the forge needs a model at all, and which means this format will have to evolve.
This section records what it cannot express today and what each repair costs, so that the
reform is a design decision taken deliberately rather than a series of accommodations bolted on
under deadline.

**None of this is a defect.** A format designed against one example, kept deliberately narrow,
and documented as narrow is the correct thing to have built. §8's rejection of full boolean
logic is the same instinct and is still right. The mistake would be discovering these limits
one at a time while the forge is already emitting proposals into them.

### 13.1 What it does express, so the boundary is clear

Rows are conjunctions of `measurement OP scalar`, tried in order, first match wins. Several rows
give disjunction, so the real expressive class is **disjunctive normal form over
(measurement, comparison, literal)**. That is a genuine and useful class: every classification-
shaped rule fits it, and the shipped `producer_of` rule — read length ≥ 70 selects STAR, below
selects HISAT2, citing Dobin — is exactly that shape and works.

The three limits below are not about power for its own sake. Each one has a canonical
bioinformatics rule sitting behind it.

### 13.2 `then` is a literal, never an expression

`DecisionRow.then` is a `ParamValue` and reaches the resolver as `value=row.then`, verbatim.

The canonical counter-example is STAR's `--sjdbOverhang`, whose documented ideal value is
**`max(read_length) − 1`**. That is a tier-3 rule by every definition this project uses: a
measured input, a documented mapping, a real consequence if wrong. It cannot be written. It can
only be *enumerated* — one row per read length the registry anticipates — which turns a rule
into a lookup table and quietly changes what "the rule matched" means.

**What a repair costs.** A computed `then` introduces an expression language into declared data,
and that is a larger decision than it looks: an expression is code, code in the registry is code
a stranger authored, and invariant 1 exists because code from elsewhere is exactly what the pure
packages must not execute. A restricted arithmetic form over declared measurements — no calls, no
attribute access, a closed operator set — is probably the answer, and it must be designed with
`substitutable()` and `MD0221` in view, because a value that reaches `ext.args` is a value that
reaches a shell. **Do not reach for `eval`.** The forge making this easy to generate is precisely
what makes it dangerous.

### 13.3 `when` sees measurements, and nothing else

`when` keys are measurement ids. A rule therefore cannot condition on:

- **Another decision.** "If the aligner is Salmon, then the GTF does not need sorting" is expert
  knowledge with nowhere to live. Decision-conditioned rules are a large slice of what a
  bioinformatician actually knows, and the router resolves module choice *before* parameters, so
  the information exists at the moment a rule would need it.
- **The goal's purpose.** The same measurement implies different values depending on what the
  analysis is *for* — differential expression versus variant calling versus assembly. `Goal` has
  `want` and `constraints`; `when` cannot see either.

**What a repair costs.** Widening `when` beyond measurements means the rule table stops being a
function of the data profile alone, and that has a determinism consequence worth stating: today a
rule's inputs are a closed, declared, content-addressed set. Adding decisions as inputs creates an
ordering dependency between rules, and ordering dependencies are where "same goal in, same
pipeline out" quietly stops being provable. If this is done, it needs a stratification argument —
rules may read decisions from a strictly earlier stage, never from their own.

### 13.4 The completeness problem, which is issue #1 wearing a different hat

**This is the one that surprised us, and it is why §12's "Ranking policies" bullet and §13.3 are
the same finding.**

When several contracts can produce a needed type, the ladder is: a tier-3 `producer_of` rule
decides it with a citation; failing that, the `priority` scalar decides it as tier-2 convention;
failing that — a tie — invariant 8 demotes to tier 4 and a human is asked.

At the spine's scale this is clean: two aligners, one rule, `priority: 10` on STAR as a documented
nf-core convention. At v2 breadth — alternative aligners, pseudo-aligners, UMI handling — it
stops being clean, because **`priority` is a single scalar per contract and is purpose-independent.**
There is no number that makes STAR correct for splice discovery, Salmon correct for fast
transcript quantification and HISAT2 correct on a low-memory machine, because "better" is not a
property of the contract; it is a relation between the contract and the goal.

That leaves three states and none of them is good:

| If the registry author… | Then |
|---|---|
| ranks the alternatives with `priority` | one aligner silently wins every build, presented as *convention* — a guess wearing a tier-2 label, which is what the product claim forbids |
| leaves them equal | every build ties, demotes to tier 4, and asks the user to choose an aligner every time — the review wall |
| writes a `producer_of` rule covering all of them | correct — **and it must be complete over the alternatives, and it inherits §13.2 and §13.3's limits** |

So the third option is the only honest one, and it means: **as the registry grows, every
additional producer of an already-produced type is a liability until a rule covers it.** Adding a
contract can make the pipeline *worse* — by creating a tie, or by falling under a purpose-blind
scalar — and nothing currently warns the author of that.

**Two candidate repairs, and they are not equivalent.** Issue #1 proposes purpose-varying scoring;
§13.3 proposes letting `when` see purpose. They decide the same thing by different mechanisms, and
§12 already flags that the interaction needs settling before both exist. The rule-based route
keeps every module choice cited and auditable, which is the product claim; the scoring route is
cheaper and produces a number nobody can cite. **Prefer the rule.** If scoring is added anyway, it
should be a *tie-breaker of last resort* that still emits a `DecisionRecord`, never a silent sort.

### 13.5 The vocabulary underneath has no author

Every rule keys on a **declared measurement**, so the measurement vocabulary gates the rule table
entirely: a rule that needs an undeclared measurement cannot be written at all.

Thousands of rules implies hundreds of measurements, and each measurement costs two things — a
declaration in `<layer>/measurements/`, and something that actually *measures* it, since
`mendel profile` emits a pipeline that does the measuring.

**Nothing drafts measurements.** Plan 2's forge covers contracts (Task 9), vocabulary states
(Task 10) and parameters (Task 11); there is no measurement drafter and no approval path for one.
This is the quietest of the gaps in this section and probably the most load-bearing, because it
sits *under* every rule the forge will eventually propose: a rule drafter that can only key on
the measurements somebody hand-declared will propose rules about read length and strandedness
for ever.

Tracked as [#38](https://github.com/comeni-project/Comeni-Labs/issues/38); §13.2–13.4 as
[#39](https://github.com/comeni-project/Comeni-Labs/issues/39).

### 13.6 The order these want to be done in

Recorded as a recommendation, not a decision, because the argument may change.

1. **Hand-author ~20 real abstract rules first**, before any drafter exists. They are the test of
   this format, and they cost days rather than a plan. Everything in §13.2–13.4 was reasoned from
   *one* shipped rule; twenty would replace argument with evidence, and the ones that cannot be
   written are the specification for the reform.
2. **Then the measurement vocabulary**, because it gates everything above it.
3. **Then the format reform**, designed against the twenty rules that broke it.
4. **Then a rule drafter** — which Plan 2 already defers past Plan 3, for the different and also
   correct reason that it needs a corpus of real tier-4 flags to learn from.

Doing 4 before 3 means a model generating proposals into a format that cannot hold them, and the
proposals will look plausible, which is the worst failure mode this project has.
