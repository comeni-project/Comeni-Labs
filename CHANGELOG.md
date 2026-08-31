# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Registry data moved out on 2026-08-16** ([issue #46](https://github.com/comeni-project/Comeni-Labs/issues/46)).
It lives in [`comeni-registry`](https://github.com/comeni-project/comeni-registry) under
CC-BY-4.0, versions separately, and is mounted here as a git submodule at `registry/`. Its
changes are recorded in its own repository, not below.

**Every package versions independently and is tagged on its own** —
`comeni-core-v0.2.0`, `mendel-resolver-v0.1.3`. Entries below sit under a `###` heading naming
the package they belong to, which is what the release workflow reads to fill a Release's notes.
Which number to move is [`docs/guides/releasing.md`](docs/guides/releasing.md).

## [Unreleased]

### comeni-vendor

- **The package exists.** `comeni-vendor add` fetches a tool's source into a registry layer at a
  pinned commit; `comeni-vendor check` asks whether a `module/` has been hand-edited (offline,
  against the digest its own `module.yml` records) or whether upstream has moved (`--upstream`,
  which needs the network and is a different question). A module declaring `upstream: null` is a
  laboratory's own process and reports `unpinned` rather than `ok`: there is nothing to compare
  it against, and reporting a pass would claim a check that never ran.

  **It is not `mendel vendor`, and the name is the point.** `mendel` is
  `mendel_compiler.cli:main` and `mendel-compiler` is one of the packages invariant 1 keeps off
  the network, so a subcommand that fetches from GitHub could not live there — and should not
  look as though it could, because this tool is not part of the deterministic build path.

### comeni-core

- **`DeclaredKind` gains `MODULES`** — the sixth kind, and the first whose declaration is *about*
  a directory rather than being the whole of what it declares. `module.yml` states where the
  `module/` beside it came from, at which commit, under which licence, and what was deliberately
  not copied; the code is upstream's and is never hand-edited. It stacks on the **module key**,
  which is the key contracts already group on, so a laboratory's overlay displacing a contract
  displaces its module with it through one mechanism.

- **The layer digest covers a tool's own source.** A `pipeline.yml` pins a layer, and a digest
  covering `meta.yml` but not `main.nf` is partial coverage — which reads as a guarantee and is
  not one, so re-vendoring at a different commit would leave the pinned digest untouched while
  the emitted pipeline changed behaviour. Covered **by directory** and not by extension: nf-core
  ships `.py`, `.sh`, `.R` and `.conda-lock/` beside `main.nf`, and an extension allowlist covers
  today's corpus and misses the next one.

- **`registry.yml` replaces `kinds:` with `layout:`.** The old field said in its own comment that
  it was *"read by nobody"*, and it had drifted exactly as that invites. The new one is
  `mendel lint`'s argument, so if it is wrong the lint refuses correctly-placed files, which is
  loud. The loader reads neither: invariant 11 says a file declares its own kind.

### mendel-compiler

- **`mendel conformance --registry X`** — does every contract agree with the module it is a
  binding for? **All of them**, where `mendel build --gate lint` only ever reaches the contracts
  a goal happens to route to. `MD0100` (no module source) is reported and does not fail the run,
  because a laboratory wrapping bare containers is legitimate.

- **`mendel lint --registry X`** — is the layer arranged the way its own manifest says? Seven
  refusals, `MD0013`–`MD0019`, including **a relative path leaving a tool's own directory**,
  which is what makes *self-isolated* a checked property rather than a hope. comeni-registry#1
  traded a guarantee for a freedom — a misfiled document used to be impossible by construction —
  and this is the other half of that trade.

- **Conformance reads the layer, not a separate root.** `check()` and `module_path()` take the
  stack's modules and look one up by **key**, derived from the contract's own `nf_include`. They
  computed `module_root / f"{nf_include}.nf"` before, over a directory in *this* repository on a
  different release cadence from the registry the contract came out of — so `MD0104`, the check
  that exists to catch a contract drifting from its module, was comparing two things nothing kept
  in step. `orchestrate.build` loses `vendor_root`.

- **`mendel_compiler.staging`** puts the module source a pipeline needs beside the artifact — one
  implementation where `mendel build` and the API's `keep` each had their own `copytree`, which is
  the shape a bug hides in (`keep` had no copy at all until `MD0210` found it). It stages **what
  the pipeline includes**: five modules for the spine, where the old sweep shipped all thirteen.

### mendel-api

- **`settings.source_root` is retired.** One root: a container that has the registry now has
  everything, and `docker-compose.yml` loses a bind mount from two services.

### Removed

- **`vendor/`**, and `vendor/modules.json` and `vendor/conf/` with it. The modules live in the
  registry layer beside the contracts that bind them. `vendor/conf/` held eight nf-core
  container-config files that no code path ever opened; the label→resource mappings Mendel emits
  are transcribed into `emit.py` as a quoted convention.

### wiener-core

- **The package exists, and it is pure.** `wiener-core` joins invariant 1 — the static scan and
  the runtime audit hook cover it exactly as they cover the three Mendel packages. A fold over
  events has no legitimate need to open a socket, and it pays for itself where nobody planned:
  the OpenTelemetry SDK is a network client, so the guard is what keeps the span *mapping* pure
  and the *export* on the other side of the line. `docs/design/wiener.md` §3.1.
- **`admit()` — the ingress allowlist.** Mendel declares what may leave; Wiener declares what
  may enter. A weblog body becomes closed types and every undeclared field is dropped, so a
  Nextflow upgrade adding a field is inert until somebody adds it in a diff. Held to
  `tests/fixtures/weblog/failing-run.jsonl`, thirteen events from a real run.
- **`EventKind.HEARTBEAT`, and `FROM_NEXTFLOW` is smaller than it.** Time enters the fold as an
  event because `wiener-core` may not read a clock; `heartbeat()` is the only constructor and
  `admit()` refuses one from the network.
- **`LabString`** marks the fields a laboratory's own words reach — `name`, `script`, `workdir`,
  `tag`. Structured fields, which is why "structured fields only" was never a privacy guarantee.

### comeni-core

- **`EmittedBy.WIENER`**, so a code can name the package that raises it. The first member
  naming a package outside Mendel.
- **Two diagnostics, `MW0001`–`MW0002`**, and a new band `MW0001`–`MW0099` for Wiener's
  ingest. `W` was reserved for Wiener when the bands were laid out; this is the first code to
  use it.

- **`SCHEMA_VERSION` 4 → 5. This breaks the artifact format**, and `0.2.0` rather than `1.0.0`
  is a judgement under `docs/guides/releasing.md`'s pre-1.0 paragraph: below 1.0.0 a `0.x.0`
  may still break something, provided the break is said out loud. This is it being said.
  A `pipeline.yml` written by this version is refused by an older Mendel (`MD0207`); a v4 file
  still emits here, which was checked rather than assumed.
- **A model's override is recorded separately from a person's.** `ParamDecision`,
  `ProducerDecision` and `SourceDecision` each gain a `model_override`, and `_Decided` gains
  `model_override_by` naming which model. `human_override` keeps its meaning — `decision.py`
  calls it *"the one field in the system that is by design a person's answer"*, and a model
  writing there would make that sentence false and a machine-assembled pipeline
  indistinguishable from a hand-drawn one. That is audit A130 from the other direction.
- **`DraftGraph`, `DraftNode`, `DraftEdge`** (`plan/draft.py`) — a graph somebody drew, before
  anything has been decided about it. Four names per edge; everything else is derived.
- **`Verdict`, `Finding`, `Level`** (`review/verdict.py`) — what a check reports. It reports at
  three levels and never refuses; refusal stays with `keep` and the gates.
- **Nine diagnostics, `MD0501`–`MD0509`**, and a new band `MD0500`–`MD0599` for validating a
  hand-built graph. `MD0400`–`MD0499` was already allocated to gates and emission.

**Known limit, recorded rather than fixed.** `ParamDecision.model_override` is
`HumanParamValue`, which includes `None`, so a parameter a model deliberately set to null is
indistinguishable from one it never touched. Detecting it via `model_fields_set` was tried and
is worse: after a `model_dump()` round-trip every field is in that set, so it would refuse every
`pipeline.yml` ever written. The same hole is inherited on `human_override` since A3. What is
checked is the reverse — an author naming no act.

- **`emitted_by` names the package that raises a code**, and `EmittedBy` gained `core`. Twenty-
  three entries named a package that does not raise them, all of them raised in `comeni-core` —
  the vocabulary had no way to say so. `tests/test_diagnostics_ownership.py` derives the answer
  from the source.
- **`MD0001`–`MD0009`** — loading declared data refuses with a code, a file name and a fix
  rather than a Pydantic traceback.
- **`ai:` and `MD0225`** — the artifact can state that no model was consulted, and refuses a
  value claiming one when none was available. `pipeline.yml` is at version 4.

### mendel-resolver

- No changes since the last release.

### mendel-compiler

- **`mendel docs`** — one Markdown page per tool, rendered from a layer's declared data.
  A tool is the first two segments of a contract's module key, never its directory, since
  comeni-registry#1 made the path meaningless. `--check` writes nothing and exits 1 when a
  page is stale, missing, or describes a tool the registry no longer ships; that is what
  `comeni-registry`'s CI runs on every pull request.
- **`MD0223` sees a tier-4 setting answered by hand.** Answering a tier-4 question is now a
  two-part edit — the override *and* the reason beside the value — and the one-part edit exits 2.

### Repository

Not part of any package's version: build and documentation changes.

- Every GitHub Action is current and pinned by commit SHA; Dependabot watches them weekly.
- A tag-driven release workflow, and [`docs/guides/releasing.md`](docs/guides/releasing.md).
- Workspace dependencies carry lower bounds, so an independent version means something.

### Changed

- **`via: meta` and `via: directive` now emit** (round three, A38). Only `via: ext` reached a
  tool before, so a value routed to the channel `meta` map or to a process directive was
  recorded with full provenance and carried nowhere — issue #10 reopened one level below where
  it was closed. All three routes emit now, and a `Via` member that emits nothing is refused at
  load rather than left to record a dead value.
- **`mendel publish` certifies the artifact on disk and re-resolves nothing** (round three,
  A50). It read the goal back and re-resolved against whatever `--registry` was installed, so an
  overlay could reroute the pipeline, erase human overrides, and stamp a gate on a result nobody
  read — at the door with no undo. Publish now needs no registry: it refuses a directory that
  diverged from its `pipeline.yml`, gates the files on disk, and stamps the verdict. Conformance
  is checked at `build`, where it always ran, since publish reads no contracts.
- **One artifact: `pipeline.yml`.** It replaces `pipeline.ir.json`, `mendel.lock.yml` and
  `pipeline.bundle.json`, which are no longer written. Every step, setting, decision, module
  digest, registry layer and gate verdict is in it, and every value carries a `why:` — the
  tier it exited at, who settled it, which layer it came from, and the citation. "What
  settings does this pipeline use, and why" was four files and four mechanisms; it is one file
  now. See [`docs/reference/pipeline-schema.md`](docs/reference/pipeline-schema.md).
- **A setting declares the route that carries it, and a dead one is refused.** Every `Param`
  names `via: ext | meta | directive`. Before this, a resolved value became a `params.<x>`
  line in the workflow that no module reads — the resolver ran, flagged tier 4, printed
  `REVIEW`, and the pipeline behaved identically whatever anyone answered. Issue #10.
- **Four verbs.** `mendel emit <pipeline.yml>` rebuilds the Nextflow with no registry and no
  network; `mendel upgrade <pipeline.yml> --out` never writes in place, and `--dry-run` is
  `verify`; `mendel publish <pipeline.yml>` certifies a directory rather than writing a
  bundle beside it.
- **Publication carries a `Pipeline`.** `PublishBundle` is retired: the artifact on disk *is*
  the payload, so what a person reads before publishing and what crosses the boundary cannot
  disagree.
- **`upgrade` reports five categories, not three** — drift, changes, replayed, stale and
  orphaned. A recorded answer that stops applying used to vanish into a "newly asked" count.

### Added

- **The diagnostic registry is data.** `comeni_core/diagnostics.yml` holds every code, and the
  table in `docs/reference/cli.md` is generated from it — `make docs` regenerates, CI checks.
  An undeclared code cannot be constructed. 30 codes: `MD0100`–`MD0108` conformance,
  `MD0200`–`MD0220` the pipeline file.
- **`emitted.from_digest`** — Nextflow runs `main.nf`, not `pipeline.yml`, so editing the file
  and forgetting to re-emit would leave the run and the artifact diverged with every digest
  matching. `mendel emit` reports and cures it; `upgrade` and `publish` refuse.
- **A resolved setting is proven to reach a tool**, on real data, in `tests/test_counts.py`.

### Fixed

- **Round three (A38–A54) is closed** — the first audit of the `pipeline.yml` surface, seventeen
  findings, four critical. Beyond A38 and A50 (above): hand-editable strings no longer flow
  unescaped into generated Groovy (`test_data` is escaped, `NfTemplate` has a grammar — A44/A45);
  a tier-4 answer has one writable home and a stored `human_override` that contradicts it is
  refused (`MD0218`, A46); `source: human` must be backed by a real override (`MD0220`, A54); two
  writers for one destination, a duplicate decision key, a missing `goal:`, and a two-writer meta
  collision are each refused (`MD0208`/`MD0217`/`MD0219`, A40/A52/A48); `upgrade --out` refuses to
  overwrite another pipeline's directory without `--force` (A53); a refused emit leaves the
  directory untouched (A49); all four displacement kinds reach the artifact (A51); and a contract
  that fails to load is blamed on the contract, not the goal (`MD0200`, A41). Every refusal added
  or restored has a reverted-and-watched row in the guard ledger. **A14 stays open** — the loop
  exits on no critical finding surviving a *fresh* audit, so round four is owed.
- **A human override on a *parameter* was discarded entirely, in silence.** A parameter's
  candidate list is a placeholder, so the replay resolver's membership check rejected every
  override, counted it as newly asked, and threw the answer away.
- **The egress guard walked three doors out of four.** It collected its roots by scanning
  `egress.py` rather than from `DOORS`, so moving the publication payload to another module
  took the door with no undo out of every check in that file, silently.

### Security

- **The 2026-08-06 audit's thirteen findings are closed** (A1–A13), plus A15, found while
  fixing A5. See `notes/audits/2026-08-06-plan-1-to-1.7-audit.md`; **A14 and A16 remain
  open**, deliberately, and are described there.
- **Invariant 1 is enforced at runtime, and its claim is now accurate.** A file in
  `comeni-core` importing only allowlisted names reached `os.system` via `pathlib.os` and
  delivered a serialised `Goal` over TCP while the purity guard reported green.
  `tests/test_purity_runtime.py` installs an audit hook over a real build and fails on any
  socket or process event from a pure package; the static scan gained bare
  `exec`/`eval`/`compile` and module-attribute chains. `CLAUDE.md` no longer says the pure
  packages *cannot* reach the network — they *do not*, which is what two partial guards
  support.
- **An installed overlay can no longer reroute a pipeline silently** (invariant 11).
  `ResolvedValue` records which layer supplied a contract or a rule block, and flags the case
  where a lower layer offered something that lost. Contracts and rule tables both, the second
  of which recorded nothing at all.
- **`mendel publish` no longer writes a bundle when its gate fails**, and a bundle records
  which gate it passed. `Gate` moved to `comeni_core.gates` with a shim at the old location.
- **A path can no longer be typed into a parameter.** `DecisionRecord.human_override` and a
  goal's `ParamOverride.value` reject path-shaped values. A blocklist and a stopgap; closed
  parameter vocabulary in Plan 2 Task 11 is the real fix.
- The egress guard learned `Mapping` and `bytes`; a registry layer may not contain a symlink;
  a contract is pinned by its file rather than by what survived parsing; `resolve()` validates
  the profile it was handed rather than trusting `mendel build` to have done it.

### Added

- **`make verify`** — `check` + the counts-matrix tests + the guards, in
  order, with `-j1` where it matters. `make check` deselects the only tests that exercise the
  v1 criterion, and naming that in a Makefile target beats remembering it.

- **A pipeline is a shareable artifact.** `mendel publish` certifies a pipeline directory:
  every contract pinned by content digest, every layer by name and digest, the gate that
  passed and the digests of what was emitted. No filesystem paths and no timestamps, both
  tested — a path is meaningless on the machine that reads it, and a timestamp would turn the
  determinism tests into noise. It writes files and sends nothing; transmitting them is a
  later, separate act.

  *Shipped in this cycle as a `PublishBundle` plus `mendel.lock.yml`; both were consolidated
  into `pipeline.yml` before release, and this bullet describes where it landed.*
- **`mendel upgrade`** re-resolves a published pipeline against the current registry, replays
  every recorded decision rather than asking again, and reports drift (the registry moved)
  separately from changes (that moved *this* pipeline), each with its tier and reason.
  Against an unchanged registry it reproduces byte-identical Nextflow.
- `ReplayResolver` — federation §4.3: load a curated pipeline, change one thing, and every
  untouched decision replays from its record. One more `AmbiguityResolver`, which is the
  payoff for Plan 1 having declared the port.
- Content addressing: `digest_of` for models and `digest_of_directory` for layers.
- `PipelineIR.registry_layers` and `PipelineIR.shadowed`, so the artifact records which
  registry built it and what an overlay displaced.
- `Goal` moved to `comeni-core` so a bundle can carry one; `mendel_resolver.goal` re-exports.
- **The registry is its own layer**, in `registry/`, with a `registry.yml` manifest, and is
  published at [comeni-registry](https://github.com/comeni-project/comeni-registry) under
  CC-BY-4.0. `examples/` now holds the example goal and nothing else.

### Fixed

- **A layer digest was forgeable.** It joined `name:hash` with newlines and escaped nothing,
  so a single file named `a.yml:<sha of "alpha">\nb.yml` digested identically to a two-file
  layer. Names are now hashed rather than embedded, and file and symlink contents are
  domain-separated so neither can impersonate the other.
- **A layer digest followed symlinks out of the layer**, making it depend on bytes the layer
  does not contain. A symlink is now hashed as its target path, as git does.
- **`Vocabulary` digested differently in every process.** Its frozensets are `dict` values
  rather than fields, so the codebase-wide "sets must sort on serialisation" rule had never
  been applied to them, and nothing had serialised a `Vocabulary` before.
- **`ShadowRecord.winning_layer` was an absolute filesystem path**, and it reaches a publish
  bundle. It now carries the layer's name.
- `Lockfile.drift_against` raised `KeyError` in two cases it exists to report: a contract
  deleted from the registry, and a contract still present but no longer used by the
  re-resolved pipeline.
- Layers compared by name rather than position, so **inverting the registry stack reported no
  drift at all** — although order decides which layer shadows which — and two layers sharing
  a basename silently collapsed into one.

- **Conformance checking: `mendel build` refuses a contract that disagrees with its
  module.** A `ModuleContract` is a hand-written binding to a foreign, dynamically-typed
  unit, and until now nothing compared the two. `ModuleSpec` parses the vendored `main.nf`
  and `meta.yml`; seven diagnostics (`MD0100`–`MD0107`) check a contract against it; any
  disagreement exits `2` and emits nothing. Every diagnostic says what to write instead.
- `mendel explain <code>` — the long form of a diagnostic, after `rustc --explain`. Loads
  nothing, so it answers even when the registry will not.
- `PipelineIR.unverified` — contracts whose module source was absent, so nothing could
  check them. A lab wrapping a bare container is legitimate; the claim still reaches a
  publish bundle marked as unevidenced.
- `make static` — conformance, `nextflow lint` and `nextflow -preview`, no Docker, about
  six seconds. Both gates now run on every pull request. They are not redundant:
  `nextflow lint` accepts a reference to a channel that does not exist and exits `0`;
  `-preview` rejects it.

### Fixed

- **Three contracts declared output ports that their modules never emit.** The port name is
  what the compiler reads as `PROCESS.out.<name>`, so each would have failed at launch
  against a channel that does not exist. All three were latent — no goal had yet routed to
  one — and all three were found by running the new checker for the first time:
  `nf-core/samtools/index` said `bai` where `SAMTOOLS_INDEX` emits `index`;
  `comeni/profile/fastqc` said `read_length` against FastQC's `html`/`zip`;
  `comeni/profile/collect` said `profile` against MultiQC's `report`/`data`/`plots`.

- **The emitted spine could not run, and once it could it counted wrongly.** Three defects,
  none of which `-stub-run` could see, because nf-core stubs never read their inputs:
  - `genome.fasta` was not a declared type. Both aligner index builders were called with an
    empty tuple where the reference belongs — you cannot build an index without a genome.
  - `STAR_ALIGN` was handed an empty GTF while the annotation channel sat in the same
    workflow feeding featureCounts.
  - A resolved parameter reached no tool at all. nf-core modules read `task.ext.args` and
    `meta`; Mendel emitted a workflow-level `params.<x>` that nothing referenced. The
    consequence was not a crash: featureCounts fell back to `-s 0`, so the spine would have
    produced a counts matrix computed with the wrong strandedness, silently.
- `Gate.TEST` ran `-profile test` without `docker`, so every process died with
  `command not found`. It had never been run.
- `PipelineIR` did not deserialise: `review_level` is a computed field, written on dump and
  refused on load by `extra="forbid"`. Nothing had read an IR back yet.
- `.gitignore`'s bare `build/` excluded the vendored `hisat2/build` module from git.

### Added

- `ModuleContract.ext_args` — flags a module always needs, emitted into
  `process { withName: … { ext.args = … } }`. Carries no tier, because it is not a decision.
- `Measurement.describes` / `meta_key` / `meta_values` — measured facts travel in the channel's
  `meta` map, where nf-core modules already translate them into flags.
- `PipelineIR.profile` — the IR records what was measured about the data it was built for.
- `NfInput.because` — an empty placeholder must say why the type system does not model that
  input, so the next hollow slot is something a reviewer reads rather than a real run finds.
- `Vocabulary.test_data` and an emitted `test` profile, pinned to a commit of
  `nf-core/test-datasets` rather than a branch.
- Public-repository documentation: `docs/` split into guides, reference, concepts, design
  and internal working notes, with `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
  and this file.
- CI: fast checks on every push and pull request, the `-stub-run` gate nightly, and the
  counts-matrix assertions nightly — the only gate that can catch a pipeline which runs and
  computes the wrong numbers.

### Removed

- The `param: strandedness` rule and featureCounts' `strandedness` parameter. `-s 2` is
  featureCounts' encoding of a measured fact, not a decision — the module already contains
  that translation, and the rule's "citation" was the tool's own manual. It was a translation
  wearing a tier-3 badge. One rule remains in `registry/rules/rnaseq.yml`, and it is a genuine
  decision between two defensible aligners.

## [0.1.0] — 2026-08-03

The deterministic core. A typed goal becomes a runnable Nextflow pipeline with no AI
involved anywhere, and every choice carries a tier.

### Added

**Pipeline construction**

- `mendel build` — goal in, pipeline directory out: `main.nf`, `nextflow.config`,
  `pipeline.yml` and the vendored module tree.
- `mendel profile` — emits a pipeline that measures the input data, plus a `profile.yml`
  recording which contract produces each value.
- Three validation gates: `lint`, `stub` and `test`. The RNA-seq spine passes `stub`
  end to end against real `nf-core` containers.
- `--registry`, repeatable: a laboratory's contracts, rules, vocabularies and measurements
  stack over the public ones, with a `SHADOW` record whenever a layer displaces another.

**The type system**

- Module contracts with semantic `state` overlays — the ~40% `nf-core`'s `meta.yml` does
  not carry, and what routing depends on.
- Closed state vocabularies: a contract naming an undeclared state fails to load.
- Declared measurements — `integer`, `number`, `boolean`, `enum`, and deliberately no
  `string`. A laboratory adds one without a release.
- Ports that accept ordered alternatives, one level of disjunctive normal form.
- `nf_inputs`, declaring the real process call signature, because a contract port is not a
  process argument — five of the ten spine processes differ.

**Resolution**

- The four-tier ladder: structural, convention, data-profiled, ambiguous. Every parameter
  *and* every module choice exits at exactly one tier and carries it forever.
- Tier-3 decision tables, validated against the registry, the vocabulary and the
  measurement declarations at load. A rule that cannot fire refuses to load and says what
  the author can write instead.
- Producer pinning: a rule may choose which module produces a type, citing why.
- Backward-chaining router with cycle exclusion, smallest-surplus ranking, and ties
  recorded as ambiguity rather than settled by a coin flip.

**Guarantees**

- Determinism: the same goal produces byte-identical output, proven across
  `PYTHONHASHSEED` values rather than assumed.
- `tests/test_purity.py` — the three pure packages import no web framework, HTTP client or
  LLM library, enforced against the standard library and dynamic import forms.
- `tests/test_egress.py` — data leaves through four declared doors, each carrying one typed
  payload, with the doors and free-text fields listed literally.
- `tests/test_construction.py` — a `DataProfile` is built in exactly one place, and that
  place validates it.
- Generated PEP 561 type stubs for declared measurements, checked fresh in CI.

### Fixed

- `.gitignore`'s bare `build/` matched `vendor/modules/nf-core/hisat2/build/`, so the
  module every short-read routing decision depends on was never committed.
- Both aligner rules had never once executed. `subject` was an unvalidated free string, no
  contract declared `aligner`, and nothing said so.
- Edges keyed on `type_id` alone handed `featureCounts` a `.bai` index file: valid
  Nextflow, no flag, and invisible to `-stub-run` because stubs never read their inputs.
- `Goal.constraints` was `dict[str, Any]`, so a filesystem path validated, reached
  `main.nf` labelled tier 1 review `none`, and suppressed the tier-4 flag it replaced.
- `needs_review()` scanned only node parameters, so the CLI reported "0 requiring review"
  while an aligner had been chosen alphabetically.
- Generated Groovy literals were unescaped: `it's fine` alone was a syntax error, and a
  crafted value could execute.

[Unreleased]: https://github.com/comeni-project/Comeni-Labs/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/comeni-project/Comeni-Labs/releases/tag/v0.1.0
