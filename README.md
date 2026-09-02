# Comeni Labs

**One platform for planning, running and watching bioinformatics analyses.**

Describe the analysis you want. Get a pipeline. Run it. Watch it work. When something breaks,
be told what went wrong and what to do about it — without writing code, logging into a cluster,
or reading a thousand lines of log.

Comeni Labs exists to close the gap between the bench and the analysis. The people who generate
the data should be able to analyse it.

---

## What makes this different

Most tools take one of two positions. Hand the whole job to a model — fast, and you cannot
defend a word of it. Or make you write everything — defensible, and nobody in a wet lab is
going to.

**Comeni Labs is semi-deterministic, and that is the whole idea.**

A deterministic engine builds everything it can *prove* from declared data — which tool produces
what, which states it needs, what a convention says. Then it stops, and hands out what is left
as **typed, addressable questions**. Each one carries:

- **an id** — `produces[0].type_id`, the exact thing being asked about
- **what it is asking**, in a sentence
- **why it could not be settled** — no rule covered it, or two tools tie
- **the legal answers** — and whether that list is exhaustive
- **a ranked suggestion**, when the arithmetic is confident enough to have one

An AI answers *only those*, addressed by id, and cannot produce anything outside the candidate
set. Everything else was arithmetic.

So you get a pipeline where **you can see exactly which parts a model touched** — and the rest
is reproducible without one. The engine runs the same with no model configured at all.

It also keeps the model's job small enough to do well. Measured over every port of every tool
definition in the public registry: listing candidates alphabetically put the right one first for
**1 of 30** fields; ranking them by what the tool and the port are called puts it first for
**25 of 30** — before a model is asked anything at all.

---

## The loop

```
    describe  →  build  →  run  →  watch
       ↑                             │
       └─────────────────────────────┘
```

**Describe.** Say what you have and what you want — *paired 150bp RNA-seq reads, and I want a
gene-level count matrix*. No tool names, no flags, no filenames.

**Build.** You get a real Nextflow pipeline. Every tool and setting it could settle, it settled
— and it shows you what on: a constraint, a convention, or a measurement from your data. What it
could not settle it leaves **empty and flagged in red**, never filled with a plausible default.

**Run.** One pipeline, several places to put it. The emitted config carries profiles for local
execution, Kubernetes and AWS Batch, so the same pipeline scales from your laptop to a cluster
without being rewritten. You launch it from the browser; containers, queueing and execution are
handled.

**Watch.** Live telemetry, automatically — one page per run, every process and every task, what
it cost in memory and time, what it is waiting on. Nothing to instrument.

**And when it fails**, you are not handed a log. The platform reads the run's own state, decides
what should happen — retry, escalate, stop — records why in terms you can audit, and gives you
a first read on what went wrong. You approve; it acts.

---

## Try it

You need [`uv`](https://docs.astral.sh/uv/) and Docker.

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
make dev
```

Then open **http://localhost:5173**.

Or build a pipeline from the command line in one command:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out build/
```

```
5 modules, 1 requiring review
  REVIEW  star_align.seq_platform
```

**[The tutorial](docs/tutorial.md)** takes fifteen minutes and walks the whole loop.

---

## Where it is

Honest, because a half-built platform that reads as finished is worse than one that says so.

| | |
|---|---|
| **Describe** | typed descriptions work. Plain-language input is next |
| **Build**, and the question API above | works |
| **Run** | works on a local executor. Kubernetes and AWS Batch profiles are emitted, not yet launched for you |
| **Watch** | works. Live per-process and per-task telemetry, with a timeline |
| **Diagnose a failure** | partly. The run's state is folded and a decision recorded with its reason; only *cancel* is wired to act |
| **An agent that proposes a fix to the pipeline** | not built. This is the next thing |

RNA-seq is the analysis the platform is proven on end to end. Other assays need registry data,
not code.

---

## Documentation

| You want to | Read |
|---|---|
| build your first pipeline | [Tutorial](docs/tutorial.md) |
| run and watch pipelines | [Running the platform](docs/guides/running-the-stack.md) · [Watching a run](docs/guides/watching-a-run.md) |
| add a tool the platform does not know | [Adding a tool](docs/guides/writing-a-contract.md) |
| make a choice depend on your data | [Writing a rule](docs/guides/writing-a-rule.md) |
| understand a decision it made | [The four tiers](docs/concepts/tiers.md) |
| know what leaves your machine | [Privacy](docs/concepts/privacy-and-egress.md) |
| work on the code | [ARCHITECTURE.md](ARCHITECTURE.md) |

Everything is in [`docs/`](docs/).

---

## Contributing

**Adding a tool needs no Python.** It is a YAML file with a citation, and it is the most useful
contribution anyone can make. See [adding a tool](docs/guides/writing-a-contract.md).

Tool definitions live in [comeni-registry](https://github.com/comeni-project/comeni-registry);
code lives here. [CONTRIBUTING.md](.github/CONTRIBUTING.md) has the details.

## Licence

Code is Apache-2.0 ([`LICENSE`](LICENSE)). The tool registry is CC-BY-4.0 in its own repository —
tool definitions cite papers, and attribution matters. Bundled `nf-core` modules keep their own
licences.
