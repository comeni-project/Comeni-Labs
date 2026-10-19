# Changelog

Notable changes are recorded here for users and package consumers: features, fixes,
breaking changes, deprecations and operational changes. Routine commits do not each need
an entry. Add relevant notes under Unreleased as work lands, then group them for release.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), with
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Packages version independently,
using tags such as `comeni-core-v0.2.0`. Each version has one `###` heading per package;
[the release workflow](.github/workflows/release.yml) extracts that package's section.
See [the release procedure](docs/how-to/development/release.md) before tagging.

Registry data lives in [comeni-registry](https://github.com/comeni-project/comeni-registry),
mounted here as a submodule. Its changes and releases are recorded in that repository.

## [Unreleased]

### Deployment

- Mendel and Wiener share one PostgreSQL server with separate non-superuser roles, databases
  and migration histories. A new data volume preserves both legacy volumes; migration tooling
  backs up, restores and verifies data before Make permits cutover.
- Production requires separate administrator, Mendel and Wiener database passwords.

These notes consolidate the earlier unreleased entries and backfill notable changes
through the explain-inputs and retention work on this branch. They are not a new release
or a complete commit history.

### comeni-core

#### Added

- Module declarations record source, pinned commit, licence and omitted files. Layer digests
  cover module source as well as contracts, including auxiliary files regardless of extension.
- Registry manifests declare directory layout for linting. Files still declare their own kind;
  module declarations stack by the same key as their contracts.
- Saved pipelines carry the goal, measured profile, pinned contracts and registry layers,
  displacements, decision provenance, emitted-file digests and gate verdicts in `pipeline.yml`.
  It replaces the separate IR, lockfile and publication bundle formats.
- Human and model overrides have separate attribution. Draft graphs and review verdicts
  represent hand-built pipelines and their checks. Diagnostics now declare the emitting
  package, including core and Wiener, and reject undeclared codes.
- Type families, display names and explanations support goal selection and readable
  questions. Measured facts carry their sources; AI-read facts retain evidence attribution.
- Contract declarations include parameter destinations (`ext`, `meta`, `directive`), fixed
  arguments, input-placeholder reasons and pinned test data.

#### Changed

- The saved artifact schema is now version 7: `intent` (what is wanted) and `facts` (inputs
  and measurements, each with its source) at the top, in place of `goal`, which is now
  computed from them. A value a person stated has `source: said` (was `goal`). Only version 7
  is read: before v0.1.0 any other version is refused (`MD0207`) and an older file is rebuilt
  from its starter, not upgraded. Schema version changes are distinct from package release
  versions.
- Each locked registry layer may record where to fetch it: `source` (a network URL, never a
  path, credentials, query or fragment), `commit` (SHA-1 or SHA-256), `dirty`, and `path` (its
  folder in the repository), each left out when unknown.
- Publication payloads use the saved pipeline itself. Emission integrity includes the
  digest of the artifact used to generate the Nextflow files.

#### Fixed

- Artifact validation rejects conflicting writers, duplicate decision keys, missing goals,
  inconsistent override attribution and unsupported parameter destinations. A human or model
  attribution must correspond to an actual decision; AI-derived premises are also counted.
- Directory digests distinguish filenames, file contents and symlink targets, preventing
  ambiguous encodings and accidental hashing of files outside the directory.
- Vocabulary serialization sorts sets. Layer order and identity no longer collapse layers
  with the same display name; serialized displacement records avoid absolute host paths.
- Loading invalid declared data reports a diagnostic with the offending file and remedy.
  IR serialization round-trips computed review fields correctly.

#### Known limitations

- Legacy parameter decision records use null for both an absent override and an explicit
  null answer. Human and model attribution does not resolve that ambiguity.

### mendel-resolver

#### Added

- Replays preserve recorded answers while reporting stale and orphaned decisions. Resolved
  values record the supplying layer and displaced alternatives for contracts and rules.
- Goals and profiles use declared type families and validated measurements with sources.
  Rules record the premises they lacked so the authoring flow can explain unanswered questions.

#### Fixed

- An inapplicable rule becomes a tier-4 question rather than failing resolution or guessing.
  Producer pins are honored when applicable and refused when their inputs cannot be reached.
- Parameter overrides survive replay instead of being discarded by candidate-list checks.
  Registry drift handles deleted or unused contracts and changes to layer order.
- Profile validation occurs at the resolver boundary, not only in the CLI.

### mendel-compiler

#### Added

- `mendel build <starter>` builds from a starter: a version-7 `pipeline.yml` with only
  `intent` and `facts` (`examples/rnaseq.yml`). `--goal` and the separate goal format are
  removed.
- Builds record each layer's git source and commit, and warn when a layer has no network
  source (`MD0231`) or uncommitted edits (`MD0232`); keep and the builder's preview say the
  same. `mendel upgrade` names the commit and folder a changed layer was locked at. `emit` and
  `publish` refuse a starter, which has nothing resolved (`MD0233`).
- `mendel emit` regenerates Nextflow from a saved pipeline without registry access;
  `mendel upgrade` re-resolves against current layers, replays answers and reports drift,
  changes, replayed, stale and orphaned decisions. Dry runs do not write files.
- `mendel publish` verifies and gates the saved files without re-resolving. It records the
  successful gate and refuses divergent files or a failed gate.
- Whole-layer conformance checks compare contracts with module signatures and outputs.
  Missing source is reported as unverified. Layout lint checks declared directory structure
  and refuses relative paths that escape a tool's directory.
- Shared module staging copies only the sources included by a pipeline. `mendel docs`
  renders tool documentation from declared data, with a check mode for stale or missing pages.
- `mendel explain` provides the long-form diagnostic without loading a registry.

#### Fixed

- Resolved settings reach their declared destinations in tool arguments, channel metadata
  or process directives. Reference and annotation inputs reach the processes that need them;
  real-data tests check the resulting counts, beyond what stub execution can establish.
- Conformance reads module source from the contract's registry stack rather than a separate
  vendor root. Build refuses disagreements before emission.
- Emission escapes editable Groovy values and validates template grammar. Refused emission
  leaves existing files untouched; upgrade refuses another pipeline's output directory unless
  explicitly forced. Tier-4 hand edits require both an override and its explanation.
- The test gate enables Docker. Emitted test profiles pin their datasets by commit.

### mendel-authoring

#### Added

- A pure package owns the authoring protocol, typed commands and interpreter. The session's
  current node and named arrows drive transitions; protocol loading checks fork coverage.
- Build plans describe steps, required facts, choices and registry gaps in pipeline order.
  The flow walks the plan, records facts and decisions, and summarizes the resulting pipeline.
- Pacing controls the conversation; tier-4 choices still stop for review. Previously answered
  questions are not asked again. Build and Spawn are consolidated into one authoring flow.

### mendel-api

#### Added

- Persistent authoring sessions support goal extraction, fact gathering, sample uploads,
  read-back, typed answers, build review and resumption. Questions explain their subject,
  affected steps, reason and available answers; uploads can answer missing facts.
- Model-call records retain replies, response format and token usage. Installation settings
  support environment locks, sealed credentials, provider connections and a model per purpose.
- Sample inspection and AI characterisation run as background jobs under protection-level
  checks. Characterisation validates offered identifiers and quoted evidence before using facts.
- Saved whole-pipeline alternatives can be previewed without re-resolving. Manual edits create
  linked authoring drafts, and corrected goals invalidate reviews when their meaning changes.
- Draft deletion removes working content while retaining the specified audit record.
  Cleanup applies retention settings and records deletion counts.

#### Fixed

- Authoring actions use one transaction, with jobs queued after commit. Serialized draft
  writes and version checks prevent autosave and background work from overwriting each other.
- Late or duplicated replies cannot silently advance or lock a newer question. Failed jobs
  remain visible; expired sample text cannot be reused by a late characterisation reply.
- Measured-fact conflicts require an explicit choice. Unbuildable corrections persist
  truthfully, while accepted decisions and current answers remain visible in session history.
- Database constraints and migrations align stored enums, JSON shapes and ownership keys.
  Invalid phase filters return a validation response rather than a server error.

#### Removed

- The separate module source-root setting and mount; registry layers carry module source.

### comeni-ai

#### Added

- Shared provider transport supports purpose-specific models, system/user message splits,
  cache markers, raw replies and cached-token accounting.
- Provider-specific structured response formats constrain declared answers and preserve null
  where allowed. Server validation remains required; an empty allowed list allows no values.

### mendel-ai

#### Changed

- Mendel model integration uses the shared `comeni-ai` transport. The package split does not
  yet encompass all Mendel prompts or worker orchestration; ownership is tracked in
  [issue #310](https://github.com/comeni-project/Comeni-Labs/issues/310).

### comeni-inspect

#### Added

- A separate inspection package processes bounded uploaded samples in subprocesses, producing
  measured facts. Compressed samples support truncated stream inspection with expansion limits.

#### Fixed

- Preserve available decompressed bytes from truncated gzip samples, including on Python 3.14.
  The truncated FASTQ fixture now reports all 998 complete records; the previous report lost
  its final 20 records to buffered reads.

### mendel-forge

#### Added

- Source discovery, scaffolding, typed gaps, verification and human-approved landing support
  registry proposals. Revisions persist new candidates rather than overwriting prior generations.

### comeni-vendor

#### Added

- `comeni-vendor add` fetches module source into a registry layer at a pinned commit.
  Offline `check` verifies the recorded digest; `--upstream` checks for upstream movement
  over the network. Laboratory modules with no upstream report unpinned rather than checked.

### wiener-core

#### Added

- A pure event fold models run state. Ingress admits declared Nextflow fields and drops
  undeclared fields; heartbeat time arrives as an internally constructed event.
- Laboratory-authored strings are identified separately from other structured fields.
  Telemetry mapping stays pure, with export handled outside the package.

### wiener-api

#### Added

- Run submission, local execution, event ingestion and live updates integrate with the build
  application. Wiener reports its execution and retention settings to the shared settings UI.
- Run deletion removes associated files, event streams and pipeline content. Working files
  expire after completion according to retention settings; launching requires available params.

#### Fixed

- Run claims and event folding are serialized. Queued run parameters are durable in the
  run directory, and lost queued jobs can be requeued.
- Database constraints enforce declared shapes and laboratory ownership of child records.

### dag-core

#### Added

- Shared pure graph layout supports the build and run canvases.

### frontend

#### Added

- Goal and build flows show facts, sources, readable questions, step cards, review history
  and model-call usage. Upload cards expose inspection and characterisation status.
- Settings cover appearance, model connections, purpose-specific models, building, running
  and retention. Locked or unavailable settings explain why they cannot be changed.
- Whole-pipeline previews, retained pipeline views, draft/run deletion and retention controls
  expose the corresponding backend operations.

#### Fixed

- The canvas uses a consistent frame for retained and previewed pipelines. Session answers,
  progress and alternative views reflect saved state; duplicate React keys are corrected.

#### Changed

- The interface takes the identity shared with Comeni Code: light first with a dark palette
  that follows the system, Lexend for the interface and Geist Mono for data, one meaning per
  colour (done, the main action, measured, needs you, selected/now), rounder controls and a
  raised main button. The animated background field is removed. The rules are in
  `docs/explanation/visual-identity.md`.
- The header carries the product's mark, *Build · Runs · Registry*, a jump search over saved
  pipelines and recent runs (⌘K or Ctrl+K from any page), help linking to the documentation,
  and settings.

### Repository

#### Added

- `make verify` combines repository checks, real-tool tests and invariant guards;
  `make static` exercises conformance, Nextflow lint and preview. Isolated test databases
  separate destructive fixtures from development data.
- CI runs fast checks on pushes and pull requests, with slow execution checks nightly.
  Database test jobs fail when their required database is unavailable.
- Package release automation, workspace dependency lower bounds, SHA-pinned GitHub Actions
  and Dependabot updates support independent releases.

#### Changed

- Compose documentation identifies service roles and configuration sections. Mendel services
  use `mendel-worker` and `mendel-ai-worker` names alongside `wiener-worker`.
- Documentation is organized into user guidance, reference, design and working notes.
  Build-file comments and command guidance are being simplified without changing behavior.

#### Security

- Static and runtime guards cover pure-package I/O, including indirect process/network calls.
  Egress guards derive payload roots from declared doors and inspect mappings and byte fields.
- Registry loading refuses symlinks. Parameter overrides reject path-shaped values as a
  limited safeguard, not a complete closed-vocabulary solution.

#### Removed

- The separate vendored module tree and unused container configuration files. Registry layers
  now contain source beside contracts; registry-data fixes are tracked in comeni-registry.

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
