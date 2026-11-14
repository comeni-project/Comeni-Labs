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
- The API and the AI worker share `.run/chatgpt` as `CHATGPT_TOKEN_DIR`, for a ChatGPT
  subscription's sign-in (#457).

These notes consolidate the earlier unreleased entries and backfill notable changes
through the explain-inputs and retention work on this branch. They are not a new release
or a complete commit history.

### comeni-core

- Rule proposals (#462): a door, `rule_proposal` (`RuleProposalRequest`): a target, the existing rows, the facts a row may test, the legal answers, and each person's answer with its study facts and reason. Codes MI0500 and MI0501.

- A second table (#466): `Constraints.tables` names study inputs given as several items (MD0347); their channel carries a `TableShape` (`name`, file `columns`, item `facts`). A port may select on a fact describing its own type, a table row's fact, which is a column of that table rather than of the samplesheet. MD0348 refuses a by-sample join after a cross.

- Parts (#466): a port may run on parts of a sample's item (`parts`), and a splitter's output fans out (`fans_out: part`, `Grain.PART`), MD0346. `Constraints.whole` names the tools a person keeps whole; `IRNode.parts` and `Step.parts` record each step that can run on parts, and `StepInput.parts` says where parts spread and gather. Splitting and merging tools are never routed as producers.

- Relations between samples (#466): measurement kinds `key` and `sample_ref`, read only from samplesheet rows (MD0342); a port gathers per key (`by`, MD0343) or selects samples by their facts (`select`); a shared slot joins `by_key` or `by_ref` on an `NfInput.key` (MD0344). Each relation is a samplesheet column (`StepInput.by`, `StepInput.select`, `CallArg.key`).

- Lanes and folds (#466): `Constraints.units` names inputs whose rows may repeat a sample, carried on the channel (`Channel.units`), which makes the input a samplesheet (MD0340); a port may gather at `grain: sample` (a sample's rows). A run-time fact may be folded over the study (`AtRunSource.FOLDED`, `AtRunFact.folds` and `using`).

- A tool chosen per sample (#466): `IRNode.guard` and `Step.guard` (`Guard`: the decision as a lookup giving a tool, and the tools whose samples a step takes); `StepInput.mixed` names further producers where branches rejoin; `SheetFact.from_row` is a closed vocabulary (`RowFact`). MD0339.

- Mixed single-end and paired samples (#466): a type's second column may be blank (`second_may_be_blank`); a measurement may be read off the row (`row: second_file_present`, MD0338); a samplesheet fact may come from the row (`SheetFact.from_row`).

- Per-sample facts (#466): `Grain` (study, sample) replaces channel `scope` and port `cardinality` (a gathering port says `grain: study, many: true`; MD0331); a measurement's scope is its type's grain, so `per_sample` is gone (a `describes` naming no type is MD0334); `constraints.varies` lists facts a person said differ between samples (MD0332). `AtRun` reads several facts, each from the samplesheet, a measurement or both, and may fall back to stopping the run; `Pipeline.sheet_facts` are samplesheet columns checked by the run (MD0335). A contract's rule may read `fact.<measurement>` (MD0336), settled per sample (`Step.sample_rules`), and refused when every sample breaks it (MD0337). SCHEMA_VERSION 9.

- Measurers (#465): one `declares: measurer` replaces `declares: measure`, by our code (`by: code`, a format's records) or by a tool and a parser of its output (`by: tool`), with where it runs (`runs: [server, pipeline]`); MD0326/MD0327. `Evidence.coverage` and `PremiseRecord.coverage` (`Coverage`: head or all) say how much of the data a fact was read from. Run-time decisions (#217): `plan.at_run` (`AtRun`, `MetaAtRun`, `Confirm`), carried as `Setting.at_run`, `Channel.meta_at_run` and `Pipeline.confirms`.

- Tool constraints, phase 2 (#464): an `nf_inputs` entry may mix required and optional ports and hold independent optional ones; `join` may be a map giving each later port its own (`NfInput.join_for`); conditions may test `type.<input>`, the type connected to an input with `accepts`; the constraint check tries each accepted type (MD0612). `ToolTest.types` says which accepted type a test's data is. The artifact's `CallArg.joins` carries a per-port join.
- A contract param routed to `ext` with no template is refused when it loads if its default
  is outside the substitutable class (MD0221). QUAST's `prefix: ${meta.id}` passed every check
  and then failed every build that used it (#477).
- Tool constraints (#460): contracts declare optional inputs (`required: false`, `absent`), outputs written under a condition (`produced_when`), constraint rows and groups. `comeni_core.logic.when` is the one condition evaluator for contracts and rules; `declared.constraints` evaluates a setup and checks a contract for contradictions, dead and fake-optional inputs and outputs never written (MD0601–MD0607). `pipeline.yml` records each step's optional-input states and run rules, and marks optional channels.
- A model choice may carry `temperature`, `reasoning_effort` and `timeout_seconds` for that
  purpose's calls (#457). Invariant 12 (no subscription OAuth) is retired.
- `qc.report::assembly`: a type's states are written in the type. A contract file writing them
  beside it is refused (`MD0110`), and a signature is spelled that way. `OutputPort.format` records the file formats an output
  writes, checked against the module (`MD0109`) and taking no part in matching.
- `LockedLayer.release`: a pipeline names the registry release it was built with. Omitted when
  unknown, so existing pipelines keep their digests
  ([#367](https://github.com/comeni-project/Comeni-Labs/issues/367)).
- `declares: test`: a tool's tests, beside it (`ToolTest`), naming files inside nf-core's
  `test-datasets`, never URLs ([#365](https://github.com/comeni-project/Comeni-Labs/issues/365)). An
  older engine refuses a layer holding one.
#### Added

- A goal's constraints carry a person's structural intent: `absent_roles`, `exclusions` and
  `sources`, each left out of the file when empty. `pipeline.yml` is version 8; only 8 is read
  ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395), A1).
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

- `OMITTABLE` names the routes on which an unanswered setting is optional: the emitter writes
  nothing and the tool keeps its own behaviour (`ext`, `directive`)
  ([#384](https://github.com/comeni-project/Comeni-Labs/issues/384)).

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

- Rule proposals (#462): `proposals` turns a kept pipeline's decisions into cases, gathers a person's tier-4 answers per target (`MIN_CASES = 3`), judges a proposed row against them (contradicted, unsupported or never firing), narrows it to where the existing rows missed, and replays it over every past decision of its target.

- Parts (#466): a step that can run on parts of each sample is split before it and merged after it whenever the registry has a splitter and a merger and the step's only per-sample input is the split one, unless the person keeps it whole.

- Lanes and folds (#466): an input whose rows may repeat a sample gets the type's `merging` step before anything reads it (MD0341). `aggregate` folds over `study` (was `cohort`) with `agree`, `all`, `any`, `count` and `distinct` beside `max`, `min` and `mean`, at build time from known values and in the run otherwise.

- A tool chosen per sample (#466): an `implementation` decision whose rows wait only on facts said to vary is a branch point (`at_run.branch_points`); the goal is routed once per tool and the routes merged, each branch's steps guarded; its fallback is asked once (`<step>.if_no_row.implementation:<role>`); routes that differ before the choice are refused (MD0339).

- Per-sample facts (#466): a run-time setting may wait on several facts, from samplesheet cells or measurements; its fallback question is its own (`<step>.if_no_row.<setting>`) and may be answered with a stop; a fact must describe the input behind the step's first input. `mendel_resolver.cases` gives a rule's cases with undetermined, its gaps and overlaps; a `hit: unique` rule over a per-sample fact may not overlap (MD0333). MD0328 is retired.

- Settings decided at run time (#217): a param rule waiting on one fact a pipeline measurer can measure, describing an input in the step's lineage, compiles into a lookup; discovery asks nobody, the build routes again with the measurement wanted (MD0328, MD0329). Estimates a decision used are measured again over all the data (`confirms`). `measure_steps` builds the generated measuring steps; `Layers.routing` is the registry builds route with. A decision may require `coverage: all`. An omittable setting's run-time fallback is the tool's own value.

- Rules v2 (#461): a setting can take a fact's value (`then: {fact: <id>}`); `round` joins the transform chain; a decision declares `hit: first | unique`, and a tie under `unique` is asked at tier 4; load checks every case a table's rows tell apart for gaps (MD0311), dead rows (MD0323) and too many cases (MD0324), and a literal value against the tool's constraints (MD0325). A row reading a derived fact records the facts it came from. mendel-resolver needs pydantic 2.12.
- Constraints are checked with the types routing connected (#464): a step's required inputs are routed first, its optional ones decided with their types; resolution follows the router's first matching alternative; a refused alternative leaves no steps behind; a pipeline input feeding an `accepts` input gets a channel of the type it matched.
- Optional inputs are routed off unless switched on, made required when a later step needs what they add, and brought along by constraint rows; constraints are re-checked once parameters resolve (MD0608–MD0610) (#460).

#### Added

- Loading refuses a module that no contract in the stack binds (`MD0025`): such a module could
  never be chosen. The three in `comeni-registry` were removed ([#410](https://github.com/comeni-project/Comeni-Labs/issues/410)).
- The resolver honours a person's structural intent on every re-plan: a role switched off, a
  tool excluded at a site, a port's source pinned (recorded as the person's). Conflicts are
  named (`MD0319`–`MD0321`); `inert_intents` reports intents that applied nowhere
  ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395), A1).
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

- `mendel lint` checks a measurer piece's imports and calls (MD0027), whatever the layer's
  manifest says. The inspector-pieces guard, the forge and the registry's CI use this one check
  (#487).

- A step reading a sample and a table runs on every pair (`combine`, then `multiMap` into its two inputs), the row's `meta` on the sample's under the table's name; each pair publishes under its own name; a blank or repeated row name, a missing file, or a table none of whose rows the step reads stops the run (#466). A crossed step that takes only some samples or reads a fold is refused (MD0348).

- A sample's parts run in parallel and merge per sample, gathered with a `groupKey` sized by the splitter's own count, so one sample never waits for another's; a splitter making one part still flows; each part publishes under its own name (#466).

- A group runs once with its own samples, gathered with a `groupKey` sized from the sheet; a pair joins one member per key, a patient with two normals stopping the run naming it; a sample reads the control it names, which may feed several, and a reference to no row stops the run naming both (#466).

- A sample's lanes are merged in the run, gathered with a `groupKey` sized from the samplesheet; a one-lane sample passes straight on; lanes that disagree, or a repeated sample and unit, stop the run naming the sample. A fact folded over the study joins every sample's `meta` once every sample has its value (#466).

- Each sample goes down its own branch (#466): a step the samples enter takes only those its tool's rows admit; an index waits for one of its samples; branches rejoin by mixing; each sample's tool is recorded in `decided/<role>.tool.tsv`.

- A row whose second reads file is blank is a single-end sample where pairing varies; a blank required file cell stops the run naming the sample and the column (#466).

- Per-sample facts (#466): the samplesheet carries fact columns, each cell checked before any sample is processed; only rows that leave a measured fact blank are measured, and the measured facts are rejoined after the measuring branch; per-sample tool rules stop a sample naming it; the decided record lists each fact's value and source.

- A run-time setting is emitted as a Groovy lookup over `meta`, from the closed operations only; the measuring branch runs first and its fact is joined into the input by `meta` (`failOnMismatch`); each value used is recorded under `{outdir}/decided/` (#217). The generated measuring step's module (a launcher, the stdlib runner and the pieces) is staged and recorded in `pipeline.yml` (#465). MD0330. `mendel profile` is removed.

- A shared slot passes `[]` in the position of each optional port that is off, and joins each later port its own way (#464).
- An optional channel is emitted as `params.x ? … : <empty tuple>`, and run rules as guards at the workflow's start. `ModuleSpec.optional_emits`; MD0611 reports an optional emit a contract says is always written. Builds stop only on codes `diagnostics.yml` declares refusing (#460).

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

### comeni-flow

#### Added

- A new pure package: the declarative flow engine the builder's conversation was written on —
  the protocol model and its construction checks, the interpreter, forks and the Mermaid
  diagram — made generic over a flow's own phases, events, commands and refusal code, so the
  forge can declare its flow on the same engine (planned) ([#364](https://github.com/comeni-project/Comeni-Labs/issues/364)).

### mendel-authoring

- The memory rendered for the model says how uploaded samples spread over each fact they differ on (#466).

#### Changed

- The protocol engine moved to `comeni-flow`; `PROTOCOL` is declared on it through
  `authoring_protocol(...)`, with no change to the builder's behaviour or its generated diagram
  ([#364](https://github.com/comeni-project/Comeni-Labs/issues/364)).

#### Added

- `read_edit` reads a canvas edit as the intent it means, with the sentence that asks the person
  to confirm it ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395), A1).
- `read_graph` reads a pipeline drawn by hand whole: every tool pinned where its output is, and
  every output nothing reads wanted. `read_edit` reads from a blueprint's sites; a `Reading`
  gives the `DecisionChange` that confirming it writes ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395)).

#### Removed

- The `fork_correction` command, its node and its arrows: a correction after a hand edit lands
  in the same pipeline ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395)).
- Walk progress names the steps still to come (`upcoming`), each with its place in the plan;
  a step whose review still holds is not among them.

- A pure package owns the authoring protocol, typed commands and interpreter. The session's
  current node and named arrows drive transitions; protocol loading checks fork coverage.
- Build plans describe steps, required facts, choices and registry gaps in pipeline order.
  The flow walks the plan, records facts and decisions, and summarizes the resulting pipeline.
- Pacing controls the conversation; tier-4 choices still stop for review. Previously answered
  questions are not asked again. Build and Spawn are consolidated into one authoring flow.

### mendel-api

- Learned rules (#462): `/api/rules/...` proposes rules from people's answers in kept pipelines, one model call per target whose evidence moved (`rule_proposal` table, job `propose_rules`), checks each against the registry, and on approval writes it to the installation's own layer (`MENDEL_OWN_LAYER`, default `<workspace>/layer`), which every build now stacks above the release.

- A study input may be a table of several items (#466): a `tables` change from a checkbox on the input in *What was understood*, offered only on inputs the study shares, while the lanes checkbox is now offered only on per-sample ones; inputs store it (`pipeline_input_revision.table`), and suggestions and turns move to shapes 6 and 10.

- A step that runs on parts of each sample says so on its card, with the tools and why, and *Run each sample whole* keeps it whole: a `whole` change, stored as its own decision family (`pipeline_whole`). Previews, suggestions, turns and drafts move to shapes 9, 5, 9 and 4 (#466).

- A step only some samples take says which, with its rule, on its card and its canvas node (#466); previews migrate to shape 8.

- An input may span several rows per sample (#466): a `units` change, from a checkbox on the input in *What was understood*; inputs store it (`pipeline_input_revision.units`), and suggestions and turns move to shapes 4 and 8.

- Several uploads (#466, #218): an upload takes any number of files, mates paired by name; each sample is measured and kept with the session, with its name and measurements (session shape 3). Facts every sample agrees on are recorded; where they differ, the question says how they spread and proposes an answer to confirm. The model's memory carries each spread, never a sample's name.

- Per-sample facts (#466): the conversation offers *it differs between samples* where everything reading a fact can take a value per sample (a fact's origin `varies`); the step card lists tool rules checked per sample and where each run-time fact comes from. Stored previews, drafts, blueprints, turns and forge items migrate to the new shapes.

- The measurer index lists each measurer with where it runs; the browser sends each file's real size, so a whole small file is measured on all of it (#465). A fact only settings read and the pipeline can measure is not asked (#217).

- Forge drafts read item guide v4 (`forge.draft.v9`): settings from facts, hit policies and derived facts (#461); drafted rules show table findings. The builder asks for a measurement a setting's fact is derived from.
- Forge drafts read item guide v3 (`forge.draft.v8`): shared slots, joins per port, `accepts` inputs and rows on the connected type (#464); the forge shows MD0612. A step card shows the type connected to an `accepts` input and words a condition on a type.
- The builder still asks for an input only optional ports read, such as QUAST's reference,
  but *I don't have one* leaves it out and the conversation goes on (#481).
- The builder asks only for the inputs of producers that can make a wanted type in its
  required states: QUAST's assembly report no longer asks for FastQC's reads (#479).
- The forge's item guide (`items.v2`) says a setting the module falls back on itself, such as
  `task.ext.prefix ?: "${meta.id}"`, has no default (#477).
- A person's choice for a tool's optional input is a decision family (`optional_input`), switched from the step sheet or proposed by the chat (`builder.chat.v8`) under the quote rule. The forge drafts constraints (`forge.draft.v6`) and flags main.nf evidence (MF0530–MF0532). Turn blocks, suggestions and proposals move to shapes 5, 3 and 3 (identity upgrades).
- The forge publishes a draft that extends a shared type once the registry has the added states, and names the missing states otherwise (#473).
- A forge test's expected pattern may match a folder output by the folder's name (#472).
- A forge test may leave an optional input out: the tool runs without it, and validation
  asks only required inputs to be fed (#470).
- The forge chat (`forge.chat.v3`) is shown every item kind and its shape, from one shared
  guide (`forge/prompts/parts/items.v2.md`), so it can add the first constraint, group or
  other item of a kind the draft has none of (#468). Pieces are drafted with `forge.draft.v7`,
  which reads the same guide; it spells out a parameter's `domain` by its `kind`.
- The forge's reviewer (`forge.review.v2`) comments only where it has a concern, and only with a
  verbatim quote. A revision it reads with no concern is recorded as reviewed. Drafted
  questions use `forge.questions.v5`. Both prompts see each type's name, scope and meaning, and
  the engine's findings (#453).
- Questions are drafted with `forge.questions.v7`. A redraft sees only what the person
  settled (answers and removals), so each open question is drafted fresh rather than kept
  from an earlier model's guess. Outputs on nf-core's `versions` topic get no type question.
  Every question carries a suggestion, an output prefers a state of a listed type to a new
  type, and competition is answered `no_rule` or `rule_needed` (#453).
- Pieces after Questions are drafted with `forge.draft.v5`. It names each port's exact
  fields, writes `nf_include` without `.nf`, and gives a directory output `folder`. Every
  piece's redraft, not only Questions, sees only what the person settled (#459).
- Each question option's `new` flag comes from the registry, not the model (#451).
- Type questions carry advisory engine findings (MF0520–MF0522) for scope, duplicate types and
  format, on each item and in the question context (#452).
- Questions have explicit removal with a recorded reason; rejection remains unresolved. Approved
  new question answers permit draft references, while vocabulary declarations remain required
  at Assembly. Contract completion requires a process and a port. Draft prompts distinguish
  approved answers and removed history, and refusals name each invalid field (#428, #431).

- Forge piece pages retain answered questions and show declared details, ordered decisions and
  refusal history. Rule previews run hypothetical facts through the server's resolver with a
  revision check; Forging progress excludes removed items. Assembly, testing and publication show
  their recorded status; Tool pages draw their ports
  ([#429](https://github.com/comeni-project/Comeni-Labs/issues/429)).

- Forge item constructors replace raw JSON for writing and changing questions, contracts,
  settings, vocabulary, rules and tests. Registry pickers, source channel suggestions,
  typed setting defaults and a live preview help build each entry; refused saves retain it
  ([#427](https://github.com/comeni-project/Comeni-Labs/issues/427)).

- Forge questions show module source, upstream descriptions and registry explanations. An optional
  reviewer adds advice for the current item revision, with source-checked quotes; it stays off
  unless explicitly configured in Settings → Models. Registry data is pinned to v0.7.0 (#426).

- `GET /registry/choices` serves every type, job and tool a person can pick from, with what makes
  and reads each, for the forge's searchable pickers.
#### Added

- Forge calls record their tokens, and `forge_step` keeps each step, attempt, refusal and call
  total. `GET /forge/adaptations/{id}/events` reads it and `.../events/stream` follows it.
- A role in the registry is an `id` and a required `explain`. Bare names no longer load, and the job
  picker's data carries the words.
- The forge's chat shows what the AI is doing as it works, says what each reply changed, including
  nothing, keeps a refused draft to a sentence with its details a click away, and resizes. At phone
  width it is a sheet.
- The catalogue filters by what a module reads and makes, by tool suite and by having no topic,
  folds a format's spellings together, and keeps a format only mentioned in a description apart.
  `GET /forge/catalogue/flow` joins the formats on show. The `format` filter is gone.
- Registry releases ([#367](https://github.com/comeni-project/Comeni-Labs/issues/367)): `GET` and
  `POST /forge/releases`, with `forge_release`; an hourly worker cron fetches releases into read-only
  folders under `MENDEL_REGISTRIES_ROOT` and switches only to one that loads. New setting
  `registry.release` (`MENDEL_REGISTRY_RELEASE`).
- Forge pull requests ([#366](https://github.com/comeni-project/Comeni-Labs/issues/366)):
  `POST /forge/adaptations/{id}/publish` and `/approve`, with `forge_pull_request`, at most one
  open. `COMENI_FORGE_GITHUB_TOKEN` now reaches only `mendel-worker`; other services read
  `COMENI_FORGE_GITHUB_TOKEN_SET`. New `MENDEL_REGISTRY_REPO`.
- Forge tests ([#365](https://github.com/comeni-project/Comeni-Labs/issues/365)):
  `POST /forge/adaptations/{id}/tests` runs an assembled draft's tests as Wiener runs from a worker
  job, read by a 30-second cron and stored in `forge_test_run`. Green counts only for the draft it
  ran on. New `MENDEL_WIENER_URL` and, on the worker only, `MENDEL_WIENER_TOKEN`; `httpx` becomes a
  runtime dependency.
- Forging ([#364](https://github.com/comeni-project/Comeni-Labs/issues/364)): `/forge/adaptations` — start (or re-forge), read, a person's
  commands (each against the revision it acts on), the chat, asking the AI to draft, assembling,
  abandoning. Tables `forge_adaptation`, `forge_item`, `forge_revision`, `forge_message`. Model
  calls cross a new declared boundary, `forge_drafting`, carrying public module files and
  registry ids only. Pending vocabulary lets later adaptations use assembled ones'. Codes
  `MF0510`, `MF0513`.
- The forge's catalogue ([#362](https://github.com/comeni-project/Comeni-Labs/issues/362)): `GET /forge/catalogue` lists every nf-core module
  with its state against the loaded registry (imported, update available, unknown version,
  gone upstream, not imported), filtered by state, topic, format and source, searched and
  paged; `GET /forge/catalogue/{source}/{path}` gives one module; `POST
  /forge/catalogue/sync` queues a sync, which the worker also runs daily. A failed sync keeps
  the last good catalogue. `GET /registry/tools/{contract_id}` serves an imported tool's page.
  New tables `catalogue_sync` and `catalogue_module`; codes `MF0502`–`MF0504`.
- A session's chat replies run in the order its messages were sent, at any AI concurrency
  ([#392](https://github.com/comeni-project/Comeni-Labs/issues/392)). A pending proposal says
  when it was asked (`asked_at`); a receipt says what it changed (`about`), and turn blocks move
  to shape 4. What a sample measured is announced in the conversation.
- `GET /pipeline/drafts/{id}/emitted`: the Nextflow a draft compiles to, from its preview, written
  nowhere (`MI0219` while there is no pipeline yet).

- Structural intents are decision families (`role`, `exclusion`, `source`) with history;
  pinning a tool withdraws its exclusion at that site and the reverse. Turn blocks move to
  shape 3 ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395), A1).
- **One builder** ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395)): a hand edit is read, not saved. At any phase, the walk
  included, `POST /authoring/{id}/edits` offers each reading as a suggestion grouped by edit
  (`edit`) and worded by the engine (`says`); a typed value is applied at once. Applying one
  reading applies its edit's group as the person's changes, re-planned as a correction is; an
  intent the engine cannot honour is refused with its code and nothing is kept.
  `DecisionChange` gains `role`, `exclude` and `source`; suggestion changes move to shape 2.
- `POST /drafts/{id}/session` opens a pipeline's conversation, or a new one with nothing said
  that reads a drawn graph back; a drawn pipeline gathers its inputs at its first confirmed
  reading ([#399](https://github.com/comeni-project/Comeni-Labs/issues/399)).
- Persistent authoring sessions support goal extraction, fact gathering, sample uploads,
  read-back, typed answers, build review and resumption. Questions explain their subject,
  affected steps, reason and available answers; uploads can answer missing facts.
- Model-call records retain replies, response format and token usage. Installation settings
  support environment locks, sealed credentials, provider connections and a model per purpose.
- Sample inspection and AI characterisation run as background jobs under protection-level
  checks. Characterisation validates offered identifiers and quoted evidence before using facts.
- Saved whole-pipeline alternatives can be previewed without re-resolving. Corrected goals
  invalidate reviews when their meaning changes.
- Draft deletion removes working content while retaining the specified audit record.
  Cleanup applies retention settings and records deletion counts.

#### Fixed

- A refused forge draft or chat reply now tells the retry why: `forge.questions.v2` and
  `forge.chat.v2` carry the problems, and the questions prompt teaches its item keys
  ([#421](https://github.com/comeni-project/Comeni-Labs/issues/421)).
- Forge assembly names the licence the module's code arrives under, not its tool's, so a tool with
  any licence can be assembled ([#432](https://github.com/comeni-project/Comeni-Labs/issues/432)).
- Authoring actions use one transaction, with jobs queued after commit. Serialized draft
  writes and version checks prevent autosave and background work from overwriting each other.
- Late or duplicated replies cannot silently advance or lock a newer question. Failed jobs
  remain visible; expired sample text cannot be reused by a late characterisation reply.
- Measured-fact conflicts require an explicit choice. Unbuildable corrections persist
  truthfully, while accepted decisions and current answers remain visible in session history.
- Database constraints and migrations align stored enums, JSON shapes and ownership keys.
  Invalid phase filters return a validation response rather than a server error.

- An unanswered setting on a route that leaves the tool its own behaviour is optional:
  `SettingView.optional`, counted apart in `Provenance.optional`, and not named in a pipeline's
  `open_values` ([#384](https://github.com/comeni-project/Comeni-Labs/issues/384)). Saved
  proposal previews move to shape 2. A step card says a setting stays unset only when it may.
- `DraftRow.session` names the conversation a pipeline was built in
  ([#390](https://github.com/comeni-project/Comeni-Labs/issues/390)).
- `SettingView.evidence` says how good the facts a rule read were: *measured* only when every
  one was measured ([#397](https://github.com/comeni-project/Comeni-Labs/issues/397)).

#### Removed

- The separate module source-root setting and mount; registry layers carry module source.
- The fork ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395)): `ownership`, `forked_from` and the fork columns are dropped
  (old forks stay separate pipelines, unlinked), as are the session view's `ownership`,
  `forked_from`, `forked_from_session` and `hand_edits`. A hand edit no longer saves a graph
  or writes a receipt; the walk no longer refuses it (`MI0217` remains for a plain draft `PUT`).
- The old forge's API, worker jobs and tables
  ([#361](https://github.com/comeni-project/Comeni-Labs/issues/361)). The forge, contracts,
  questions, sources and tools routes and their services are gone, as are the nightly source
  sync and drift check, the forge's AI jobs and the `forge_*`, `source_check` and `queue_visit`
  tables (dropped by migration; there is no downgrade). `GET /api/attention` returns only
  `mendel`. The Docker Hub and nightly source-check settings are gone; the GitHub token remains
  for the new forge's publishing. Model-call records keep their `forge` rows.

### comeni-ai

#### Added

- Shared provider transport supports purpose-specific models, system/user message splits,
  cache markers, raw replies and cached-token accounting.
- Provider-specific structured response formats constrain declared answers and preserve null
  where allowed. Server validation remains required; an empty allowed list allows no values.
- `ModelAccess.reasoning_effort`, sent only when set. A `chatgpt/` model signs in through
  LiteLLM with no key (#457).

### mendel-ai

#### Changed

- Mendel model integration uses the shared `comeni-ai` transport. The package split does not
  yet encompass all Mendel prompts or worker orchestration; ownership is tracked in
  [issue #310](https://github.com/comeni-project/Comeni-Labs/issues/310).

### comeni-inspect

#### Changed

- The inspection core runs on the standard library alone, and `measure_cli` runs it over whole files in a pipeline step (#465). Every fact carries `coverage`; codecs open a stream; `--as` keys a report by measurement.

#### Added

- A separate inspection package processes bounded uploaded samples in subprocesses, producing
  measured facts. Compressed samples support truncated stream inspection with expansion limits.

#### Fixed

- Preserve available decompressed bytes from truncated gzip samples, including on Python 3.14.
  The truncated FASTQ fixture now reports all 998 complete records; the previous report lost
  its final 20 records to buffered reads.

### mendel-forge

- The forge drafts measurers (#487). A new last step, **Measurers**, proposes a `by: tool`
  parser of one of the tool's outputs, with its tests, and any new measurement. The parser is
  checked with MD0027 and is never run on Mendel's server. A forge test runs it on the tool's real
  output in Wiener, and is green only when it reports a value. Publishing may drop
  `assertion_only` from a measurement the tool now measures.
- An approved new measurement from the vocabulary step is written to the draft layer; it was
  dropped (#490).

- A tool test leaves out a setting the tool can do without (#217).

- Derived facts are drafted as `rules:derive:<fact>` items and assembled into the layer's `rules/derived/<fact>.yml` (#461).
- Forge tests may leave out a port in a shared slot and name the type of their data for an `accepts` input (#464); an `accepts` input round-trips through forging's items.
- `forging.checks` finds a type question's scope, duplicate-type and format mismatches. They are
  advice only; nothing is refused (#452).
- Explicit Family items in Vocabulary let a reviewed new type such as `assembly.fasta` load
  with its new family at Assembly. Constructors and AI drafting use the registry Family schema;
  pending family dependencies reopen affected items when their supplying draft changes (#441).

- Output questions distinguish content states from file formats. New states require a reviewed
  vocabulary extension before assembly; the forge accepts `add_states` proposals (#426).

- `publishing`: places a proven draft in the registry's layout, runs the registry's checks and
  writes the pull request's record, behind `RegistryPublisher`
  ([#366](https://github.com/comeni-project/Comeni-Labs/issues/366)). The catalogue's *in review* and
  *merged, not released* are real.
- A sixth forging piece, Tests, with `build_test_pipeline`, which builds a test directly so routing
  cannot choose another tool, and the narrow `TestRunner` interface
  ([#365](https://github.com/comeni-project/Comeni-Labs/issues/365)).
#### Added

- Forging ([#364](https://github.com/comeni-project/Comeni-Labs/issues/364)): an adaptation's pieces (questions, contract, parameters,
  vocabulary, rules) as items with append-only revisions; the AI (or the registry, on a
  re-forge) proposes and only a person decides; pieces go in order and a change re-opens what
  depends on it. Item values are the registry's own models; replies are checked against the
  registry and `main.nf`; approved items assemble into a draft layer proven with the builder's
  loader and conformance. The flow is declared on `comeni-flow`. Codes `MF0505`–`MF0509`,
  `MF0511`–`MF0512`.
- The new forge's first part ([#362](https://github.com/comeni-project/Comeni-Labs/issues/362)): the `CatalogueSource` interface and
  `NfCoreSource`, which keeps a blobless clone of `nf-core/modules`; a parser that reads
  everything a module declares (`meta.yml`, `environment.yml`, `main.nf`, its nf-tests); topics
  and formats derived from nf-core's keywords, EDAM terms and file patterns; and each module's
  state against a registry, computed on read. The tool-version rule is shared with the
  registry's version check. Codes `MF0500`–`MF0501`.

#### Removed

- The package, its `forge` CLI and its diagnostic codes (`MF0001`–`MF0406`, and the API's
  `MI0100`–`MI0114` except `MI0106`)
  ([#361](https://github.com/comeni-project/Comeni-Labs/issues/361)). The forge is being
  rebuilt from scratch; until then, registry data is written by hand.

### comeni-vendor

#### Added

- `comeni-vendor add` fetches module source into a registry layer at a pinned commit.
  Offline `check` verifies the recorded digest; `--upstream` checks for upstream movement
  over the network. Laboratory modules with no upstream report unpinned rather than checked.

### wiener-core

#### Added

- `MEASURED` events, Wiener's own: what a run measured and the values its run-time settings took (`wiener_core.measured`), compared with what the pipeline was built on (#465).

#### Added

- A pure event fold models run state. Ingress admits declared Nextflow fields and drops
  undeclared fields; heartbeat time arrives as an internally constructed event.
- Laboratory-authored strings are identified separately from other structured fields.
  Telemetry mapping stays pure, with export handled outside the package.

### wiener-api

- The run form composes each table input with a `name` per row, its files and its item facts, and sends it under its own parameter (`input_tables`, #466).

- The run reads which tool each sample went through when it was chosen per sample, and the run page says so (#466).

- The run form has a `unit` column where a sample may span several rows; a fact folded over the study is read as `folded`; key and reference columns are checked as identifiers, a reference may stay blank (#466).

- The run form lists the samplesheet's fact columns; a decided value lists each fact it read and where it came from (#466).

- When a run completes, what its measuring steps published is read into its record, closed to what its `pipeline.yml` declares; `GET /runs/{id}/measured` says whether each estimate was confirmed (#465).

- A stored artifact says which inputs a run may leave empty and the run rules between them, read from its `pipeline.yml` (#460).
- The image pins Nextflow (26.10.2) and installs `nf-weblog@1.2.0`, which the site config loads: Nextflow 26 has no built-in weblog, so no run reported its end (#471).

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

- **Registry → Learned rules** (#462): each proposed rule with the model's reason, its evidence, the engine's check and what it would change; Approve, Reject, and Withdraw for a rule in use.

- The upload takes every sample at once; current answers list each sample with its measurements, filtered, sorted and grouped (#466).

- The samplesheet editor offers each per-sample fact's values, `auto` where the run measures a blank; the run page says where each decided value's facts came from (#466).

- The step card shows a setting decided at run time with every value it can take; the run page shows what the run measured and flags a disagreement (#217, #465).

#### Added

- Forge question cards (#454):
  - one question open at a time;
  - collapsed rows show the answer or the suggestion and the engine's findings;
  - one card per option merges the registry's name, scope and meaning with the AI's reason;
  - the module's evidence and the engine checks sit above the options;
  - the second opinion is labelled as a model's;
  - on a phone the options fold under "N more".

- Forging ([#364](https://github.com/comeni-project/Comeni-Labs/issues/364)): the Forging tab, an adaptation's page (pieces, items with Approve,
  Change and Reject, *Draft with the AI* or *Write it myself*), the chat with the AI's proposal
  cards, and assembling. *Forge* on the catalogue and *Re-forge* on a tool page start one.
- **The Registry tab** ([#362](https://github.com/comeni-project/Comeni-Labs/issues/362)): the module catalogue (board 1) with filters, search,
  sort and *Sync now*, and an imported tool's page (board 2). Forging, tests and releases are
  drawn and disabled until the parts that bring them.
- **What was asked for and is not offered here is said where the goal is checked**
  ([#293](https://github.com/comeni-project/Comeni-Labs/issues/293), Part I.2): a row in *What
  was understood* and on the goal card, in the person's words. The goal names types the way the
  registry does; a question's mechanical line is dropped where its explanation says why, and
  answered lines are no longer cut short ([#306](https://github.com/comeni-project/Comeni-Labs/issues/306)).

- **The build is one conversation** (one builder plan 3,
  [#392](https://github.com/comeni-project/Comeni-Labs/issues/392),
  [#391](https://github.com/comeni-project/Comeni-Labs/issues/391)): the *Step* and *Assistant*
  tabs become one stream beside the canvas, with a step strip above it. The composer never
  locks; messages sent while the engine works wait in line. Each engine question and step offer
  is a message; once you talk past a question it docks above the composer. A step opens over
  the conversation. Describe uses the same frame, *What was understood* where the canvas will be
  and *Start building* in the header. Changes made elsewhere are announced with a link.
- **A build ends with a hand-over** ([#393](https://github.com/comeni-project/Comeni-Labs/issues/393)):
  what was built, how its values were decided (each count opening the pipeline file), what still
  needs you (each opening its step; Run stays locked), and what next. Composed from the
  engine's records; the wrap-up sentence stays under it.
- **The pipeline file, file first** ([#394](https://github.com/comeni-project/Comeni-Labs/issues/394)):
  each value's line carries a mark of how it was decided, any line of a value opens its reason
  beside the file, the counts filter the file, and *Compile it* shows `main.nf` and
  `nextflow.config`. The values table gives way to the marks and the reason.

- **One builder at `/build`** ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395)): every pipeline opens as a conversation and a
  canvas; `?draft=` and a bare `/build` open or start one. The canvas has the manual builder's
  hands — Delete, wiring by dragging between ports, detaching a wire, picking a step for a port,
  zoom buttons — and the name renames in place. A hand edit's reading waits under *From your
  edit* with *Yes* / *No, undo*.

- Goal and build flows show facts, sources, readable questions, step cards, review history
  and model-call usage. Upload cards expose inspection and characterisation status.
- Settings cover appearance, model connections, purpose-specific models, building, running
  and retention. Locked or unavailable settings explain why they cannot be changed.
- Whole-pipeline previews, retained pipeline views, draft/run deletion and retention controls
  expose the corresponding backend operations.

#### Fixed

- The canvas uses a consistent frame for retained and previewed pipelines. Session answers,
  progress and alternative views reflect saved state; duplicate React keys are corrected.

- From the walk of the redesign with a real model
  ([#384](https://github.com/comeni-project/Comeni-Labs/issues/384)–[#390](https://github.com/comeni-project/Comeni-Labs/issues/390)):
  Run stays locked and the build says *built*, not *complete*, while a value needs you, and the
  panel names the step that does; an optional value is asked as optional and says what happens
  if it is left; after *Add it* the panel follows the next offer; a step card leads with what
  the tool does and says nothing twice; a wire passing a column turns in the gap before its
  target; the session canvas draws the minimap; Home and ⌘K open a pipeline in its conversation.
- A rule's value or step is never called *measured* because of its tier: its premise may be one
  you typed. Counts and chips follow what the rule read
  ([#387](https://github.com/comeni-project/Comeni-Labs/issues/387),
  [#397](https://github.com/comeni-project/Comeni-Labs/issues/397); a regression of #268).

#### Changed

- The interface takes the identity shared with Comeni Code: light first with a dark palette
  that follows the system, Lexend for the interface and Geist Mono for data, one meaning per
  colour (done, the main action, measured, needs you, selected/now), rounder controls and a
  raised main button. The animated background field is removed. The rules are in
  `docs/explanation/visual-identity.md`.
- The header carries the product's mark, *Build · Runs*, a jump search over saved pipelines
  and recent runs (⌘K or Ctrl+K from any page), help linking to the documentation, and
  settings. *Registry* returns with the new forge.
- Describing and building follow the engine rather than a chat transcript
  ([#377](https://github.com/comeni-project/Comeni-Labs/issues/377)). Until there is
  something to draw, the builder is a describe page: the sentence, the card waiting for an
  answer, and what was understood. After that, the canvas sits beside a panel with two tabs.
  *Step* holds the plan as a line (decided steps and who settled them, the step on offer and how
  many are to come), the card waiting and changes proposed in conversation. *Assistant* is the
  conversation itself. The canvas brings the offered or selected step into view.
- The pipeline file is a page beside the canvas rather than a drawer
  ([#379](https://github.com/comeni-project/Comeni-Labs/issues/379)). Every value appears
  with how it was decided and why, beside the `pipeline.yml` text, whose open values are
  marked. The page can be filtered to open values only, and the file can be downloaded. The
  header counts the values that need you. The run sheet is laid out as numbered sections
  (*Checked*, *Your files*, *Values still open*), with a summary that holds the run action.
- Home leads with a describe box. Below it, cards say what needs you (each pipeline's open
  values, with *Answer*), what is running and what went wrong; each card is drawn only when it
  has something to show. Your pipelines say in words how their values were decided, and finished
  runs appear under *Results ready*. No owner or *started by* appears
  ([#378](https://github.com/comeni-project/Comeni-Labs/issues/378)).
- The runs board names each run by its pipeline, filters by outcome with tabs, and drops the
  executor and submitter columns, along with the summary tiles and the per-day chart. Each row
  still compares a finished run with its pipeline's usual time. A run opens on its failure:
  the failed task's attempts, each showing its peak against the memory it asked for, sit beside
  what Nextflow reported, as written. The run header has *Console* and *Open the pipeline*
  ([#380](https://github.com/comeni-project/Comeni-Labs/issues/380)).
- The settings overlay's own words (its subtitle, *Esc*, the `.env` note and section counts) are
  in the interface font rather than the data font
  ([#381](https://github.com/comeni-project/Comeni-Labs/issues/381)).
- The screens are redrawn to match the redesign boards
  ([#370](https://github.com/comeni-project/Comeni-Labs/issues/370)). The builder's header says
  where the build is as a chip. The canvas is a framed card with a caption, *Fit* and a legend;
  steps are outlined and count their values (*1 measured · 2 settled*). The plan line colours
  how far the walk has reached and names the steps still to come. The step card offers its tools
  as radio cards with *Add it* and *Why this one?*. Opening a step asks each value that needs you
  as a question, and the answer is saved with your reason. Describe shows the goal as *What was
  understood*, a line per input, output and fact with where each came from. When pacing is set
  to ask, *Start building* also answers how to go through the build. The pipeline file has
  section chips; the run sheet sits in the page with *Your files* first. Home links *All
  results*. A failed run says what its exit code is from the recorded signal, without
  guessing a cause.

#### Removed

- The old forge's screens: the *Registry* tab and every `/forge…` page
  ([#361](https://github.com/comeni-project/Comeni-Labs/issues/361)). Those addresses are now
  unknown pages. A refusal's code is looked up with `mendel explain`.

- The manual builder (`Builder`), its rail, status line, findings panel, wires and draft hook,
  the `/build/living` route, the example opened at a bare `/build`, and the fork's links
  ([#395](https://github.com/comeni-project/Comeni-Labs/issues/395)).

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
