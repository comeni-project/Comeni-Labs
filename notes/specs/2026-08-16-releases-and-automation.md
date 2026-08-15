# Releases, tags, and repository automation

**Written 2026-08-16 against the tree at `0acd2d7`.** The trigger is that the Actions are three
to five majors behind and every run prints a Node 20 deprecation warning; the larger point is
that **this repository has no tags and no releases at all**, and it is about to grow components
that ship on their own cadence.

## 1. What is actually wrong

**The Actions are stale, measurably.**

| action | pinned | latest |
|---|---|---|
| `actions/checkout` | v4 | v7.0.1 |
| `actions/upload-artifact` | v4 | v7.0.1 |
| `astral-sh/setup-uv` | v5 | v10.0.1 |
| `nf-core/setup-nextflow` | v2 | v3.0.1 |

**There is no release.** `git tag` is empty. Four `pyproject.toml` files say `version = "0.1.0"`
and always have. `CHANGELOG.md` has an `[Unreleased]` section and nothing else, so the changelog
is a list of things that have never been released.

**Inter-package dependencies carry no version constraints.** `mendel-compiler` declares
`dependencies = ["comeni-core", "mendel-resolver"]`. In a `uv` workspace that resolves to the
checkout and is fine. As a *released* artifact it is meaningless: a `mendel-compiler` tarball
would accept any `comeni-core`, including one predating a type it imports.

**`emitted_by` says something false about roughly a third of the diagnostic registry.** Its
docstring is *"Which subsystem raises it"*, and `EmittedBy` is `compiler | resolver | forge |
api` — with **no `core`**. But `comeni-core` holds `pipeline.py`'s validators, so `MD0207`,
`MD0212`, `MD0216`–`MD0221`, `MD0225` and others claim `compiler` while raising in
`comeni-core`. Six of the nine codes added on 2026-08-16 are wrong the same way, and they were
written that way because the vocabulary offered no truthful option. **Nothing checks it**, which
is why the count is roughly twenty rather than one.

## 2. The shape: mirror the components, name them readably

The diagnostic prefixes already encode the component boundaries — `MD` for Mendel's
deterministic core, `MF` for the forge, `MA` for the API, `MI` for the AI adapters, with `N` and
`W` reserved for Nightingale and Wiener. That taxonomy is the release taxonomy.

**Tags are per package, spelled out.** `comeni-core-v0.2.0`, `mendel-resolver-v0.2.0`,
`mendel-compiler-v0.2.0`, and later `mendel-forge-v…`, `mendel-ai-v…`, `mendel-api-v…`. A
prefix-derived scheme (`md/v0.2.0`) was considered and rejected by the operator for being
unreadable, and the objection is right: a tag is read far more often than it is parsed.
`comeni-registry` keeps its bare `v0.2.0`, because it is already alone in its repository.

**Versions are independent.** A change to `comeni-core` does not bump `mendel-compiler`.
Lockstep was considered — the three share invariant 1 and the `MD` prefix — and rejected,
because "treat it as a multi-repo" is the operator's stated intent and lockstep is precisely the
thing that has to be undone the day the forge ships separately.

**Independence is only real if the constraints are.** Each inter-package dependency gains a
lower bound: `comeni-core>=0.2.0`. Without that, "independent" means "unverified".

## 3. `emitted_by` is made true

`EmittedBy` gains **`CORE = "core"`**, every mislabelled entry is corrected, and a guard derives
the answer from the source rather than trusting the label:

> for every code in the registry, find the package whose source constructs a message beginning
> with that code, and refuse if it is not the package `emitted_by` names.

**A code with no raise site is not a failure.** `MD0100` is not an error condition, some codes
are raised through a `Diagnostic` object rather than an f-string, and a reserved code has no site
yet. The guard reports what it *could not locate* separately from what it found *wrong*, because
a check that conflates "absent" with "mismatched" gets switched off.

**Why this belongs in the release work rather than in its own plan.** Per-package releases need
to answer *what changed in this package*, and the diagnostic registry is the one place that maps
behaviour to component. A release note saying "adds `MD0001`–`MD0009`" is only true if the codes
know which package they belong to.

**`emitted_by` also stops being a synonym for the CLI's grouping.** The generated document groups
by `concern`, not by `emitted_by`, so correcting these labels changes no published page — which
is what makes it a safe repair rather than a churn of the reference.

