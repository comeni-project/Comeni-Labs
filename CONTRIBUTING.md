# Contributing

Thank you for considering it. This document covers how to set up, what the project cares
about, and what a reviewable change looks like.

## Two kinds of contribution

**Registry data** — a contract, a rule, a measurement, a vocabulary state — is the most
valuable kind and needs no Python. It is a YAML file plus a citation. Start with
[`docs/guides/writing-a-contract.md`](docs/guides/writing-a-contract.md) or
[`docs/guides/writing-a-rule.md`](docs/guides/writing-a-rule.md).

**Code** changes the machinery. Read [`ARCHITECTURE.md`](ARCHITECTURE.md) first — it is
short, and it explains why several things that look wrong are deliberate.

## Setup

```bash
git clone https://github.com/comeni-project/Comeni-Labs
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

Fifteen properties are listed in [`CLAUDE.md`](CLAUDE.md), and three are enforced by tests
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
every plan in `docs/internal/plans/` is shaped that way, and the tests are the
specification.

**Watch your guard fail.** If you add a test that asserts something *cannot* happen, break
the thing on purpose, confirm the message names the right file and line, then restore it.
Three of three earlier guards in this repository had holes; all three were found this way,
and one of them was found by the plan step that required doing it.

**Determinism is a test.** The same goal must produce byte-identical output. Anything that
serialises a `frozenset` needs a `field_serializer` that sorts — `frozenset` iterates in
hash order, and hash order varies with `PYTHONHASHSEED`.

**Read the module, not the plan.** Process names and container URIs come from
`vendor/modules/**/main.nf`. It is `SUBREAD_FEATURECOUNTS`, not `FEATURECOUNTS`, and
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
  resolution. Institutional memory here is `contracts/`, `rules/`, `vocabularies/` and
  decision records — versioned, approved, diffable and citable. A fuzzy layer beside them
  could change a pipeline without passing review.
- `nf-core` module edits. Those belong upstream; `vendor/` is a copy.

## Reporting a security or privacy issue

See [`SECURITY.md`](SECURITY.md). A hole in the egress boundary or a way to get patient
data into a `Goal` is a security issue, not a bug report.

## Licensing

Code is Apache-2.0 ([`LICENSE`](LICENSE)). Registry data is CC-BY-4.0
([`LICENSE-DATA`](LICENSE-DATA)) because contracts cite papers and attribution matters.
Vendored `nf-core` modules keep their own licence. By contributing you agree your work is
released under whichever applies.

## Code of conduct

[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) applies everywhere in this project.
