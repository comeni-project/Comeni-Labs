# Documentation

Comeni Labs plans, runs and watches bioinformatics analyses. These pages are how to use it.

**New here: [the tutorial](tutorial.md).** Fifteen minutes, and it walks the whole loop.

## Building pipelines

| | |
|---|---|
| [Describing an analysis](reference/goal-schema.md) | what you have, what you want, what your data looks like |
| [Building a pipeline, properly](tutorial.md) | the full loop on the command line — build, read, edit, re-emit |
| Measuring your data | turning *I think the reads are 150bp* into a measured fact |
| [The pipeline file](reference/pipeline-schema.md) | every step, setting and reason, field by field |

## Running and watching

| | |
|---|---|
| [Running the platform](guides/running-the-stack.md) | bring it up on your machine, and what runs where |
| [Watching a run](guides/running-the-stack.md) | send a pipeline, follow it, read what happened |

## Adding tools the platform does not know

No Python required. A tool definition is a YAML file with a citation.

| | |
|---|---|
| [Adding a tool](guides/writing-a-contract.md) | teach the platform a tool it has never seen |
| [Writing a rule](guides/writing-a-rule.md) | make a choice depend on your data |
| [Your lab's own tools](guides/registry-layers.md) | ship private tools without forking anything |
| [Drafting tools faster](guides/writing-a-contract.md) | read a tool's own documentation and fill in the rest |

## Understanding what it decided

| | |
|---|---|
| [The four tiers](concepts/tiers.md) | what each decision commits you to, and why some are flagged |
| [How tools get chosen](concepts/routing.md) | working backwards from what you want to what you have |
| [What leaves your machine](concepts/privacy-and-egress.md) | and why your data is not part of it |
| [Diagnostics](reference/diagnostics.md) | every refusal, and what to do about it |
| [Glossary](reference/glossary.md) | the eight words this project uses in a particular way |

## Working on the code

| | |
|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | how the pieces fit. Read before writing code |
| [Contributing](../.github/CONTRIBUTING.md) | how a change gets in |
| [Releasing](guides/releasing.md) | which version number to move |
| [File formats](reference/) | contract, rule, vocabulary, measurement, CLI |

## Deeper

**design/** — why it works this way, and what was rejected. Long and opinionated.

**[notes/](notes/)** — plans, audits and a running journal. Kept for provenance; not maintained
against the code.
