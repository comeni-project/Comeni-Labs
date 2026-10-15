# Facts a step needs — design

Issue [338](https://github.com/comeni-project/Comeni-Labs/issues/338) (decided), defect
[340](https://github.com/comeni-project/Comeni-Labs/issues/340), toward the I.0 exit criterion
under [321](https://github.com/comeni-project/Comeni-Labs/issues/321). Code baseline: branch
`fix/i0-walk-findings` at `3c6e9228`. The run-time measurement that removes the question for good
is [339](https://github.com/comeni-project/Comeni-Labs/issues/339), deferred.

## 1. What a researcher gets

Given a sample, the builder asks nothing a file or their sentence answers. What nothing here can
measure (on the RNA-seq spine, strandedness) is not asked before the build. The step that
depends on it stops on the board as tier 4: *featureCounts counts reads by strand; your library's
strandedness is not known. Forward, reverse or unstranded?* The answer is recorded as a fact
about their data, and the pipeline follows. A pipeline is never emitted with a tool quietly
choosing a value nobody gave it.

## 2. What is wrong today

A step reads two kinds of thing: **files**, through the ports its contract declares, and
**facts about the sample**, from the label nf-core modules carry beside each sample's files
(`meta`). A missing file is a gap the engine asks for. A missing fact is not noticed:

- strandedness is declared with `meta_key: strandedness` and no rule reads it (the
  `param: strandedness` rule was removed as a fake decision: `registry/rules/alignment.yml`);
- an open value leaves `meta.strandedness` unset (`MeasurementRegistry.meta_sources_by_type`
  skips it, and calls that silence "the honest default");
- the module then picks for the person: `subread/featurecounts/main.nf:26`
  `def strandedness = 0` counts unstranded, and `hisat2/align/main.nf:30` passes no
  `--rna-strandness`.

The protocol's tier table (`docs/explanation/authoring-protocol.md`, *How a fact's source reaches
the tiers*) sends an open fact to tier 4 only when **a rule reads it**; a fact no rule reads is
*"1 or 2 as today"*. That row is the hole.

## 3. Choices agreed with the operator

| Question | Choice |
|---|---|
| The bar | Given a sample, ask nothing a file or the sentence answers; leave what nothing here can measure as tier 4 on the board (#338). |
| Strandedness for now | Not asked in gathering; open; tier 4 at the steps that need it. Measured at run time later (#339). |
| The concept | **A step declares the facts it needs, the way it declares the files it needs.** How a known fact reaches the tool (the `meta` label) is unchanged and stays internal. |
| Where it is decided | In the **contract and the resolver** (option A), so the tier is the same from the CLI, the browser and a self-hosted install (invariant 13), recorded, and replayed. Not in the API alone (option B), which would leave the CLI emitting `-s 0`. |

## 4. The declaration

`ModuleContract` gains:

```yaml
needs: [strandedness]        # facts this step reads; each a declared measurement id
```

- `needs: list[MeasurementId] = []`, sorted when serialised. Each id must be a declared
  measurement (closed vocabulary, invariant 7); an undeclared one fails to load with a coded
  diagnostic (new, `MD02xx`, declared in `diagnostics.yml`).
- A contract needs a fact **only if its module cannot run correctly without it**. A module
  that reads a label it can do without (`meta.id`, `meta.single_end`, which `_ALWAYS_SET` already
  names) does not declare it.
- On the spine: `nf-core/subread/featurecounts` and `nf-core/hisat2/align` declare
  `needs: [strandedness]`. STAR does not read it (its module has no `strandedness`), so it never
  stops for it.
- The registry change is a PR to `comeni-registry` (two `contract.yml` files), landed before the
  submodule pointer moves here. Registry data is CC-BY-4.0, unchanged.

## 5. Conformance checks the declaration against the code

`mendel conformance` and the build's own check already parse each module's label reads
(`ModuleSpec.meta_reads`, `mendel_compiler/conformance.py`). Two new findings beside `MD0106`:

- **A module reads `meta.<key>` for a declared measurement its contract does not `need`.** A
  warning, not a refusal: reading a label is not proof the tool cannot run without it. The fix
  text says to declare the need or accept the module's default knowingly. This is what would
  have flagged featureCounts.
- **A contract `needs` a fact whose `meta_key` its module never reads.** A refusal: the
  declaration claims a dependency the code does not have. Skipped (`unverified`) when the module
  source is unreadable, as `MD0106`'s unused direction already is.

## 6. The resolver: an open need is tier 4

In `mendel_resolver.resolve`, for each chosen contract, for each fact it `needs`:

- **Known** (in the profile, from any source: measured, said, read by AI): nothing new is
  recorded. The value still reaches the tool through `meta_for`, exactly as today.
- **Open**: the step gets a tier-4 decision, a new record `NeedDecision(_Decided)` in
  `comeni_core/plan/decision.py`, keyed `<node>.needs.<measurement>`, with `unknown=[measurement]`
  and `candidates` = the measurement's declared values (`forward`, `reverse`, `unstranded`).
  It is flagged like every tier 4 (invariant 6) and listed in `needs_review()`.

There is nothing to replay: answering it records the **fact** in the goal's profile, and the
re-resolved pipeline then has no open need and no record. A `NeedDecision` exists only while the
fact is open.

## 7. The walk: the card already asks for facts

`mendel_authoring.needs.need_of` reads a step's open tier-4 records; a record with `unknown`
facts makes it `NeedKind.FACT`, and `stages/building/cards.py` offers *tell me* for each
(`fact_<measurement>`), recorded as the fact. Today only `ProducerDecision.unknown` is read; it
reads `NeedDecision.unknown` too. The card's reason is the record's: *featureCounts reads
strandedness, and it is not known.* Under *Set it up, stop only where you need me*, this step
stops; nothing else changes.

## 8. Gathering: do not ask what only a step needs

`mendel_api/services/gaps.py` asks every measurement a rule reads, and every `meta`-carried
measurement of a leaf type. A measurement is **not** a gathering gap when all of these hold:

- no rule's `when` reads it (it is not a premise, so asking it changes no routing);
- no trusted inspector measures it (a sample could not answer it);
- it is not already known.

It is left open, and the step that needs it stops (§6). On the spine that is strandedness alone:
read length is a premise and measured, pairing and quality encoding are measured. Typed words
can still state it at any time, through the chat's `facts`, which records it before the walk
reaches the step.

## 9. The guard

`tests/guards/`: **no emitted pipeline contains a step whose contract `needs` a fact that is
open in its goal without a tier-4 record for it.** Built over every contract in the shipped
registry with the fact removed from the example goal. It must be watched failing against today's
code, where featureCounts emits `-s 0` with no record (A14), and recorded in
`tests/fixtures/guard-ledger.md`.

## 10. What `pipeline.yml` records

A tier-4 `NeedDecision` is a decision record like the others and is written where they are. If a
new record kind needs a schema change, it lands **with Plan B's version 7** (Part I.0, the save
file), not as a version of its own: two version bumps in one week would give upgraders two
migrations for one release. If Plan B is not ready when this is, the plan says so and the operator
chooses between waiting and a version 7 that Plan B then extends.

## 11. Testing

- `comeni-core`: a contract with an undeclared need fails to load; `needs` round-trips sorted.
- Conformance: featureCounts' module reading `meta.strandedness` without `needs` warns; a
  `needs` whose key the module never reads refuses; unreadable source is `unverified`.
- Resolver (pure, golden): the spine with strandedness open has tier 4 on featureCounts and
  HISAT2 align, `unknown == ["strandedness"]`, candidates the declared values; with strandedness
  `reverse`, no `NeedDecision` and byte-identical `.nf` to today (invariant 10).
- `mendel-authoring`: `need_of` returns `NeedKind.FACT` for a step with an open need.
- `mendel-api`: gathering does not ask strandedness for counts; the walk stops at featureCounts
  with *tell me*; answering `reverse` records the fact and re-resolves; the chat stating it before
  the walk means the step does not stop.
- The guard (§9), watched failing.
- `make verify` (it touches `resolve.py` and the compiler), and the walk in §12.

## 12. Done when (the walk)

One sentence (*gene counts from paired-end RNA-seq of yeast*) plus the walk sample
(nf-core test data `SRR6357070_1/_2.fastq.gz`, 101 bp, paired) uploaded on the reads question:

- read length, pairing and quality encoding are measured, not asked;
- the genome and the annotation are answered by upload or *I have it*;
- strandedness is not asked; under *Set it up* the build stops only at featureCounts for it;
- answering it, the pipeline completes; *Keep* emits `.nf` with `-s` set from the answer;
- nothing in the conversation was asked that the sentence or a file answered.

## 13. Not here

- Measuring strandedness at run time (#339).
- The model approving steps (#336) and quote scope (#337): protocol choices pending, and they
  touch the same walk, so they are better decided first.
- Prompt quality (#327).
- Declaring needs for contracts off the spine: the guard reports them; each is a registry change.
