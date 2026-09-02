# How tools get chosen

There is no list of pipelines anywhere. You say what you have and what you want, and the
platform works **backwards** — finding a tool that produces what you asked for, then a tool that
feeds it, until the chain reaches something you already hold.

That is why adding a tool makes it usable everywhere it fits, without anybody writing a new
pipeline.

## Backward chaining

You ask for `counts.matrix[gene_level]`. Nothing you have produces it, so:

```
counts.matrix[gene_level]     ← featureCounts produces this
  needs alignment.bam[coordinate_sorted]   ← samtools/sort produces this
    needs alignment.bam                    ← star/align produces this
      needs fastq.reads[trimmed]           ← trimgalore produces this
        needs fastq.reads                  ← you have this. Done.
      needs genome.index.star              ← star/genomegenerate produces this
        needs genome.fasta                 ← you have this. Done.
        needs annotation.gtf               ← you have this. Done.
      needs annotation.gtf                 ← you have this. Done.
  needs annotation.gtf                     ← you have this. Done.
```

Five modules, in dependency order, and nobody wrote that sequence down. It falls out of
the contracts. You can print the result of that search for any built pipeline — see
[reading a route](#reading-a-route) at the end of this page.

This is why adding a tool is a data change: declare what it consumes and produces, and it
becomes reachable everywhere it fits.

## Three rules keep it honest

Backward chaining is easy to get subtly wrong. Each of these fixes a specific failure that
happened.

### A contract cannot satisfy its own input

`SAMTOOLS_SORT` consumes `alignment.bam` and produces `alignment.bam`. It is therefore a
candidate for its own dependency, and without exclusion it selects itself forever.

The router carries a `visiting` set down the recursion. This is also what lets an
`implementation` rule pinning STAR fire correctly one level below the sorter: at that point the sorter is
excluded and the aligners are the real candidates.

### Smallest surplus wins

`Registry.producers_of` matches on **superset**, which is right for a requirement — asking
for `coordinate_sorted` should accept a producer that also indexes.

But when nothing is required, *every* producer of the type matches, and the aligner and
the sorter become indistinguishable. So candidates are ranked by how many states they add
beyond what was asked for, fewest first.

Without it, "get me a BAM" silently means "get me a sorted BAM" — an extra module nobody
requested, in a pipeline that is supposed to be defensible.

### A tie is ambiguity

Contracts equal on surplus and on priority are a genuine question. The router records an
`Ambiguity`, emits a `DecisionRecord`, marks the selection tier 4, and surfaces it.

Never an alphabetical pick presented as a decision.

## Where rules enter

Before ranking, the router asks the rule table whether anything pins an implementation for
the **role** being filled, given your profile. If a rule matches **and the pinned contract is
genuinely a candidate here**, it is selected at tier 3 carrying the citation.

A rule targets a role — *something must align these reads* — rather than a type or a tool.
[Writing a rule](../guides/writing-a-rule.md) is the format.

That second condition matters. When featureCounts asks for `alignment.bam[coordinate_sorted]`,
the only producer is `samtools/sort` — STAR cannot emit that state at all, so an aligner
rule is not about that routing site. It applies one level down, on the sorter's own BAM
input.

If a pin *is* selected and its own inputs cannot be reached, the build stops with
`UnroutablePinError`. Falling back to the next candidate would mean the rule said one thing
and the pipeline did another, silently.

## Ports with alternatives

A port may declare several acceptable shapes, tried in declaration order:

```yaml
accepts:
  - {type_id: alignment.bam,  states: [coordinate_sorted]}
  - {type_id: alignment.cram, states: [coordinate_sorted]}
```

One level of disjunctive normal form — alternatives ORed, states within each ANDed.
Deliberately not more. Full boolean logic would express more and cost the thing the tool
sells: today "why is `SAMTOOLS_SORT` here?" answers in a sentence, and under a general
constraint language it becomes a solver trace.

## Wiring, which is a separate problem

Routing decides *which* modules. Wiring decides which output feeds which input, and it has
its own version of the same trap.

Matching on `type_id` alone once handed featureCounts a `.bai` index file: `samtools/index`
declared its output as `alignment.bam[indexed]`, it was emitted last, and last-writer-won.
Valid Nextflow, no flag, and `-stub-run` cannot catch it because nf-core stubs never read
their inputs.

Two fixes. `samtools/index` now declares `alignment.bai`, because an index is not a BAM.
And a source qualifies only if its emitted states are a superset of the port's required
states, with smallest surplus winning and a real tie recorded at tier 4 — the same rule as
routing, applied to what the pipeline actually built rather than to what the registry could
build.

## Termination

Depth is capped at 10. Beyond that you get `UnroutableError` rather than a stack overflow,
which usually means a cycle the `visiting` set could not break — two contracts refining
each other's states indefinitely.

## Reading a route

`pipeline.yml` carries the whole thing: every step with its selection tier and reason, the
wiring keyed under the step that consumes it, and every decision record.

```bash
uv run python -c "
import yaml
p = yaml.safe_load(open('build/pipeline.yml'))
for s in p['steps']:
    for i in s['inputs']:
        origin = i['source'] or f\"channel:{i['channel']}\"
        print(f\"{origin} → {s['id']}.{i['port']}\", i['states'])
"
```

Keyed on the *destination*, because that is the question a reader has: what arrives here?

Implementation: `packages/mendel-resolver/src/mendel_resolver/router.py` and `resolve.py`.
