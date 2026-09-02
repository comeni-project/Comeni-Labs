# Contributing

Thank you for considering it. This document covers how to set up, what the project cares
about, and what a reviewable change looks like.

## Two kinds of contribution

**Adding a tool** is the most useful thing you can do, and it needs no Python. A tool definition
is a YAML file with a citation.

- [Adding a tool](../docs/guides/writing-a-contract.md)
- [Writing a rule](../docs/guides/writing-a-rule.md) — make a choice depend on the data

These go to a **different repository**:
[comeni-registry](https://github.com/comeni-project/comeni-registry). Open your pull request
there; you never need to touch this one.

**Changing the code** happens here. Read [ARCHITECTURE.md](../ARCHITECTURE.md) first.

If a change needs both, it is two pull requests — the registry one first.

## Setup

Already cloned without `--recurse-submodules`? `git submodule update --init`. `make check`
refuses in one sentence if you forget, rather than failing thirty-three times about missing
contracts.

```bash
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs
cd Comeni-Labs
uv sync
make check     # ruff, pytest, and the generated-stub freshness check
```

`make check` is exactly what CI runs on a pull request; it takes about a minute and needs
no Docker. The `stub` gate does need Docker and Nextflow:

```bash
make stub      # ~1 min warm, ~15 min on a cold container cache
```

## The invariants

Fifteen properties are listed in [`CLAUDE.md`](../CLAUDE.md), and three are enforced by tests
that will fail your PR:

| Guard | Says |
|---|---|
| `tests/test_purity.py` | `comeni-core`, `mendel-resolver` and `mendel-compiler` import no web framework, HTTP client or LLM library |
| `tests/test_egress.py` | data leaves through four declared doors, each carrying one typed payload |
| `tests/test_construction.py` | a `DataProfile` is built in exactly one place, and that place validates it |

If a change to a pure package seems to need a banned import, the design is wrong rather
than the guard. Say so in the PR and we will work out the seam together.

## How we work

**Test first.** Write the failing test, watch it fail, then make it pass. Every task in
every plan in `docs/notes/plans/` is shaped that way, and the tests are the
specification.

**Watch your guard fail.** If you add a test that asserts something *cannot* happen, break
the thing on purpose, confirm the message names the right file and line, then restore it.
Three of three earlier guards in this repository had holes; all three were found this way,
and one of them was found by the plan step that required doing it.

**Determinism is a test.** The same goal must produce byte-identical output. Anything that
serialises a `frozenset` needs a `field_serializer` that sorts — `frozenset` iterates in
hash order, and hash order varies with `PYTHONHASHSEED`.

**Read the module, not the plan.** Process names and container URIs come from
`registry/tools/**/module/main.nf`. It is `SUBREAD_FEATURECOUNTS`, not `FEATURECOUNTS`, and
nf-core 4.x mostly uses `community.wave.seqera.io`. `tests/test_spine_contracts.py` checks
contracts against the modules on disk so a guess fails in milliseconds rather than at
pipeline launch.

**Read generated files before committing them.** A golden file committed unread once put
two include statements on one line. A generated stub committed unread was a syntax error
that looked fine.

## Style

- `ruff` with a 100-character line length. `make fmt` before you push.
- Comments explain *why*, especially why an obvious alternative was rejected. This codebase
  is unusually heavy on that, on purpose: most of the non-obvious code is non-obvious
  because something subtle broke, and the comment is the record.
- Match the density and idiom of the surrounding code.

## Commits and pull requests

Conventional-commit prefixes: `feat(scope):`, `fix:`, `docs:`, `test:`, `chore:`.

Write the body for someone reading `git log` in a year. What broke, what you tried, why
this and not the obvious alternative.

The PR template asks two questions, and they are the ones that matter:

1. **Which tier does this exit at?** If your change makes a choice, say which tier carries
   it and why that is honest.
2. **Did you watch your guard fail?** If you added one.

## What gets rejected

- A network call in a pure package. There is no version of this that is fine.
- A field that widens the egress boundary without editing `tests/test_egress.py`. Editing
  that file is allowed and is the point — it is a file that says *these are all the ways
  data leaves*, so changing it should feel like something.
- A rule that cannot fire. It will not load, so this is caught for you.
- A vector store, an embedding index, or any fuzzy recall layer that could influence
  resolution. Institutional memory here is the declared registry data and
  decision records — versioned, approved, diffable and citable. A fuzzy layer beside them
  could change a pipeline without passing review.
- `nf-core` module edits. Those belong upstream; `tools/**/module/` in the registry is a verbatim copy, replaced wholesale by `comeni-vendor add`, and `comeni-vendor check` fails CI on a hand-edit.

## Reporting a security or privacy issue

See [`SECURITY.md`](SECURITY.md). A hole in the egress boundary or a way to get patient
data into a `Goal` is a security issue, not a bug report.

## Adding a diagnostic code

A code is declared in exactly one place and emitted through exactly one function, and both
directions are tested — so the two cannot drift.

1. **Declare it** in `packages/comeni-core/src/comeni_core/diagnostics.yml`, in the band for its
   concern, with `emitted_by` naming the package that will raise it. `says` is one line; `fix` is
   what to write instead; `explanation` is the long form `mendel explain` prints.
2. **Emit it** through `coded()`:

   ```python
   from comeni_core.diagnostics import coded

   raise ValueError(coded("MD0002", f"{path} is not a valid contract"))
   ```

   Never write the code into the string yourself. `coded()` checks it against the registry, so a
   typo raises here rather than printing to a user and then failing `mendel explain`.
3. **Run `make docs`.** `docs/reference/diagnostics.md` is generated in full; CI fails if it is
   stale, and hand-editing it is refused.
4. **Do not declare a code you are not going to raise.** A test fails on it. A code that cannot
   happen still appears in the generated page and still answers `mendel explain`, which makes it
   documentation of a refusal that does not exist. Reserving a *band* is fine — that is a comment
   in `diagnostics.yml`, not an entry.

**A code is never renumbered once published**, because a laboratory runbook can cite it. That is
also why adding one is a *feature* rather than a fix — see [`releasing.md`](../docs/guides/releasing.md).

## Releasing

Every package versions independently and is tagged on its own — `comeni-core-v0.2.0`. Which
number to move is a judgement, and [`releasing.md`](../docs/guides/releasing.md) is the rule this project
holds itself to: `0.0.x` for a fix, `0.x.0` for a feature, `x.0.0` for a break.

Your pull request is where a version bump gets reviewed. Nothing mechanical can tell a fix from
a feature.

## Licensing

Code is Apache-2.0 ([`LICENSE`](../LICENSE)). Registry data is CC-BY-4.0 and lives in
[`comeni-registry`](https://github.com/comeni-project/comeni-registry), which carries its own
`LICENSE` — contracts cite papers and attribution matters. Vendored `nf-core` modules keep their
own licence. By contributing you agree your work is released under whichever applies.

## Conduct

Be civil, argue with the work rather than the person, and assume the other reader is trying to
get something right. Report anything that goes beyond that through
[`SECURITY.md`](SECURITY.md)'s private channel.

There is no separate code of conduct. There was a 119-line one until 2026-08-16, adopted as
boilerplate rather than written, and it committed this project to an enforcement process nobody
here had agreed to run. Two sentences somebody means beat a document nobody read.
