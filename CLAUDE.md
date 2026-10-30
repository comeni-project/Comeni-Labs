# Comeni Labs

Comeni helps a researcher describe an analysis, build a Nextflow pipeline, run it and
watch the result. Mendel owns describe/build; Wiener owns run/watch. Comeni-Code is a
separate project and is outside this repository's scope.

Construction uses declared contracts, rules and measured facts. Unsettled choices become
typed questions with reasons and legal answers; people or models answer those questions.
The engine records the decisions and emits the pipeline. Explain that boundary when
introducing the project: a model's contribution must remain visible and reviewable.

## Before working

- Read [current work](docs/notes/now.md), then the relevant source and tests. The
  [journal](docs/notes/journal) records completed work; GitHub issue #119 is the task tree.
- Check the branch, worktree and working tree before editing. Use a feature branch and
  preserve other agents' changes. Worktree submodule configuration is shared: never run
  `git submodule deinit` inside a worktree.
- Treat [Architecture](docs/explanation/architecture.md) as background requiring verification against
  code. Its detailed sections are awaiting revision. Current notes and design documents can also lag the code;
  distinguish an implemented behavior from a proposal.
- This brief has a 300-line budget, checked by `make doc-sizes`. Put temporary status in
  current notes, detailed rationale in design documents, and local caveats beside the code.

## Working agreements

- Follow the user's requested scope. A documentation pass changes documentation; report
  implementation problems separately. Do not turn an audit into an unsolicited refactor.
- Record defects in GitHub issues before implementation. For rule, protocol or ownership
  changes, explain the alternatives and costs so the operator can choose. The
  [walking procedure](docs/how-to/development/investigate.md) describes the issue and decision workflow.
- Before code changes, agree on the approach. Design work proceeds through an approved
  spec and plan; a mechanical fix needs a short approved approach. Existing explicit
  authorization carries forward, including the user's choice to proceed without those steps.
- Specs and plans live in `docs/superpowers/specs/` and `docs/superpowers/plans/`.
  Ground them in existing code. Tick completed steps, record deviations, and archive finished
  documents beside them. Do not backfill old plans.
- Execute the agreed plan yourself. Subagents are for review or design when requested,
  rather than the default implementation workflow.
- If the work grows to roughly twice the estimate, explain the cause and revised cost.
  Tune a rule that is too strict or too permissive; do not bypass it just to finish.
- Verify the relevant behavior. A regression guard must fail against the defect it claims
  to detect; record invariant-guard evidence in `tests/fixtures/guard-ledger.md`.
  Check that a cited test exists and exercises the claimed path.
- Inspect UI changes in a browser, including the intended viewport. Where an artboard
  exists, compare it visually; DOM tests cannot establish layout correctness.
- Compact completed journal work using [the compaction procedure](docs/notes/compaction.md).

## Boundaries to preserve

Read [the invariants](docs/explanation/invariants.md) for rationale; verify implementation
claims in source and guards before repeating them.

- Pure packages (`comeni-core`, `comeni-flow`, `mendel-resolver`, `mendel-compiler`,
  `mendel-authoring`, `wiener-core`, `dag-core`) do not perform network I/O. Keep adapters outside them.
  Static and runtime purity guards provide partial coverage, not a security sandbox.
  Wiener receives time as an event rather than reading the clock inside its fold.
- Registry proposals require human approval. Runtime resolution reads declared data;
  it does not automatically write new registry entries. Vocabularies and states are closed.
- Model calls use declared AI points and typed egress payloads. Validate offered IDs and
  legal answers at the receiving boundary, even if a provider enforces an output schema.
  A tier-3 rule miss or routing tie becomes a tier-4 question; tier 4 remains flagged for review.
- Preserve why a choice was made, who answered it and the supplying layer. Replays use
  recorded decisions. The same inputs and recorded decisions must reproduce the output;
  sort unordered collections before serializing them.
- Repair changes the IR and re-emits. Do not patch generated Nextflow as a substitute.
  Check the implementation before claiming a repair agent exists.
- Registry layers stack by position, not display name. Record displacements and pin
  contracts, module source and layers by content digest. A contract's declared ports must
  agree with readable module source; absent source is unverified, not confirmed conformance.
- `pipeline.yml` is the saved pipeline, including settings and decision provenance.
  Publication verifies the saved artifact and emitted files; it must not silently re-resolve.
- Use API keys or local models, not subscription OAuth. Self-hosting must retain the same
  construction capabilities and reproducible output. Telemetry is opt-in and off by default.
- Data crosses boundaries only through declared payloads. Sample inspection and model
  characterisation are explicit exceptions controlled by protection level. Inspect the current
  upload, egress and retention code before making privacy claims: sampled file text can reach
  a model and stored replies at level 0. Do not promise that only measured facts are retained.

## Documentation and public claims

Use the [documentation style guide](docs/how-to/development/documentation.md) when editing
pages. The [docs homepage](docs/index.md) connects tutorials, how-to guides, reference and
explanation. Give each maintained subject one home and link to it from other paths.

