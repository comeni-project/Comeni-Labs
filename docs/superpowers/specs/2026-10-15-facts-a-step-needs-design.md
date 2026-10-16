# What a tool reads must come from somewhere — design

Issue [338](https://github.com/comeni-project/Comeni-Labs/issues/338) (decided), defect
[340](https://github.com/comeni-project/Comeni-Labs/issues/340), toward the I.0 exit criterion
under [321](https://github.com/comeni-project/Comeni-Labs/issues/321). Code baseline: branch
`fix/i0-walk-findings` at `3c6e9228`. The run-time measurement that removes the question for good
is [339](https://github.com/comeni-project/Comeni-Labs/issues/339), deferred.

## 1. What a researcher gets

Given a sample, the builder asks nothing a file or their sentence answers. What nothing here can
measure (on the RNA-seq spine, strandedness) is not asked before the build. Each step that reads
it stops on the board as tier 4: *featureCounts counts reads by strand; your library's
strandedness is not known. Forward, reverse or unstranded?* They answer once; it is recorded as
a fact about their data, and every step that reads it follows. A pipeline is never emitted with a
tool quietly choosing a value nobody gave it.

## 2. The rule

> **Whatever a chosen tool reads — a setting, or a fact about the sample — comes from somewhere:
> the goal, a file, the person, a rule, or a documented default. If nothing supplies it, it is
> tier 4, and flagged.**

For **settings** this already holds: `mendel_resolver.resolve._resolve_param` falls through goal,
rule and default to a tier-4 `ParamDecision`. For **facts about the sample** it does not. A fact
reaches a tool one of two ways:

- **through a rule** (read length chooses the aligner): unknown, the rule cannot match and the
  decision is tier 4. This holds today.
- **on the sample's label**, which nf-core modules read themselves (`meta.strandedness`): unknown,
  the label is simply absent (`MeasurementRegistry.meta_sources_by_type` skips it) and the module
  picks: `subread/featurecounts/main.nf:26` `def strandedness = 0` counts unstranded,
  `hisat2/align/main.nf:30` passes no `--rna-strandness`. **This is the hole** (#340), and the
  protocol's tier table encodes it: a fact no rule reads is *"1 or 2 as today"*.

The fix puts the second way through the same rule as the first.

## 3. Choices agreed with the operator

| Question | Choice |
|---|---|
| The bar | Given a sample, ask nothing a file or the sentence answers; leave what nothing here can measure as tier 4 on the board (#338). |
| Strandedness for now | Not asked in gathering; open; tier 4 at the steps that read it. Measured at run time later (#339). |
| How the engine knows a tool reads a fact | **Derived from the tool's code**, which `ModuleSpec.meta_reads` already parses. No new declaration: a `needs:` field was considered and rejected as a third copy of what the fact's `meta_key` and the module's code already say, kept honest only by a check. |
| Where it is decided | In the resolver, so the CLI, the browser and a self-hosted install agree (invariant 13), and the record is replayable. |

## 4. The resolver is handed what each tool reads, as data

The resolver is pure and does not import the compiler. It does not need an interface either:
`resolve` takes one more argument, a plain mapping.

```python
facts_read: Mapping[str, frozenset[str] | None] | None = None
"""Per contract id, the declared measurements whose `meta_key` its module reads; None for a
contract whose source cannot be read. The argument None: nobody looked (today's behaviour)."""
```

- Computed in `mendel-compiler`, next to conformance, from what it already parses:
  `ModuleSpec.parse(path).meta_reads` (variable `meta`), mapped through the measurements'
  `meta_key`s, minus the keys always set (`conformance._ALWAYS_SET`, today `{"id"}`). Once per
  registry.
- Passed by the two callers that have the stack's modules: the CLI build
  (`mendel_compiler.orchestrate`) and `mendel-api`'s blueprint resolution.
- Sorted when iterated (invariant 10).

## 5. An unsupplied fact is tier 4 at the step that reads it

In `resolve`, for each chosen contract, for each fact its tool reads:

- **Known** (in the profile from any source: measured, said, read by AI): nothing new. The value
  reaches the tool on the label, exactly as today.
- **Unknown**: the step gets a tier-4 decision, `FactDecision(_Decided)` in
  `comeni_core/plan/decision.py`, keyed `<node>.fact.<measurement>`, with `unknown=[measurement]`
  and `candidates` = the measurement's declared values. Flagged like every tier 4 (invariant 6),
  listed in `needs_review()`.
  **Why a new record kind rather than a `ParamDecision`:** a setting's answer is stored as that
  one step's setting, so two steps reading strandedness would ask twice and could disagree; this
  answer is stored as the fact, once, for every step. It is the one new type in this design.
- **Source unreadable** (`facts_read` is `None`): no decision, and the step's `why` says its
  reads could not be checked, as conformance marks an unreadable module `unverified`.

There is nothing to replay. The answer is recorded as the **fact** in the goal's profile, so the
re-resolved pipeline has no unknown and no record, at every step that reads it. A
`FactDecision` exists only while the fact is unknown.

Pairing travels the same way (`meta.single_end`), so an unknown pairing would stop the steps
whose code reads it too. That is the rule working, not a side effect.

## 6. The walk: the card already asks for facts

`mendel_authoring.needs.need_of` turns a step's open tier-4 records with `unknown` facts into
`NeedKind.FACT`, and `stages/building/cards.py` offers *tell me* for each (`fact_<measurement>`),
recorded as the fact. Today it reads `ProducerDecision.unknown`; it reads `FactDecision.unknown`
too. Under *Set it up, stop only where you need me* this step stops (it has declared values, so
it is not the *setting with no declared values* that is placed and left to the run).

## 7. Gathering: do not ask what only a tool reads

`mendel_api/services/gaps.py` asks every measurement a rule reads, and every label-carried
measurement of a leaf type. A measurement is **not** a gathering gap when all of these hold:

- no rule's `when` reads it (asking it changes no routing);
- no trusted inspector measures it (a sample could not answer it);
- it is not already known.

It is left unknown, and the steps that read it stop (§5). On the spine that is strandedness
alone. Typed words can still state it at any time through the chat's `facts`.

## 8. The guard

`tests/guards/`: **no emitted pipeline contains a step whose tool reads a fact that is unknown in
its goal without a tier-4 record for it.** Built over the shipped registry with each label-carried
fact removed from the example goal in turn. Watched failing against today's code, where
featureCounts emits `-s 0` with no record (A14), and recorded in `tests/fixtures/guard-ledger.md`.

## 9. What `pipeline.yml` records

A `FactDecision` is a decision record and is written where the others are. If the new record kind
needs a schema change, it lands **with Plan B's version 7** (Part I.0, the save file), not as a
version of its own. If Plan B is not ready when this is, the plan says so and the operator chooses
between waiting and a version 7 that Plan B then extends.

## 10. Testing

- The adapter: featureCounts and HISAT2 align read `strandedness`; STAR align reads `paired`
  (its module reads `meta.single_end`) and not `strandedness`; an unreadable module gives
  `None`.
- Resolver (pure, golden): the spine with strandedness unknown has a tier-4 `FactDecision` on
  featureCounts and HISAT2 align, `unknown == ["strandedness"]`, candidates the declared values;
  with strandedness `reverse`, no `FactDecision` and byte-identical `.nf` to today
  (invariant 10); with no mapping passed, identical to today.
- `mendel-authoring`: `need_of` returns `NeedKind.FACT` for a step with a `FactDecision`.
- `mendel-api`: gathering does not ask strandedness for counts; the walk stops at the first step
  that reads it with *tell me*; answering `reverse` records the fact and settles the other step;
  stating it in the chat first means no step stops.
- CLI: `mendel build` on a goal without strandedness reports the tier-4 decision, not a silent
  `-s 0`.
- The guard (§8), watched failing.
- `make verify` (it touches `resolve.py` and the compiler), and the walk in §11.

## 11. Done when (the walk)

One sentence (*gene counts from paired-end RNA-seq of yeast*) plus the walk sample
(nf-core test data `SRR6357070_1/_2.fastq.gz`, 101 bp, paired) uploaded on the reads question:

- read length, pairing and quality encoding are measured, not asked;
- the genome and the annotation are answered by upload or *I have it*;
- strandedness is not asked; under *Set it up* the build stops for it once;
- answering it, the pipeline completes; *Keep* emits `.nf` with the strand set from the answer;
- nothing in the conversation was asked that the sentence or a file answered.

## 12. Not here

- Measuring strandedness at run time (#339).
- The model approving steps (#336) and quote scope (#337): protocol choices pending, which touch
  the same walk and are better decided first.
- Prompt quality (#327).
- Tools off the spine: the guard reports any that read an unknown fact; nothing to declare.
