# Tier-3 rule tables and port expressiveness

**Date:** 2026-08-03
**Status:** Approved. Not yet implemented.
**Extends:** [`2026-08-02-mendel-design.md`](2026-08-02-mendel-design.md) §5.1, §6.1–6.3.
**Related:** [`2026-08-03-clinical-data-protection-design.md`](2026-08-03-clinical-data-protection-design.md)
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

---

## 2. Why this exists

Five rules ship in `examples/rules/rnaseq.yml`. **Two of them have never once executed**, and
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
  `IRNode` has no tier field, so only parameters are tiered. §6 below fixes this.
- **`state_preferred` is dead.** Declared on `InputPort`, validated at load, never read. §7 gives
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
```

One block per decision, rows underneath. The three strandedness rules were one concept split
across three entries repeating their subject and citation; a reviewer should read the
justification once and then read the branches. Grouping also lets a reviewer notice a **missing**
branch, which flat rules actively hide.

`because` and `cite` sit on the block and may be overridden per row.

---

## 4. Matching

**Conditions.** `when` maps a `DataProfile` field to either a bare value, meaning equality, or a
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
| every field in a `when` | not a field of `DataProfile` |
| two blocks, one target, one layer | duplicate decision |

**The error message is the feature.** A rule table that will not load must say what the author
can write, not that a lookup failed:

```
examples/rules/rnaseq.yml, decision 2 — {param: aligner}
  No contract in the registry declares a parameter named 'aligner'.
  Registry layers searched: examples/contracts
  Parameters that do exist:  seq_platform, strandedness
```

The last line carries most of the value. Every validation class gets a message of this shape and
a test asserting it names the offending thing.

**A rule table is only valid against a registry that can satisfy it.** Rules and contracts are
coupled data. The shipped example currently violates this — `nf-core/hisat2/align@2.2.1` is not
in `examples/contracts` — and under this design the file refuses to load. Since v1 scope excludes
alternative aligners, the HISAT2 row is dropped rather than the module vendored. The aligner
decision then has a single row, which demonstrates fallthrough honestly: reads under 70bp match
nothing and the choice lands at tier 2 by ranking instead of tier 3 by rule.

---

## 6. Module pinning, and a tier for every choice

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

## 7. Ports in disjunctive normal form

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

## 8. Layer composition

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

## 9. Impact on code

| File | Change |
|---|---|
| `mendel_resolver/rules.py` | `Rule`/`RuleTable` become `Decision`/`DecisionRow`/`RuleTable`; `match()` splits into `value_for(param, profile)` and `producer_for(type_id, profile)`; `load` gains layers, registry and vocab and validates |
| `mendel_resolver/router.py` | consults `producer_for` before ranking; alternatives in declaration order; `prefer` as tiebreak; a pin that cannot route raises |
| `mendel_resolver/resolve.py` | tier-3 branch calls `value_for`; populates `IRNode.selection` |
| `comeni_core/ir.py` | `IRNode.selection: ResolvedValue` |
| `comeni_core/contract.py` | `InputPort.accepts` and `prefer`; existing form kept as sugar |
| `examples/rules/rnaseq.yml` | five flat rules become two decision blocks; HISAT2 row dropped |

No package gains a dependency. Nothing here touches an egress door, a model, or the network, and
`tests/test_purity.py` and `tests/test_egress.py` must pass unchanged.

---

## 10. Testing

- **Golden file** — rules YAML in, parsed table out, byte-identical
- **One test per validation class**, each asserting the message names the offending thing and
  lists the valid alternatives
- **Determinism** — same profile, same decision, across repeated calls
- **Tier assignment** — one test per row of §6's table
- **Pin failure** — an unroutable pin raises and the error names the rule
- **Alternatives** — a port accepting BAM-or-CRAM routes from either, and records which
- **The shipped example rules load against the shipped example registry.** One line, and it is
  what makes a dead rule impossible to ship again

---

## 11. Open questions

- **Rule provenance.** Contracts carry `provenance` with `approved_by` and `approved_at`. Rules
  carry `cite` but no approval record, and the forge will need one. Deferred to Plan 2, where the
  approval queue exists to write it.
- **Profile fields are fixed.** `DataProfile` has four measurements, so `when` can only reason
  about four things. Adding a fifth is a code change to a pure package, which sits awkwardly
  beside "rules are data". Whether the profile should itself be declared data is unresolved.
- **Ranking policies.** Issue #1 proposes that candidate ordering vary by purpose. A named policy
  and a rule-pinned producer both decide the same thing, and the interaction needs settling before
  both exist.
- **`prefer` across alternatives.** Preference is defined within a matched alternative. Whether a
  preferred state should ever promote a *later* alternative over an earlier one is left open;
  the answer is probably no, but no case has been examined.
