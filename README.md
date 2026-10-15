# Comeni Labs

Comeni Labs helps researchers build, review, run and monitor Nextflow pipelines.
The builder uses declared tool contracts, rules and facts about the data to choose
steps and settings. Choices it cannot settle become questions for review. Model
assistance works through that process, and its contributions remain recorded.

The output includes plain Nextflow and a saved pipeline record with the reasons for
its decisions. You can inspect the files and run the workflow outside Comeni.

Comeni is **Alpha, pre-MVP**. The app supports local execution; generated Kubernetes
and AWS Batch profiles are not integrated launch targets. Model-assisted authoring
needs a configured provider or local model. Manual building is available without one.

## Start locally

Install `uv`, Docker with Compose, and Node.js with npm. The development command
installs frontend dependencies, builds the service images and starts the app.

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
make dev
```

Open [http://localhost:5173](http://localhost:5173).
See [installation and troubleshooting](docs/how-to/install.md) for setup
details, and stop the stack with `make dev-down` when finished.

## Documentation

| You need to | Start here |
|---|---|
| Learn through a worked example | [Tutorials](docs/tutorials/index.md) |
| Complete a specific task | [How-to guides](docs/how-to/index.md) |
| Look up commands, schemas or terminology | [Reference](docs/reference/index.md) |
| Understand the design and its boundaries | [Explanation](docs/explanation/index.md) |

The [documentation homepage](docs/index.md) connects these paths.
Developers can start with [architecture](docs/explanation/architecture.md) and
[contributor setup](docs/how-to/development/contribute.md).

## Contribute

Registry contributions add tools, measurements, vocabulary and cited rules.
Tool contracts are YAML declarations bound to real module source; writing a
contract does not require Python. See [writing a contract](docs/how-to/registry/add-tool.md).

Registry changes belong in [comeni-registry](https://github.com/comeni-project/comeni-registry);
platform changes belong here. The [contributing guide](.github/CONTRIBUTING.md)
explains setup, checks and review requirements.

## Name and licence

Comeni is named after John Comenius, who argued that knowledge belongs to everyone.
Code is Apache-2.0 ([LICENSE](LICENSE)). Registry data is CC-BY-4.0 in its own
repository. Vendored `nf-core` modules retain their own licences.
