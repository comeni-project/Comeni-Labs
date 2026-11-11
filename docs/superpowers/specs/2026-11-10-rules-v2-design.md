# Rules v2: settings from facts, hit policies and table checks

Part 3 of #463, issue #461. Follows tool constraints phase 2
([its design](2026-11-10-tool-constraints-phase-2-design.md)).

## Why

The goal for #463 parts 2–5 (operator, 2026-11-10): import a tool easily, and the builder then
really builds with it. Phase 2 made real tools describable. This part makes the settings that
depend on the data decidable by declared rules that a person can read and the engine can check,
instead of living in module code, flags and prose. The operator left the example to me, asking
only that it is intuitive to use and works.

**What exists** (`packages/mendel-resolver/src/mendel_resolver/rules/`): decision tables per
target (a role's implementation, presence or one parameter), rows matched first-to-last,
derived facts (`derives:` with rows, a cohort aggregate or a chain of arithmetic transforms
including `log2`, `at_most` and `at_least`), a per-row `because`/`cite`, a domain check on a
parameter's `then`, and a gap check for tables over a single fact (`MD0311`). The forge drafts
decision tables (`rules:rule:<role>`) but not derived facts.

**What is missing for the goal:**

1. **A setting cannot take its value from a fact.** `then` is a literal; a value computed from
   a measurement is refused (`MD0300`, "that is issue #39"). STAR's `--genomeSAindexNbases` is
   `min(14, log2(genome_length) / 2 - 1)`. The derived fact can already be computed, but no
   rule can hand it to the tool.
2. **Checks stop at one-fact tables.** A table over two facts is not checked for gaps; no table
   is checked for overlapping or dead rows; the hit policy (first match) is implicit.
3. **A rule's value is not checked against the tool's constraints** (#460): a rule can set a
   param to a value whose constraint row then refuses the build.
4. **The forge cannot draft a derived fact**, so a tool whose setting depends on one cannot be
   imported in full.

## The demo (my call)

STAR's genome index. STAR is curated and in the RNA-seq example, so the builder shows it in
every RNA-seq build. Its index-size setting depends on genome length, which nf-core's module
works out internally where nobody sees it. With this part:

- a derived fact `star_sa_index_nbases` is `genome_length` → `log2` → `divide 2` →
  `subtract 1` → `at_most 14` → `round`, as nf-core's module computes it, cited to STAR's
  manual. `round` is a new transform op (no operand): an integer setting needs a whole number;
- a decision sets STAR genomegenerate's `sa_index_nbases` from that fact;
- the step card says "genomeSAindexNbases = 6, from genome length 29,903 bp (stated), per
  STAR's manual", and the person can override it like any setting.

`genome_length` is assertion-only today (a person states it). Part 4 (#465) measures it; until
then the decision reads a stated fact and says so.

## Goals

- **A. `then` from a fact.** A row's `then` may be `{fact: <id>}`: the value of a measurement or
  derived fact. Load checks the fact exists and that its kind fits the parameter's domain
  (integer to integer, number to number; an enum's values within the domain's). At resolution
  the value is the fact's value; the reason names the fact and its value.
- **B. A declared hit policy.** A decision may say `hit: first` (the default, today's
  behaviour) or `hit: unique` (at most one row may match). Under `unique`, two matching rows at
  build time is a tie, and a tie becomes a tier-4 question (invariant: a tier-3 miss or tie
  becomes tier 4). A `unique` decision reading a fact that can differ between samples may not
  overlap at all: that is refused at load (per-sample design, D; operator, 11-11).
- **C. Table checks over several facts.** Load tries representative cases built from the
  rows' own conditions (each enum value and boolean; for an ordered fact, a point below, at
  and above each boundary), bounded like the constraint check:
  - **gap** (`MD0311`, extended): a case no row matches, when no row is a catch-all;
  - **overlap** (`MD0322`, new): under `unique`, a case two rows match;
  - **dead row** (`MD0323`, new): under `first`, a row that is first for no case;
  - **too many cases** (`MD0324`, new): refused rather than checked partly.
- **D. A rule's value against the tool's constraints.** For a `param` decision, each literal
  `then` is evaluated with the implementations' constraints (`comeni_core.declared.constraints`).
  A value that no setup allows is refused at load, with the row's sentence.
- **E. The forge drafts derived facts and these tables.** A new item kind
  `rules:derive:<fact>` (a `Derivation`); the item guide shows `{fact: ...}`, `hit`, and the
  STAR example; forge checks report the table findings.
- **F. The builder shows it.** A setting decided from a fact shows the fact, its value and its
  source (measured, stated, derived), through the existing reason path.

## Non-goals

- Lists and quantities with units as values, choosing a set of tools, and a decision feeding
  two steps' parameters from one decided value: proteomics needs from #461. They wait for a
  pipeline that needs them; recorded on #461.
- Per-sample decisions (part 5, #466) and run-time decisions (part 4, #217/#465).
- Rules reading `given.`/`param.`/`type.` facts. Contract constraints read those; a rule reads
  measurements, derived facts and goal facts, as today.
- A new expression language. Derivations keep their closed operation list, plus `round`.

## Anti-goals

- A value reaching a tool that nobody can trace: every `{fact: ...}` value carries the fact's
  provenance into the setting's reason.
- A check that reports clean over cases it did not try.

## Constraints

- `mendel-resolver` stays pure. Same inputs and recorded decisions reproduce the output.
- Existing rule files (the registry's `rules/alignment.yml`) load unchanged and keep their
  digests: `hit` defaults to `first`, and `then` stays a literal unless written as `{fact:}`.
- Diagnostics are declared in `diagnostics.yml` and emitted through `coded()`.

## Design

### A. `then: {fact: <id>}`

- `DecisionRow.then: ParamValue | FactRef`, where `FactRef` is `{fact: MeasurementId}`.
- Load (`rules/validate.py`): only on a `param` effect; the fact is a declared measurement or
  a derivation in the stack; its kind fits the param's domain. `MD0300` stays for an
  expression written as a string.
- Resolution (`RuleTable._for` and `value_for`): a `FactRef` resolves to the premise's value; a
  missing premise means the row does not fire (as a missing `when` premise does today), so the
  decision falls to the next row or to tier 4.
- The pin records the fact as a premise read, so the reason line names it.

### B. `hit`

- `Decision.hit: Literal["first", "unique"] = "first"`, left out of the dump when `first`.
- `_for`: under `unique`, collect every matching row; two or more is an `AmbiguityResolver`
  question at tier 4, offering the rows' values.

### C. The table check

- `rules/validate.py` gains `check_table(decision, measurements) -> list[str]` (coded
  messages), replacing `_check_exhaustive`'s single-fact path while keeping its messages for
  that case.
- Cases: the product, over the facts the rows read, of each fact's representative values. A
  case missing a fact is not generated: a missing premise is tier 4 by design, not a gap.
- Bound: 4096 cases, as the constraint check.

### D. Constraints

- For each literal `then` of a `param` decision, for each implementation that declares the
  param: `evaluate(contract, Setup(given=required ports, unknown=optional ports,
  params={name: then}))`. A `forbidden` naming the param in every world is `MD0325` at load.

### E. Forge

- `rules:derive:<fact>` joins `_FAMILIES` (value: a `Derivation`), assembled into the rule file's
  `derives:`.
- Item guide v4 and the next draft prompt: `{fact:}`, `hit`, derived facts, the STAR example.
- Forge checks call the table check and the constraint check on drafted rules.

### F. Builder

- The setting's reason already lists the premises a pin read. A `FactRef` adds the fact as a
  premise, so the step card shows it with its source. Verify on the step view; change only what
  a test shows is missing.

## Proof

- STAR genomegenerate with a `sa_index_nbases` param (test overlay) and the STAR rule: built from
  a goal stating `genome_length: 29903` emits `--genomeSAindexNbases 6`, and from
  `3_100_000_000` emits `14`.
- A two-fact table with a gap, an overlap under `unique`, and a dead row under `first`, each
  refused with its code.
- A rule setting a param to a value a constraint forbids, refused.
- The forge drafts the STAR derivation and rule from a recorded reply.

## Left to the builder

- Diagnostic wording, per `docs/design/voice.md`.
- How representative points are spaced, as long as each boundary is tested on both sides.
