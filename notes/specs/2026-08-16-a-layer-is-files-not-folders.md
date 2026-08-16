# A layer is files, not folders

**Written 2026-08-16 against the tree at `af0b60a`.**
[comeni-registry#1](https://github.com/comeni-project/comeni-registry/issues/1): *"contracts,
rules and vocabs are split… it's not human readable at all, I need to navigate back and forth for
one module."*

The complaint is exact. To work on STAR today you open three trees:

```
registry/contracts/nf-core/star-align.yml
registry/vocabularies/genome.index.star.yml
registry/rules/rnaseq.yml
```

## 1. Why the split exists, and why it does not have to

**The directory is currently how the loader knows what a file *is*.** `stack()` takes a `Kind`
and scans `layer.path / kind.which.value`, so `contracts/` means "these parse as contracts". Two
kinds go further and take their **identity** from the filename: `_parse_type` reads `type_id`
from `path.name`, and `_parse_measurement` does the same. Contracts already carry `id:` in
content, and rules are keyed on the decision's *target* rather than the file — so three of five
kinds are already path-independent and nobody noticed.

Nothing about resolution needs the layout. The loader needs to know a file's **kind** and its
**identity**; both can live in the file, and for most kinds already do.

## 2. The change: kind and identity move into the file

Every declared file gains a `kind:`:

```yaml
kind: contract
id: nf-core/star/align@1.11.0
```

```yaml
kind: vocabulary
id: genome.index.star
states: []
```

`stack()` stops scanning a per-kind directory and instead globs the whole layer once, parses each
file far enough to read its `kind:`, and buckets. The existing load order — measurements →
vocabulary → roles → contracts → rules — is unchanged, because it is a fact about how kinds
depend on each other, not about where they sit.

**Directory structure then carries no meaning at all.** A lab can arrange a layer per module, per
assay, per tool, or in one flat folder, and the loader will not notice.

**Two kinds gain an explicit `id:`** — vocabularies and measurements — because their identity
came from the filename. That is the migration's real content.

## 3. The convention, documented and not enforced

Mechanism allows anything; the project still ships an opinion, because a registry with no
convention is a registry where every contributor invents one.

> **A file lives with the narrowest thing it is about.**

```
registry/
  registry.yml                       the layer's account of itself
  roles.yml                          the jobs a contract can do — one closed vocabulary
  measurements/
    read_length.yml                  facts about data, true regardless of tool
  types/
    fastq.reads.yml                  types many tools touch
    alignment.bam.yml
  tools/
    nf-core/star/
      align.contract.yml             everything STAR, in one place
      genomegenerate.contract.yml
      genome.index.star.type.yml     only STAR's own modules use it
  rules/
    alignment.rule.yml               decides between tools, so it belongs to neither
```

**`tools/`, not `modules/`.** `genome.index.star` is produced by `star/genomegenerate` and
consumed by `star/align`; grouping per *module* would split it again, which is the problem being
fixed. Measured, not assumed — five types are touched by four or more contracts, and the two
index types by exactly the two modules of their own tool.

**`rules/` stays separate.** A rule that picks STAR over HISAT2 is about neither, and filing it
under `star/` would be a lie about what it decides. This registry's whole claim is that a
decision states its own reason; the layout should not contradict it.

**The `.contract.yml` / `.type.yml` / `.rule.yml` suffix is for humans.** The loader reads
`kind:` and ignores the name. A lab that dislikes the suffix drops it and nothing breaks.

**Not enforced by a test.** A convention the loader cannot see is a convention, and testing it
would make it a rule while claiming it is not. What *is* tested is that every file declares a
kind it can be loaded as.

## 4. Invariant 11 changes, and this is the part to read twice

It currently opens:

> A layer is a **directory** holding one subdirectory per `DeclaredKind` — `contracts/`,
> `rules/`, `vocabularies/`, `measurements/` and `roles/`.

It becomes: **a layer is a directory of declared files, each of which says what it is.** What the
invariant is actually about survives untouched — one stacking mechanism, `Kind` parameterising
how a file parses, keys and merges; module-key displacement; `Layer.index` as identity;
`states:`/`add_states:`. None of that is about folders.

**What genuinely weakens:** `_every_file_is_claimed` (`MD0003`) refused a `.yml` outside a kind
directory, which caught a misspelled `contract/` and a file dropped at the layer root. That check
becomes *"every declared file names a kind that exists"* — narrower in one way, since a file can
now sit anywhere, and wider in another, since it now inspects content rather than location. A
typo'd `kind: contrat` is caught where a typo'd directory used to be.

## 5. New refusals

| code | says |
|---|---|
| `MD0010` | a declared file does not say what kind it is |
| `MD0011` | a declared file names a kind that does not exist |
| `MD0012` | a vocabulary or measurement does not declare its `id` |

All three are new failure modes created by this change, and all three are the *same* failure the
directory used to prevent by construction. Declaring them is the cost of the flexibility.

## 6. The digest, and why the timing matters

`declared_entries()` — the layer digest's allowlist, written yesterday — enumerates
`DeclaredKind` directories. It becomes every `.yml`/`.yaml` under the layer plus `registry.yml`,
which is what a layer now *is*.

**Every layer digest moves.** That is free today and expensive on the first day a laboratory
holds a `pipeline.yml` pinning one. `comeni-registry` has tags but nothing published references a
layer digest, which is the operator's argument for doing this now and it is correct.

## 7. How it lands across two repositories

The registry is a submodule, so this is two changes and they cannot be one:

1. **`comeni-registry`** — migrate every file, adopt the convention, tag `v0.3.0`.
2. **`Comeni-Labs`** — the loader change, the new codes, the fixtures, **and the submodule
   pointer bumped to `v0.3.0` in the same commit.**

There is no transitional dual-reader. The new loader cannot read the old layout and the old
loader cannot read the new one, and a compatibility mode would be a third thing to maintain for a
migration that happens once, in a repository nobody has forked.

## 8. What is not in scope

- **No change to what a contract, rule, vocabulary or measurement *means*.** Fields, semantics
  and validation are untouched; only where a file may sit and how it announces itself.
- **No `mendel show <module>`.** A per-module view is a good idea and a separate one — it reads
  the registry rather than restructuring it.
- **No enforcement of the convention**, per §3.
- **No re-versioning of contracts.** A contract's `@version` is about the module it binds, not
  about this move.

## 9. Success criterion

`registry/` is arranged per §3; a build from `examples/rnaseq-goal.yml` produces the same
`steps:` and the same `main.nf` as before, with only the layer digest moved; moving any file
anywhere inside the layer changes nothing; and a file with no `kind:`, an unknown `kind:`, or a
vocabulary with no `id:` each refuse with a code naming the file.
