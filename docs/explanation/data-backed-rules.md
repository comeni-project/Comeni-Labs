# Data-backed rules and reachable tools

## The intuition first

A convention says “this registry usually prefers STAR.” A rule says “choose STAR when a stated
fact about this dataset makes STAR the defended choice.”

That distinction matters in a low-code app. The user should not have to pick an aligner because
they know the tool landscape, and the app should not pick one because a model sounded
confident. A rule gives the app a small, cited piece of scientific judgement it can apply
reproducibly.

In the RNA-seq example:

```text
read_length >= 70  -> STAR
read_length < 70   -> HISAT2
```

The useful part is not the syntax. The useful part is that a future reader can ask “why STAR?”
and get a data fact, a rule, and a citation instead of a hidden preference.

## Before and after

Before a rule exists, the app may still build a pipeline, but the choice is weaker:

| Before | After |
|---|---|
| aligner is chosen by registry convention | aligner is chosen by a matching data fact |
| a reviewer sees a default or an open question | a reviewer sees tier 3 with the premise |
| changing read length may not change the route | changing read length can pick a different aligner |
| the reason is “this registry prefers it” | the reason names the fact, rule, and citation |

Use a rule when the choice should vary with the data. Use priority or a lab layer when the
choice is simply your default.

## A pinned module must still be reachable

An `implementation` rule pins a module; it does not conjure its inputs. If the rule picks
HISAT2 and nothing in the registry can build a HISAT2 index, the build stops:

```
mendel: cannot route this goal — a rule pins nf-core/hisat2/align@2.2.2 to produce
alignment.bam, but its inputs are unreachable from this goal (…). Rule condition:
{'read_length': '< 70'}
```

Loudly, rather than quietly using STAR instead. A rule that says one thing while the
pipeline does another is the failure this whole tool exists to remove.

A pin applies only where the pinned module is genuinely a candidate for the *states* being
asked for. When featureCounts asks for a coordinate-sorted BAM, the only producer is
`samtools/sort` — so the aligner rule does not apply there. It applies one level down, on
the sorter's own BAM input, where the aligners actually compete.

For instructions, see [Write a rule](../how-to/registry/write-rule.md).
