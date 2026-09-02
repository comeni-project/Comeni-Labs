# Documentation

Comeni Labs turns a description of an analysis into a Nextflow pipeline, and every choice
it makes carries a reason you can read.

There are two halves. **Mendel** builds pipelines. **Wiener** runs them and shows you what
happened. A third thing, **the forge**, writes the registry Mendel reads from.

## Start here

**[Your first pipeline](tutorial.md)** — fifteen minutes, one command at a time, ending with
a pipeline that runs. Everything else on this page assumes you have done it.

## Then pick what you are doing

### Building pipelines

| | |
|---|---|
| [Driving Mendel](guides/driving-mendel.md) | the full loop — goal, build, read, edit, re-emit |
| [Measuring your data](guides/measuring-your-data.md) | turning *I think the reads are 150bp* into a measured fact |
| [`pipeline.yml`](reference/pipeline-schema.md) | the file that **is** the pipeline, field by field |
| [Diagnostic codes](reference/diagnostics.md) | why something was refused |

### Running pipelines

| | |
|---|---|
| [Running the stack](guides/running-the-stack.md) | `make dev`, what comes up, and on which port |
| [Watching a run](guides/watching-a-run.md) | submitting a pipeline to Wiener and reading the result |

### Extending the registry

Mendel only knows the tools the registry declares. Adding one needs no Python.

| | |
|---|---|
| [Driving the forge](guides/driving-the-forge.md) | discover, draft, fill, verify, land |
| [Writing a contract](guides/writing-a-contract.md) · [a rule](guides/writing-a-rule.md) · [a layer](guides/registry-layers.md) | the three things you can add |
| [Contract](reference/contract-schema.md) · [rule](reference/rule-schema.md) · [vocabulary](reference/vocabulary-schema.md) · [measurement](reference/measurement-schema.md) | what each file may contain |

### Changing the code

| | |
|---|---|
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | how the pieces fit. **Read before writing code** |
| [Contributing](../.github/CONTRIBUTING.md) | how a change gets in |
| [Releasing](guides/releasing.md) | which version number to move |

## The three ideas

Read one when something surprised you. Each is a page, not a chapter.

- **[The four tiers](concepts/tiers.md)** — every choice exits at one of them, and carries it for ever
- **[Routing](concepts/routing.md)** — how a tool gets picked, and what happens when two could
- **[What leaves](concepts/privacy-and-egress.md)** — the four doors, and why your data is not one of them

If a screen is using a word at you, that is the [glossary](reference/glossary.md) — eight words
this project uses in a particular way.

## The shelves

| | |
|---|---|
| **[guides/](guides/)** | task-shaped. Start to finish, with real output |
| **[reference/](reference/)** | every field and every flag. Checked against the code by `make docs` |
| **[concepts/](concepts/)** | the four ideas above. Short by design |
| **[design/](design/)** | *why* it works this way, and what was rejected. Long, opinionated, written to be argued with |
| **[notes/](notes/)** | plans, audits and the journal. **Provenance, not documentation** — not maintained against the code, and the one directory here `make links` does not check |

**Reference pages cannot drift.** `tools/check_reference.py` fails the build if a schema page
documents a field the model does not have, or misses one it does — and if the CLI grows a verb
nobody wrote down. That check exists because on 2026-09-02 all five schema pages disagreed with
their models and two `mendel` verbs were documented nowhere.