## 4. What the automation is

**Every action pinned by SHA, with the version in a trailing comment.** A mutable `@v7` tag can
be repointed at any commit by whoever controls the action. This repository takes some trouble
over what code runs inside it — invariant 1's whole posture — and a supply chain that resolves by
tag is the inconsistent part of that. The comment is what keeps a SHA readable and what
Dependabot rewrites.

**Dependabot, weekly, grouped**, for `github-actions` and `uv`. Without it these go stale again
by exactly the mechanism that produced this spec. Grouped so a week of patches is one pull
request rather than nine.

**A release workflow driven by the tag.** Pushing `comeni-core-v0.2.0` runs the full gate, builds
the sdist and wheel, extracts that package's section from the changelog, and cuts a GitHub
Release with the artifacts attached. **It refuses if the tag and the package's
`pyproject.toml` version disagree** — a tag is a claim about a version, and the two disagreeing is
the release-time version of `MD0223`.

**No PyPI.** Decided by the operator: GitHub Releases only, for now. `uv` installs from a git
tag, so nothing is blocked, and a published PyPI version cannot be withdrawn — only yanked. PyPI
is a v1 decision.

**No release-please or similar.** It wants to own the changelog and the version bump, and this
repository's changelog is written by hand on purpose, in the same register as the journal. A bot
rewriting it would flatten exactly the part that carries the reasoning.

## 5. The changelog stays one file

One `CHANGELOG.md` with a section per package under each version heading, rather than a changelog
per package. The repository is one repository today; splitting the changelog before splitting the
repository would leave four files that all describe the same commits. The release workflow
extracts a package's section by heading, so the split can happen later without changing the
mechanism.

**Two stale claims in it are repaired while we are here.** It says registry data *"moves to its
own repository at Plan 1.7"* — it moved on 2026-08-16, in issue #46 — and it says registry data
*"lives in `examples/`"*, which stopped being true several plans ago.

## 6. When to bump what — the policy, written down

**Decided by the operator on 2026-08-16.** The whole point of independent versions is that a
number means something, and it only means something if everyone bumps by the same rule.

| change | bump | example |
|---|---|---|
| a minor code change — a fix, a message, an internal refactor | **`0.0.x`** | `MD0223`'s wording; splitting a module with no surface change |
| a feature — new behaviour, a new field, a new diagnostic code | **`0.x.0`** | `MD0001`–`MD0009`; `Pipeline.ai`; a new `derives:` transform |
| a big release — the artifact format moves, or a public surface breaks | **`x.0.0`** | `pipeline.yml` version 3 → 4; a renamed CLI verb |

**Read the middle row generously.** A new diagnostic code is a feature even though it only ever
refuses: a laboratory runbook can cite `MD0002`, so its arrival is new surface a consumer can
depend on. That is the same reasoning that makes a code never renumbered.

**The bump is judged, not derived, and this is the one place that is admitted.** Nothing in the
release workflow can tell a fix from a feature; the workflow's job is to refuse a tag that
disagrees with its `pyproject.toml`, not to decide which number was right. A wrong bump is a
review comment.

**A `pipeline.yml` schema bump is always `x.0.0` for `comeni-core`**, because `SCHEMA_VERSION`
lives there and a file written by a newer Mendel is refused by an older one (`MD0207`). That is
the definition of a break, and it is worth naming so nobody argues it case by case.

**This policy lives in `docs/guides/releasing.md`**, next to the procedure, rather than only
here — a working note is not where somebody cutting a release will look.

## 7. What is not in scope

- **No signing.** `comeni-registry` plans signed tags (`federation.md` §3); signing engine
  releases is a separate design with a key-management question attached.
- **No PyPI**, per §4.
- **No version bumps.** This ships the machinery and tags the current state as `0.1.0`; deciding
  that anything here is `0.2.0` is a judgement about the code, not about the automation.
- **A14** stays out, as it has all week.

## 8. Success criterion

`docs/guides/releasing.md` states the bump policy and the procedure, and
`git tag comeni-core-v0.1.0 && git push --tags` produces a GitHub Release with an sdist, a wheel
and the changelog section, and the same command with a mismatched version refuses. Dependabot
opens grouped pull requests. Every action resolves to a SHA. `emitted_by` names the package that
actually raises each code, and a test fails if that stops being true.
