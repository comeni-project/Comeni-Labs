# Documentation

Three doors. Pick the one that describes what you are doing.

## I am driving Mendel

An agent, or a person doing what an agent does: turning a question into a goal, building a
pipeline, reading what it decided, and tuning it.

1. **[Driving Mendel](guides/driving-mendel.md)** — the loop, end to end, with real output
2. [`pipeline.yml`, field by field](reference/pipeline-schema.md) — the save file
3. [Diagnostic codes](reference/diagnostics.md) — why something was refused
4. [The four tiers](concepts/tiers.md) — what each decision commits you to

## I am writing the registry Mendel reads

The other loop. Mendel reads declared data; the forge is how it gets written.

4a. **[Driving the forge](guides/driving-the-forge.md)** — discover, draft, fill, verify, land

## I am running a pipeline Mendel produced

5. [Getting started](guides/getting-started.md) — install, build, run
6. [Measuring your data](guides/measuring-your-data.md) — turning an asserted premise into a
   measured one
7. [Privacy and egress](concepts/privacy-and-egress.md) — what leaves, and through which door

## I am changing Mendel

8. **[`ARCHITECTURE.md`](../ARCHITECTURE.md)** — the five stages, the load order, routing, both
   tier ladders and the three guards, written against the types that exist. Read it before
   writing code
9. [Contributing](guides/contributing.md) — registry data needs no Python and is the most
   valuable contribution
10. [Releasing](guides/releasing.md) — which number to move, and how a tag becomes a release
11. [Writing a contract](guides/writing-a-contract.md) · [a rule](guides/writing-a-rule.md) ·
    [a registry layer](guides/registry-layers.md)
12. [The design arguments](design/) — why it works this way, and what was rejected
13. [Working notes](../notes/) — how it got here. Provenance, not documentation

## The sections

**[guides/](guides/)** — task-shaped, start to finish. Read one when you are trying to get
something done.

**[reference/](reference/)** — every field of every file format, and every CLI flag. These
describe Pydantic models in `packages/comeni-core`, so a field named here exists in the code.

**[concepts/](concepts/)** — the three ideas the rest depends on: the four resolution tiers, how
routing picks modules, and why data does not leave. Read these when something surprised you.

**[design/](design/)** — the design records. Longer and more opinionated than the concept pages;
written to be argued with.

**[../notes/](../notes/)** — plans, audits and the journal, kept for provenance and not
maintained against the code. `make links` deliberately does not check them.
