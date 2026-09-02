# Cutting a release

Every package here versions **independently** and is tagged on its own — the tag is
`<package>-v<version>`, so `comeni-core-v0.2.0`. Pushing that tag is the whole request: a
workflow builds it, reads its notes out of the changelog, and cuts a GitHub Release.

> **No release has been cut yet.** As of 2026-09-02 the repository has no tags and no
> releases, so if you are reading this you are the first — expect to find something this
> page does not cover, and add it. Every package is at `0.1.0` except `comeni-core`, which
> is at `0.2.0` in its `pyproject.toml` and untagged.

## Which number moves

**This is the part people get wrong, so it comes first.**

| the change | bump | example |
|---|---|---|
| a fix, a message, an internal refactor | **`0.0.x`** | `MD0223`'s wording; splitting a module with no change to its surface |
| new behaviour — a new field, a new setting, a new diagnostic code | **`0.x.0`** | `MD0001`–`MD0009`; `Pipeline.ai`; a new `derives:` transform |
| the artifact format moves, or a public surface breaks | **`x.0.0`** | `pipeline.yml` version 3 → 4; a renamed CLI verb |

Three rules that follow from that table but are not obvious in it:

**A new diagnostic code is a feature, not a fix.** It only ever refuses, so it feels like a
tightening — but a laboratory runbook can cite `MD0002`, which makes its arrival new surface
somebody can depend on. That is the same reasoning that means a code is *never renumbered*.

**A `SCHEMA_VERSION` bump is always `x.0.0` for `comeni-core`.** `pipeline.yml`'s version lives
there, and a file written by a newer Mendel is refused by an older one (`MD0207`). That is the
definition of a break, and naming it here means nobody has to argue it case by case.

**The bump is judged, not derived.** Nothing in the release workflow can tell a fix from a
feature; its job is to refuse a tag that disagrees with the version in `pyproject.toml`, not to
decide which number was right. A wrong bump is a review comment, which is why the version lands
in a pull request before it lands in a tag.

**Before `1.0.0`, `0.x.0` may still break something.** The table is the discipline this project
holds itself to, not a promise semantic versioning makes on its behalf — under semver everything
below `1.0.0` is permitted to break. If you break a surface, say so in the changelog entry
whichever number you moved.

## The procedure

1. **Write the changelog entry.** In `CHANGELOG.md`, under `## [Unreleased]`, in the
   `### <package>` section. If there is no section for your package, add one.
2. **Move `[Unreleased]` to a version heading** — `## [0.2.0] - 2026-09-01` — and open a fresh
   empty `## [Unreleased]` above it.
3. **Bump the version** in that package's `pyproject.toml`. It must match the heading exactly;
   the workflow refuses if it does not.
4. **Commit and open a pull request.** The version and the notes get reviewed like anything
   else — this is where a wrong bump gets caught.
5. **After it merges, tag and push:**

   ```bash
   git checkout main && git pull
   git tag comeni-core-v0.2.0
   git push origin comeni-core-v0.2.0
   ```

6. **Watch it.** `gh run watch` — the workflow checks the tag against the manifest, runs
   `make check`, extracts your notes, builds an sdist and a wheel, and cuts the Release.

## What the workflow refuses, and why

| it refuses when | because |
|---|---|
| the tag names no package under `packages/` | the format is `<package>-v<version>`; a typo would otherwise release nothing quietly |
| the tag's version and `pyproject.toml` disagree | a tag is a claim about a version, and the two disagreeing is the release-time shape of `MD0223` |
| the changelog has no `### <package>` under that version | a release cut with empty notes is worse than one that failed to cut — it looks finished |
| `make check` fails | nothing ships from a red tree |

It gates on `make check` rather than `make verify`: `verify` needs Docker and the slow lane, and
the nightly workflow already runs those against `main`. A release blocked on a container pull is
a release people stop cutting.

## What this does not do

**No PyPI.** GitHub Releases only, decided 2026-08-16. `uv` installs straight from a git tag, so
nothing is blocked, and a published PyPI version cannot be withdrawn — only yanked. That is a
`1.0.0` decision.

```bash
uv add "comeni-core @ git+https://github.com/comeni-project/Comeni-Labs@comeni-core-v0.2.0#subdirectory=packages/comeni-core"
```

**No signing.** `comeni-registry` plans signed tags ([`federation.md`](../design/federation.md)
§3); signing engine releases is a separate design with a key-management question attached.

**No automatic version bumping.** Tools that do it want to own the changelog too, and this one is
written by hand on purpose — in the same register as the working notes, carrying the reasoning
rather than a list of commit subjects.

## Dependencies between packages

Each package declares a **lower bound and no cap** on the workspace packages it imports:
`comeni-core>=0.1.0`. The bound is what makes an independent version mean anything — without it
a released wheel accepts a `comeni-core` predating a type it imports.

A cap would be a promise to bump in lockstep: `mendel-compiler` pinning `comeni-core<0.3` means
every `comeni-core` minor release breaks the compiler until somebody edits a file. Both
directions are enforced by `tests/test_packaging.py`.

**Raise a lower bound when you start depending on something new.** Adding a field to
`comeni-core` and using it from `mendel-compiler` means `mendel-compiler` now needs that version,
and nothing infers that for you.
