# The forge for the MVP — design

**Status: written for review (2026-10-19).** *(operator)* marks a choice made in chat on
2026-10-19; *(spec)* marks this document's own call. Supersedes
[the read-only registry design](2026-10-19-read-only-registry-design.md): the app does write to
the registry, through pull requests on `comeni-registry`, and reads it by release.

## Why

The MVP has two weeks to show the whole product: describe an analysis, get a pipeline, run it.
Today the registry holds ten nf-core tools, all for RNA-seq counts, so the builder can only ever
build one family of pipeline. The forge is how the registry grows, and the current one is
unusable *(operator)*. It is rewritten from scratch, for nf-core first, as a dashboard and a
chat that turns an nf-core module into a tested registry tool, published by pull request and
released.

**Done** *(operator)*: a broad set of tools, forged here, from which the builder makes several
very different pipelines from a sentence, and each one deploys to Wiener and runs successfully.

## The story *(operator)*

1. **Catalogue.** A dashboard of every nf-core module with its versions, each **not imported**,
   **imported** (in the registry release the app uses) or **update available** (nf-core has a
   newer version than the registry's). Filter, search and browse the whole catalogue.
2. **An imported tool** opens its page: everything the registry says about it — contract,
   parameters, vocabulary it uses, rules, tests and the release it arrived in.
3. **A tool not imported** starts forging. The person answers the questions that matter; the AI
   proposes the **contract** (ports, wiring), the **parameters**, any **vocabulary** (types,
   states, measurements) and **initial rules**, and **tests**. The person approves each piece and
   can chat with the AI throughout. This is an open chat — the AI has room to propose — because
   a person reviews every piece before it counts; the builder's strictness is for deciding a
   scientist's pipeline, not for drafting a tool.
4. **Tests.** The AI writes the tool's tests from nf-core's own (nf-test on `test-datasets`
   files) and runs them through Comeni's contract — so a green test proves our wiring and
   parameters, not only nf-core's module. Green: it runs, and every declared output exists in
   its declared format *(operator)*. Nothing publishes until green.
5. **Open pull request.** The forge pushes a branch to `comeni-registry` with the tool, its tests,
   its vocabulary and rules, and a changelog entry, and opens a pull request whose description is
   the AI's summary and the person's approvals.
6. **Approve pull request.** Merges it *(operator: two buttons)*. The tool is now in
   `comeni-registry`, not yet released.
7. **Releases page.** A person manages releases: the page shows what is merged and unreleased
   (the changelog's *Unreleased* entries, written automatically per merged pull request), and
   cuts a release — version, notes — which tags `comeni-registry` and publishes its GitHub
   release *(operator)*.
8. **The app follows releases.** By default it builds with the newest registry release; an
   installation may pin one in Settings *(operator)*. A pipeline names the release it was built
   with.

## Goals

- The story above, working end to end, for **nf-core** modules.
- Sources behind one interface, so pegi3s is a second implementation later, not a rewrite
  *(operator)*.
- **Clean code** in everything new: small units, one responsibility each, named patterns where
  they earn it *(operator: "clean code is a must")*.
- A sample of eight pipelines the MVP should reach (below), all forged through this forge.

## Non-goals

- pegi3s (designed for, not built) *(operator)*.
- Personal or lab tools, lab layers, any registry but `comeni-registry` *(operator)*.
- Accounts and permissions (#83): anyone using the app may open or approve a pull request; the
  pull request records who *(spec)*.
- Tests that judge the science of an output (beyond format and presence) *(operator)*.
- Keeping the old forge's code, data or routes *(operator: rewrite)*. Its database tables go;
  there are no users before v0.1.0.

## Anti-goals

- A tool reaching the builder without a person approving each piece, green tests and a merged
  pull request in a release.
- A pipeline that does not say which registry release it was built with.
- The AI's proposal being recorded as the person's choice.

## Constraints (from `CLAUDE.md` and the invariants)

- Registry changes need human approval: approving each piece, and the *Approve pull request*
  button, are that approval.
- Pure packages stay pure; GitHub, git, Nextflow and model calls live in adapters.
- Model calls go through declared AI points with typed payloads, and every reply's ids are
  validated where they arrive. Forging is a declared AI point (`DoorPath.FORGE` exists for the
  review chat); its payloads are declared shapes, and what is sent is visible.
- The GitHub token is a deployment secret: set in the environment, never typed into a page,
  never logged, never sent to a model.
- A contract's ports must agree with its module source (the conformance check), and a tool's
  published files are pinned by content digest, as today.

## The sample: eight pipelines *(operator: a sample of what to aim at)*

| # | Pipeline | Tools (nf-core) | Test data (`test-datasets`) |
|---|---|---|---|
| 1 | RNA-seq gene counts (exists) | STAR/HISAT2, Trim Galore, featureCounts | existing |
| 2 | Genome assembly | fastp, SPAdes, QUAST | small Illumina reads |
| 3 | Germline variant calling | BWA (index, mem), samtools, bcftools (mpileup, call, stats) | small genome + reads |
| 4 | Taxonomic profiling | Kraken2, Bracken, Krona | reads + a small Kraken database |
| 5 | Peak calling | Bowtie2 (build, align), MACS3 | paired-end BAMs exist |
| 6 | Multiple sequence alignment | MAFFT (FAMSA, Clustal Omega) | SARS-CoV-2 sequence set |
| 7 | Cell segmentation and quantification | Cellpose, mcquant | tonsil OME-TIFF |
| 8 | Peptide identification | OpenMS peak picking, Comet | yeast mzML + protein FASTA |

All modules and test files were checked to exist (2026-10-19). 1–5 are the aim; 6–8 are a
stretch, in that order, and are where the builder meets data that is not reads. Each new area
brings vocabulary, measurements and rules the forge must propose — that is part of the test.

## The design *(spec, except where marked)*

### Shape

- **Sources** — a `CatalogueSource` interface (list modules with versions; fetch one module's
  files, metadata, tests and test data references); `NfCoreSource` implements it from
  `nf-core/modules`. pegi3s is a later `Pegi3sSource`. Nothing outside a source knows its format.
- **Catalogue** — a periodic sync stores each module, its versions and its state against the
  registry release in use. The dashboard reads it; filters run in the database.
- **Forging** — an *adaptation* per module version: the AI's proposals for each piece, each
  with a state (proposed, approved, changed by the person, rejected) and its chat. Approving is
  a recorded decision with who and when.
- **Testing** — a tool's tests live in the registry beside it (a new `tests/` folder per tool:
  inputs as `test-datasets` URLs, expected outputs and formats). The forge builds a small
  pipeline from the contract with `mendel-compiler` and **submits it to Wiener as a run**, then
  reads the result *(operator)*: Wiener stays the one service with Docker, and every forge test
  exercises the run path the eight pipelines need. The ten existing tools get tests too, through
  the same flow.
- **Publishing** — a `RegistryPublisher` interface (open a pull request, merge it, cut a
  release); `GitHubPublisher` implements it with a working clone of `comeni-registry` and the
  GitHub API. The changelog is fragments per pull request, collected into the release notes.
- **Releases in the app** — an installation setting, *registry release*: `latest` (default) or
  a pinned version. The registry is fetched by release (tag) into a read-only folder per
  version; the layer record names `comeni-registry`, the tag and its commit. This also answers
  production without git metadata in the image, and supersedes the writable `.run/registry`.

### The flow engine

The builder's protocol engine (a diagram of nodes and arrows that *is* the program, a pure
interpreter, typed commands) is a fit for forging's states. Whether to share it is judged when
the plan is written *(operator: "if it's worth it")*: if its core can be made generic over its
phases and events without bending the builder, it moves to a shared pure package and both use
it; if forging's flow is simple enough that a plain state machine is clearer, it stays separate.
Either way, no copy.

### The AI

Forging asks more of a model than the builder's chat: it writes contract YAML, parameter
routes and test specs. The model is chosen per purpose in Settings, as today; the plan measures
whether the local gemma3:12b can draft a contract that passes conformance, and if not, the
default for forging is an API model, with local models still selectable *(spec)*.

## Answers after the builder check

1. **Forging starts from `comeni-registry` `main`** (merged, possibly unreleased), not from the
   app's release, so a chain of tools (BWA index, then mem, then bcftools) can be forged one
   after another without a release between each. A forge pull request may **edit shared files**
   — vocabulary, rule tables, a role's alternatives — because adding a tool to a role means
   changing that role's rule (Bowtie2 or BWA beside STAR/HISAT2 must not leave RNA-seq routing
   tied). One forge pull request open at a time; the next starts after it merges, so there is no
   rebase handling. The catalogue shows **in review** (open pull request) and **merged, not yet
   released** beside *imported* *(spec)*.
