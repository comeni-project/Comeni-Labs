# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Registry data — contracts, rules, vocabularies, measurements — moves to its own repository
at Plan 2.5 and will version separately. Until then it lives in `examples/` as test
fixtures rather than as a shipped registry.

## [Unreleased]

### Fixed

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
  wearing a tier-3 badge. One rule remains in `examples/rules/rnaseq.yml`, and it is a genuine
  decision between two defensible aligners.

## [0.1.0] — 2026-08-03

The deterministic core. A typed goal becomes a runnable Nextflow pipeline with no AI
involved anywhere, and every choice carries a tier.

### Added

**Pipeline construction**

- `mendel build` — goal in, pipeline directory out: `main.nf`, `nextflow.config`,
  `pipeline.ir.json` and the vendored module tree.
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
