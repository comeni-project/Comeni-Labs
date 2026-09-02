# The four tiers

Every module choice and every parameter exits at exactly one tier and carries it forever.
This is the mechanism behind the whole product claim, so it is worth understanding
precisely.

| Tier | Fires when | Review | Shown as |
|---|---|---|---|
| **1 structural** | no choice exists — the inputs force it | `none` | silent |
| **2 convention** | a documented default exists | `none` | green |
| **3 data-profiled** | a declared rule matched measured data | `advisory` | yellow |
| **4 ambiguous** | no rule matched | `required` | red |

## Why four

A chat window gives you one tier: *plausible*. You cannot tell which parts of its output
were forced by your inputs, which were reasonable defaults, which followed from your data,
and which were invented to fill a gap. All four look identical, and the last one is the
one that will hurt you.

Separating them is the difference between a pipeline you can defend and a pipeline you can
only hope about.

## Tier 1 — structural

Nothing was decided, because there was nothing to decide. One contract produces what was
asked for, or one produces it with exactly the required states while the others overshoot.

Silent, because reporting it would be noise.

Tier 1 is rarer than it sounds. In the RNA-seq spine, *every* uncontested step comes out at
tier 2 rather than tier 1 — because "nothing else in this registry fills this role" is a fact
about **what happens to be installed**, which is a convention, not a structural necessity.
Install an overlay and it may stop being true.

## Tier 2 — convention

A documented default settled it — either the registry's `priority` broke a tie, or exactly one
contract in the loaded stack fills the role.

```
trimgalore            tier 2  uncontested — nothing else in this stack fills trimming
star_genomegenerate   tier 2  uncontested — nothing else in this stack fills index_building
samtools_sort         tier 2  uncontested — nothing else in this stack fills bam_sorting
subread_featurecounts tier 2  uncontested — nothing else in this stack fills quantification
```

Green rather than silent: a default is a real choice, and you may disagree with it. Note what
the reason says — *nothing else in **this stack***. It is telling you the scope of the claim.

## Tier 3 — data-profiled

A declared rule matched your measurements, and the reason carries the citation.

```
rule implementation:alignment where read_length is 150, asserted, not measured: STAR's
seed-and-extend search is built for long reads and is nf-core/rnaseq's default aligner; the
index cost it pays back over reads this length; Dobin et al. 2013,
doi:10.1093/bioinformatics/bts635
```

Read what that reason contains: the rule, the fact it read, **whether the fact was measured or
merely asserted**, the argument, and the paper.

**Advisory rather than silent, on purpose.** A rule match is only as good as the
measurement behind it, and Mendel cannot check whether your stated 150bp read length is
true. Yellow means *the machinery worked, check the premise*.

That is also why provenance is recorded per measurement: a measured value came from a tool
that named itself, an asserted one came from a person. Both are legitimate; only one is
checkable.

## Tier 4 — ambiguous

Nothing decided it. The choice was recorded, flagged, and surfaced.

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

**Tier 4 is always flagged, even at high model confidence.** This is the honesty mechanism
and the whole difference from a chat window. A model that is 95% sure is still guessing,
and a tool that hides that is selling you a feeling rather than a result.

## The rules that keep the labels meaningful

**A tier-3 miss demotes to tier 4. It never calls a model inside tier 3.** If it did, tier
3 would silently become "a model said so", the label would stop meaning "a declared rule
matched", and the common case would stop being free and reproducible.

**A routing tie is ambiguity, not a coin flip.** Contracts equal on surplus and priority
produce a decision record at tier 4 rather than an alphabetical pick.

**Every ambiguity emits a record**, including when resolved with no model in the loop.
Records are replayed on rerun rather than re-asked — which is how determinism survives
having a model available at all.

## Modules too, not just parameters

`IRNode.selection` carries a tier for the module choice itself, and `needs_review()` lists
a tier-4 one by node. Before that field existed, a module chosen because it was the only
option looked exactly like one chosen by priority — and for a while the review list scanned
only parameters, so the CLI printed "0 requiring review" while an aligner had been picked
alphabetically. A record nobody is shown is not a flag.

## Reading them

```bash
uv run python -c "
import yaml
p = yaml.safe_load(open('build/pipeline.yml'))
for s in p['steps']:
    print(s['id'], 'tier', s['why']['tier'], '—', s['why']['reason'])
    for setting in s['settings']:
        w = setting['why']
        print('   ', setting['name'], '=', setting['value'],
              'tier', w['tier'], 'by', w['source'])
"
```

`source: human` means somebody answered a tier-4 question by editing the file. The tier stays
4 — the pipeline still contains a question that had to be answered — but it stops appearing
under `REVIEW` and appears under `ANSWERED` instead.

## Where they came from

`packages/comeni-core/src/comeni_core/tiers.py`. The tier-to-review mapping is a function
rather than stored data, so the table in the docs cannot drift from the table in the code.