2. **Tests run as Wiener runs** *(operator)*, as above.
3. **Builder and Wiener gaps met while reaching the eight pipelines are in scope**, budgeted
   under step 6. A protocol or rule question still goes to the operator as choices, decided the
   same day *(operator)*.
4. **The `registry/` submodule stays**, pinned to a registry **release tag**, for this
   repository's tests, CI and the CLI. The app follows releases at run time: `latest` checks
   GitHub for a newer release and fetches it when the network is there; offline it keeps the
   newest release it has; a pinned installation never fetches. One source of truth per role:
   the submodule for development, releases for the running app *(spec)*.
5. **Approve pull request merges only when `comeni-registry`'s CI is green**; pending or red
   disables the button and says why. Registry CI keeps its current checks (layer loads, README
   current, layout lint, conformance); the forge has already run the tool's tests before
   opening the pull request, so CI does not run containers. Teaching the registry's layout and
   pinned engine (`ENGINE_REF`) about `tests/` is a task in this plan, done before the first
   forge pull request *(spec)*.
6. **A version is the tool's version** (from the module's `environment.yml` or container), as
   registry ids already are (`nf-core/fastqc@0.12.1`). The registry holds one version per tool;
   *update available* means nf-core's module now packages a newer tool version, and importing
   it replaces the tool's folder in place, through the same forge and pull request. Older
   versions are not forged. The catalogue syncs from a shallow clone of `nf-core/modules`, not
   the GitHub API, so ~2,100 modules cost one fetch *(spec)*.
