# Comeni Labs documentation

Start here. Each section answers a different kind of question.

## I want to…

| … | Read |
|---|---|
| build my first pipeline | [guides/getting-started.md](guides/getting-started.md) |
| teach Mendel about a tool it does not know | [guides/writing-a-contract.md](guides/writing-a-contract.md) |
| make a choice depend on my data | [guides/writing-a-rule.md](guides/writing-a-rule.md) |
| find out what my data actually looks like | [guides/measuring-your-data.md](guides/measuring-your-data.md) |
| ship my laboratory's own contracts and rules | [guides/registry-layers.md](guides/registry-layers.md) |
| look up a command or a field | [reference/](reference/) |
| understand *why* it works this way | [concepts/](concepts/) and [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| contribute a change | [guides/contributing.md](guides/contributing.md) |

## The sections

**[guides/](guides/)** — task-shaped, start to finish. Read one when you are trying to get
something done.

**[reference/](reference/)** — every field of every file format, and every CLI flag. Start
with [reference/pipeline-schema.md](reference/pipeline-schema.md): `pipeline.yml` is the file a
pipeline *is*, and the one you edit to change it. Read
one when you know what you want and need the spelling. These describe the Pydantic models
in `packages/comeni-core`, so a field named here exists in the code.

**[concepts/](concepts/)** — the three ideas the rest depends on: the four resolution
tiers, how routing picks modules, and why data does not leave. Read these when something
surprised you.

**[design/](design/)** — the design records. Why the system is shaped the way it is, what
was considered and rejected, and what the constraints are. Longer and more opinionated than
the concept pages; written to be argued with.

**[internal/](../notes/)** — working notes. Implementation plans and audits, kept for
provenance. Not maintained as documentation.

## One page above all

[`ARCHITECTURE.md`](../ARCHITECTURE.md) is the single best description of how the code
fits together: the five stages, the load order, routing, the tier ladders, and the three
guards. If you are about to change code, read it first.
