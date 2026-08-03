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

```
samtools_sort → tier 1 — the only contract producing alignment.bam
                         with exactly the required states
```

Silent, because reporting it would be noise.

## Tier 2 — convention

Several candidates were equally good and the registry's `priority` broke the tie. That is
a documented default — someone wrote down which one this registry prefers.

```
star_align → tier 2 — registry priority 10, over nf-core/hisat2/align@2.2.2
```

Green rather than silent: a default is a real choice, and you may disagree with it.

## Tier 3 — data-profiled

A declared rule matched your measurements, and the reason carries the citation.

```
star_align → tier 3 — rule producer_of:alignment.bam matched {'read_length': '>= 70'}:
                      Dobin et al. 2013, doi:10.1093/bioinformatics/bts635
```

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
import json
ir = json.load(open('build/pipeline.ir.json'))
for n in ir['nodes']:
    print(n['id'], n['selection']['tier'], n['selection']['review_level'])
    for b in n['params']:
        print('   ', b['name'], b['value']['tier'], b['value']['review_level'])
"
```

## Where they came from

`packages/comeni-core/src/comeni_core/tiers.py`. The tier-to-review mapping is a function
rather than stored data, so the table in the docs cannot drift from the table in the code.