7. **A test may chain registry tools** when its input cannot come ready-made from
   `test-datasets` (BWA mem after BWA index; Kraken2 after untarring its database). The test
   spec lists setup steps by registry tool id, so tools are forged in dependency order, and a
   helper such as `untar` becomes a tool when a test needs it. Ready-made inputs are preferred
   *(spec)*.
8. **Only an installation with a GitHub token can publish.** Without one the forge works up to
   green tests and shows publishing as unavailable, saying why. The pull request records the
   author name from Settings (`identity.default_author`) in its description; the GitHub actor
   is the token's account *(spec)*.

## Order of work, and what is cut first

1. Sources, catalogue and the dashboard (nf-core).
2. Forging: proposals, approvals, chat — contract and parameters first, then vocabulary and
   rules.
3. Tests: the spec format, the runner, and tests for the existing ten tools.
4. Pull requests and merge; the changelog.
5. Releases page; the app following releases.
6. Forge pipelines 2–5, build each from a sentence, and run each through Wiener (the first full
   run walk since August), fixing the builder and Wiener gaps this finds (in scope).
7. Stretch: pipelines 6–8.

Cut first if time runs short: 7, then the releases page's polish (a release can be cut from the
CLI), then *update available*.

## Testing

- Unit tests for each source, publisher and runner against recorded fixtures (no live GitHub or
  models in tests; a fake publisher records calls).
- The forge's flow tested at its boundaries: a proposal never counts until approved; publish
  refuses before green tests; approval records who.
- Live: forge one module end to end into a test repository, then the real one.
- The eight pipelines, each built from a sentence and run, are the acceptance.

## Left to the builder

- The catalogue's sync cadence and storage; the dashboard's layout (designed against the
  existing artboards where one fits).
- The exact test-spec format, as long as it lives in the registry beside the tool and names
  `test-datasets` files.
- Whether the flow engine is shared (above).
- Which old forge tables, routes and screens can be deleted in one step.
