# Comeni Labs

*After Comenius, who argued that knowledge belongs to everyone.*

Comeni Labs is a Nextflow-based platform for closing the gap between the wet lab and the dry lab. 
It gives researchers a low-code, modular way to create, deploy, and maintain real pipelines, 
with AI agents designed around recent MIT and Cambridge work on augmentation rather than automation:
the agent assists the scientist, it doesn't replace them. What comes out is plain Nextflow - run it on
your laptop, your HPC cluster, Kubernetes, or your own cloud account.

---
## Try it

You need [`uv`](https://docs.astral.sh/uv/) and Docker.

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
make dev
```

Open **http://localhost:5173** — build a pipeline, run it, watch it.


**[The tutorial](docs/tutorial.md)** takes fifteen minutes and walks all of it, including
changing one fact about your data and watching a different aligner get chosen for a stated
reason.

---

## Documentation

| You want to | Read |
|---|---|
| build your first pipeline | [Tutorial](docs/tutorial.md) |
| run and watch pipelines | [Running the platform](docs/guides/running-the-stack.md) · [Watching a run](docs/guides/running-the-stack.md) |
| add a tool it does not know | [Adding a tool](docs/guides/writing-a-contract.md) · [Drafting one faster](docs/guides/writing-a-contract.md) |
| make a choice depend on your data | [Writing a rule](docs/guides/writing-a-rule.md) |
| understand a decision it made | [The four tiers](docs/concepts/tiers.md) · [How tools get chosen](docs/concepts/routing.md) |
| work on the code | [ARCHITECTURE.md](ARCHITECTURE.md) |

Everything is in [`docs/`](docs/).

---

## Contributing

Adding or contributing to a tool needs no Python. It is a YAML file with a citation, and it is the most useful
contribution anyone can make, because tool definitions are what the compiler builds from. One
definition makes that tool available to every analysis it fits.

Write it by hand with [adding a tool](docs/guides/writing-a-contract.md), or let
[the forge](docs/guides/writing-a-contract.md) draft most of it from the tool's own documentation
and hand you what is left. Definitions live in
[comeni-registry](https://github.com/comeni-project/comeni-registry); code lives here, and
[CONTRIBUTING.md](.github/CONTRIBUTING.md) has the rest.

## Licence

Code is Apache-2.0 ([`LICENSE`](LICENSE)). Tool definitions are CC-BY-4.0 in their own
repository — they cite papers, and attribution matters. Bundled `nf-core` modules keep their own
licences.
