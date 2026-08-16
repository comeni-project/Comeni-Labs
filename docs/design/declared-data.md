# Why declared data is files, and not a database

**Decided 2026-08-16, closing [issue #43](https://github.com/comeni-project/Comeni-Labs/issues/43).**
The question was whether to keep data spread across YAML files or collect it into one SQL
database that auto-generates a human-readable table. The answer is files — and the reason to
write it down is that the question is reasonable, recurs, and had never been answered.

## What data exists

Two stores, and it is worth being exact because the answer differs by kind:

| | Where | What |
|---|---|---|
| **Registry data** | `registry/` — a git submodule of [`comeni-registry`](https://github.com/comeni-project/comeni-registry), a directory of files that each declare their own `DeclaredKind` | contracts, rules, vocabularies, measurements, roles — human-authored, cited, reviewed, stacked |
| **Diagnostics** | `packages/comeni-core/src/comeni_core/diagnostics.yml` | every code, its `says`, its long-form explanation |

Everything else that *looks* like a table in this repository is not data. `_OPS`, `_REDUCERS`,
`DOORS`, `_TIMEOUTS`, `_REVIEW_BY_TIER` map names to **functions and types**. A database cannot
hold a function, and a table of them would be a table of strings that something has to look up in
a dictionary anyway. They are code that happens to be written as a literal.

## What the field does

The registry's data class is *curated, human-reviewed, cited, community-contributed catalogue
data*. Every comparable system stores it as files in git:

| System | Scale | Source of truth |
|---|---|---|
| nixpkgs | 100k+ packages | Nix expressions in git |
| Homebrew | ~7k formulae | Ruby files in git |
| conda-forge / Bioconda | ~20k recipes | `meta.yaml` in git |
| nf-core modules | ~1.5k | `main.nf` + `meta.yml` in git |
| OPA policies, Terraform providers, ESLint rules | large | files in git |

Not one uses a database as its source, and the reason is not conservatism: **a database has no
diff, no blame, no review, no signature and no merge.** For data whose entire value is that a
human approved it and a paper backs it, those five properties *are* the product. They are also
exactly what `docs/design/federation.md` sells — signed tags over a git layer — and what
invariant 2 requires, since a contract is approved *into a directory*.

For diagnostics the closest analogues are compilers, and both converge on the same shape:

- **TypeScript** keeps one `diagnosticMessages.json` and generates its code map and docs from it.
- **Rust** declares error codes in source and generates the error index.

One declarative file, generated consumers. That is what `diagnostics.yml` plus
`tools/generate_diagnostics_doc.py` already is, and `docs/reference/diagnostics.md` is the
generated table the issue asked for. **It was already built** — issue #43 was filed before it
had a page of its own, which is part of why the question looked open.

## The honest counterexample

**crates.io moved its index off git.** It was a git repository of JSON; at roughly 100k crates,
cloning became the bottleneck, and the sparse HTTP registry protocol replaced it around 2023.

It does not transfer. crates.io is *machine-published* — an API accepts an upload and writes the
index — so there is no review step to lose. Mendel's registry is human-curated, which is the
property that keeps every system in the table above on files. The systems that moved to a
database are the ones that never had a human in the loop.

## Where a database would be legitimate

**As a derived index, never as a source.** nixpkgs has `nix-index`; conda has `repodata.json`.
If a registry ever grows large enough that `Registry.load()` globbing `*.yml` is measurably slow,
the answer is a generated index that is built from the files, is never committed, and is deleted
without loss.

That is not today. The registry is 37 files and load time is milliseconds. Building an index now
would be optimising a cost nobody has measured, and it would have to be maintained through every
change to `stack()`.

**The rule, so a future reader does not have to re-derive it:** the source of truth is the thing a
human edits and a reviewer reads. Anything else is derived, and derived things are generated,
gitignored and disposable.

## What this does not settle

**`MD0000`–`MD0099` is reserved for "loading declared registry data" and is empty.** A malformed
contract surfaces as a raw Pydantic error rather than a coded diagnostic today. That is a real
hole in the error surface and it is the substantive thing issue #43 was pointing at — the
complaint that the data layer's failures are less legible than the rest of the system's. It is
filed separately rather than folded in here, because it is work rather than a decision.

## See also

- [`federation.md`](federation.md) — registry distribution, signed tags, the visibility tiers
- [`../reference/diagnostics.md`](../reference/diagnostics.md) — the generated table
- `CLAUDE.md` — invariant 2 (approval into a directory), invariant 11 (a layer is a directory)
