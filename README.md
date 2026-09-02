# Comeni Labs

**One platform for planning, running and watching bioinformatics analyses.**

Describe the analysis you want. Get a pipeline. Run it. Watch it work. When something breaks,
be told what went wrong and what to do about it — without writing code, logging into a cluster,
or reading a thousand lines of log.

Comeni Labs exists to close the gap between the bench and the analysis. The people who generate
the data should be able to analyse it.

---

## The loop

```
    describe  →  build  →  run  →  watch  →  fix
       ↑                                       │
       └───────────────────────────────────────┘
```

**Describe.** Say what you have and what you want — *paired 150bp RNA-seq reads, and I want a
gene-level count matrix*. No tool names, no flags, no filenames.

**Build.** You get a real Nextflow pipeline. Every tool chosen, every parameter set, and beside
each one a reason you can read: a constraint, a convention, a measurement from your data, or an
open question it refuses to answer for you.

**Run.** Send it to the platform from your browser. It handles the containers, the queue and the
execution.

**Watch.** One page per run. Every process, every task, what it cost, what it is waiting on.

**Fix.** When a run fails, the platform decides what should happen — retry it, escalate it, stop
— and tells you why. You approve; it acts.

---

## What makes it different

Anything can generate a plausible pipeline. The question is whether you can defend it six months
later, to a reviewer or to yourself.

**Every decision carries its reason.** Not a log of what happened — the pipeline file itself
records, beside each choice, what settled it and on what basis.

```
star_align   tier 3   read_length is 150, asserted, not measured: STAR's seed-and-extend
                      search is built for long reads … Dobin et al. 2013
```

**It tells you what it does not know.** A choice nothing could settle is flagged in red and left
empty, never filled with a plausible default.

**The same description gives the same pipeline, every time.** Change one fact about your data and
watch the pipeline change with a reason attached.

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
| **Describe → build** | works. Typed goals today; plain-language input is next |
| **Run** | works. Upload a pipeline, fill in your data, launch |
| **Watch** | works. Live run page, per-process and per-task, with a timeline |
| **Fix** | partly. The platform decides and records what should happen; only *cancel* is wired to act on it |
| **Agents that propose pipeline changes** | not built. This is the next thing |

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

## Your data stays with you

The platform never receives your sequencing data. It plans and runs analyses; the files stay
where they are. A description of an analysis holds types and measurements — there is nowhere to
put a sample name, a filename or a path, and that is enforced rather than promised.

Clinical laboratories are a target user, not a later market. [Privacy and
egress](docs/concepts/privacy-and-egress.md) is the detail.

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