Before rewriting, inventory useful behavior, constraints, prerequisites, examples and
rationale. Retain them or record where they moved; report meaningful removals. Use
`redocument-file` for a file or related group when available. Keep comments about current
purpose; put release history in `CHANGELOG.md` and session history in working notes.
Derive volatile counts from commands or source rather than copying them into prose.

User-facing pages should use the user's task and vocabulary. Package and service names
belong in developer documentation when they help explain ownership. Do not imply that AI
writes unrestricted pipeline code or that unresolved choices disappear without review.

This is a public repository. Do not discuss auto-phylo. Curated tools are reference material
for a lab to validate, not validated clinical tests. Do not claim IVDR, CLIA, CAP or ISO 15189
compliance, call data anonymised, or promise cloud data handling that has not been decided.

## Source map

| Area | Start here |
|---|---|
| Shared types, contracts, artifact schema and diagnostics | `packages/comeni-core/` |
| Routing, rules and decision tiers | `packages/mendel-resolver/` |
| Nextflow emission, conformance and gates | `packages/mendel-compiler/` |
| Authoring protocol / the shared flow engine and interpreter | `packages/mendel-authoring/`, `packages/comeni-flow/` |
| Build sessions, API, jobs and installation settings | `packages/mendel-api/` |
| Shared provider transport / Mendel model integration | `packages/comeni-ai/`, `packages/mendel-ai/` |
| The forge: module catalogue, sources and state against the registry (#360) | `packages/mendel-forge/` |
| Module fetching into a registry layer | `packages/comeni-vendor/` |
| Sample inspection subprocesses | `packages/comeni-inspect/` |
| Run-state fold / execution API and worker | `packages/wiener-core/`, `packages/wiener-api/` |
| Shared graph layout / browser application | `packages/dag-core/`, `frontend/` |
| Services, images and developer commands | `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile`, `Makefile` |

The registry is the `registry/` submodule, with its own releases and licence. Initialize it
with `git submodule update --init`. Land registry changes in a writable checkout of that
repository, not the detached submodule. Generated clients in `frontend/src/api/` are rebuilt
with `make client`; do not edit them by hand. Diagnostics are declared in
`packages/comeni-core/src/comeni_core/diagnostics.yml` and emitted through `coded()`.

## Dependency lockfile

`pyproject.toml` declares dependencies; `uv.lock` records the resolved workspace and
third-party versions. Its download URLs and hashes cover multiple platforms and Python
versions, not packages all installed at once. Keep this generated file committed; do not
hand-edit it or add explanatory comments that regeneration would discard.

Use `uv lock --check` to check freshness and `uv tree --locked` to inspect relationships.
Change dependency declarations first, then regenerate with `uv lock`. Use
`uv lock --upgrade-package <package>` for a deliberate targeted upgrade and review its diff.
CI uses `--locked`, which refuses stale metadata; Docker uses `--frozen`, which reads the
lockfile without checking freshness. See [uv's locking guide](https://docs.astral.sh/uv/concepts/projects/sync/).

## Checks and operational cautions

The [contributing guide](docs/how-to/development/contribute.md) owns human setup and review
instructions. `make help` describes available commands. Read [the testing guide](tests/README.md) before
adding tests. Run Python tests from the repository root and use `support.paths` for root
lookup. Assert that collections are nonempty before checking each item. Use deterministic
fixtures for pure behavior and recorded responses for model calls; do not call live models
from tests.

```bash
uv sync                      # install workspace dependencies
make test-db                 # start and migrate the isolated test databases
make test                    # Python tests against those databases
make check                   # lint, tests, types and documentation checks
make guards                  # purity, egress and construction invariants
make verify                  # check plus slow execution tests and guards
make static                  # example build and Nextflow lint/preview
make dev                     # local service stack and Vite
make client                  # regenerate API clients
cd frontend && npx vitest run && npx tsc -b
```

Database fixtures truncate tables. Bare `uv run pytest` can inherit development database
settings from `.env`; use the Make targets and confirm database URLs before running fixtures.
`make check` omits slow real-tool tests. Use `make verify` after changing resolution, routing,
compiler CLI/emission or the saved pipeline schema; it needs Docker and Nextflow. Gate tests
also need their declared executables and containers, so check CI job setup before adding them.

The Wiener worker has the host Docker socket, which grants host-level control. Preserve its
authentication boundary and mount the run directory at the same absolute path inside and
outside the container. Mendel's development API reloads mounted source; background workers
need a restart after changes. Check Compose mounts before deciding whether a rebuild is needed.

Packages version independently with tags such as `comeni-core-v0.2.0`. Read
[the release procedure](docs/how-to/development/release.md) before tagging. `CHANGELOG.md` records
notable unreleased changes by package, not every commit; registry changes belong in its own
repository. Preserve historical release entries. GitHub Actions are pinned by commit SHA.
Releases go to GitHub Releases, not PyPI. Code is Apache-2.0; registry data is CC-BY-4.0.
