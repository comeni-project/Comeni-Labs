# Contribute to Comeni Labs

<!--
Serves: all four steps.
-->

Platform code is maintained in this repository. Tool contracts, rules, measurements
and vocabulary are maintained in
[comeni-registry](https://github.com/comeni-project/comeni-registry).
For registry work, start with [writing a contract](../registry/add-tool.md)
or [writing a rule](../registry/write-rule.md).
A change spanning both repositories needs separate pull requests; submit the registry
change first.

## Set up development

Install `uv` and Git. Running the app also requires Docker with Compose and Node.js
with npm. Execution gates require Nextflow and Java.

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
```

For an existing clone without registry data, run `git submodule update --init`.
The registry submodule pins the data used by the platform. Land registry changes in a
writable checkout of its own repository, rather than its detached submodule here.
Never run `git submodule deinit` inside a worktree: submodule configuration is shared.

Read [Architecture](../../explanation/architecture.md) for component ownership and the build path. Use a feature branch, check the working tree before editing, and preserve
unrelated changes. To run the app, follow the [local stack guide](local-stack.md).

## Check a change

Read the repository's `tests/README.md` before adding tests. Run Python tests from the
repository root. Start isolated test databases, then run the regular checks:

```bash
make test-db
make check
```

`make test-db` needs Docker and prepares both databases on localhost:5442.
`make check` runs lint, Python tests, generated type and reference checks, documentation
status, links, source-path checks and document-size checks. Its tests use the isolated
database URLs. Without reachable test databases, database cases can skip; CI requires
them to run.

Database fixtures truncate tables. Bare `uv run pytest` can inherit development
settings from `.env`; use the Make targets and confirm database URLs before running
fixtures. Do not point tests at a database whose contents you need to keep.

For a change to resolution, routing, compiler CLI/emission or the saved pipeline schema:

```bash
make verify
```

This runs the regular checks, slow execution tests and invariant guards in sequence.
It needs Docker and Nextflow. `make stub` exercises the example pipeline with a stub
execution gate; initial image downloads can make it substantially slower than a warm run.

For frontend changes:

```bash
cd frontend
npx vitest run
npx tsc -b
```

Inspect UI changes in a browser at the intended viewport. DOM tests cannot establish
layout correctness. If an artboard exists, compare the rendered screen against it.

## Preserve design boundaries

Read [the invariants](../../explanation/invariants.md) for the rationale behind these boundaries.
Use `make guards` to run the focused checks:

| Guard | Scope |
|---|---|
| `tests/guards/test_purity.py` and `test_purity_runtime.py` | Static and runtime checks for pure-package boundaries; coverage is partial. |
| `tests/guards/test_egress.py` | Declared model-request payloads and outbound data boundaries. |
| `tests/guards/test_construction.py` | Approved construction and validation of measurement profiles. |

Keep network adapters outside pure packages. If an operation needs I/O, explain the
adapter seam instead of adding a banned import. Changes to egress payloads or profile
construction need corresponding guard review.

The same inputs and recorded decisions must reproduce the output. Sort unordered
collections before serialization. Resolution uses declared, approved registry data
and decision records; do not use fuzzy retrieval to influence resolution.

Read process names and container declarations from `registry/tools/**/module/main.nf`,
then check the contract against the module. Vendored `nf-core` source is kept verbatim;
module changes belong upstream. Use `comeni-vendor add` to replace source and
`comeni-vendor check` to detect local edits.

## Work and review

Record defects before implementation. For a rule, protocol or ownership change, explain
the alternatives and costs and agree on the approach. Design work uses approved specs
and plans in `docs/superpowers/specs/` and `docs/superpowers/plans/`; a mechanical fix
needs a short agreed approach. Follow the user's explicitly authorized workflow.
The [walking procedure](investigate.md) describes issue handling and decision records.

Write a regression test before fixing a defect, and watch it fail for the intended
reason. For an invariant guard, deliberately introduce the prohibited behavior, confirm
that the guard catches it, then restore the code. Record the evidence in
`tests/fixtures/guard-ledger.md`. Read generated clients, type stubs and golden files
before including them in a change.

Python uses Ruff with a 100-character line length. `make lint` checks it; `make fmt`
rewrites files and is not a CI gate. Keep formatting changes scoped and review the diff.
Comments should explain current purpose, constraints and non-obvious reasons. Match the
surrounding code's conventions without carrying forward incidental bug history.

Use conventional commit prefixes such as `feat(scope):`, `fix:`, `docs:`, `test:` and
`chore:`. Describe the problem, resulting behavior and useful rationale. In the pull
request, identify the decision tier when a change affects a choice, and include failure
evidence when adding a guard. Update documentation for changed schemas, flags or
observable behavior.

## Add a diagnostic

1. Declare the code in `packages/comeni-core/src/comeni_core/diagnostics.yml`, in the
   appropriate band. Set `emitted_by` to the emitting package, `says` to the short message,
   `fix` to the corrective action and `explanation` to the text shown by `mendel explain`.
2. Emit it through `coded()` so its identity is validated:

   ```python
   from comeni_core.diagnostics import coded

   raise ValueError(coded("MD0002", f"{path} is not a valid contract"))
   ```

3. Regenerate the diagnostics page with
   `uv run python tools/generate_diagnostics_doc.py`, then run `make docs` to check it.
   The generated page must not be edited by hand.
4. Declare only codes that can actually be emitted. Reserve a band with a comment,
   rather than adding unused entries.

Published codes are never renumbered: lab runbooks may cite them. Adding a diagnostic
is a feature for versioning purposes; see [releasing](release.md).

## Releases, licensing and conduct

Packages version independently with tags such as `comeni-core-v0.2.0`. Review the
version bump in the pull request: a fix changes the patch version, a feature the minor
version, and a breaking change the major version. Follow [the release procedure](release.md).
Record notable unreleased changes by package in the root `CHANGELOG.md`; registry
changes belong in the registry repository's changelog.

Code is Apache-2.0; registry data is CC-BY-4.0 in its own repository. Vendored modules
retain their own licences. Contributions use the licence of the material they change.

Be civil and discuss the work respectfully. There is no separate code of conduct.
Report security or privacy vulnerabilities privately through
[the security policy](https://github.com/comeni-project/Comeni-Labs/blob/main/.github/SECURITY.md), including unintended sensitive data in a goal or model payload,
data disclosure, or an egress-boundary bypass.
