# Registry layers

Your laboratory has tools nobody else has, conventions nobody else shares, and rules that
came out of your own validation work. A layer is how you ship those without forking
anything.

## What a layer is

A directory holding up to four subdirectories:

```
lab-registry/
├─ contracts/       your modules
├─ rules/           your tier-3 decisions
├─ vocabularies/    your types and their states
└─ measurements/    your declared measurements
```

All four stack. Any may be absent — a layer with only `contracts/` inherits everything
else from below.

```bash
uv run mendel build --goal my-goal.yml \
  --registry registry/ \
  --registry ./lab-registry \
  --out build/
```

`--registry` is repeatable and **later layers win**. Give none and the base layer is used
alone.

## What stacking means, per kind

| Kind | Keyed on | Higher layer does |
|---|---|---|
| vocabularies | type id | replaces the type's whole state set |
| measurements | measurement id | replaces the declaration (or extends it — below) |
| contracts | **module key** — the id minus `@version` | shadows every lower-layer contract for that module, and records it |
| rules | decision target | replaces the whole decision block |

### Contracts shadow on the module key

`nf-core/samtools/sort@1.22.0` in your layer displaces `nf-core/samtools/sort@1.21.0` in
the base, because they share the module key `nf-core/samtools/sort`. A **version bump is
not an ambiguity**, and keying on the full id would make the two tie and demand human
review for something that is not a question.

A *different* module key is an ordinary candidate and competes normally.

Shadowing is announced on every build:

```
  SHADOW  nf-core/samtools/sort: nf-core/samtools/sort@1.22.0 from ./lab-registry
          displaced nf-core/samtools/sort@1.21.0
```

Never silent. An installed overlay that quietly rerouted a pipeline would break the
guarantee the tool is for.

### Rules replace whole blocks

If both layers decide `param:strandedness`, yours replaces the entire block — not row by
row. A reviewer should read one block and see the complete effective decision, rather than
mentally merging two files.

Deciding the same target twice *within* one layer is an error. That is a copy-paste
mistake, and resolving it by file order would be the silent arbitrary pick this design
exists to prevent.

### Measurements can extend rather than replace

An enum declared `extensible: true` accepts additions:

```yaml
# base: organism.yml
kind: enum
extensible: true
values: [homo_sapiens, mus_musculus]
```

```yaml
# lab-registry/measurements/organism.yml
add_values: [ambystoma_mexicanum]
```

Without `extensible: true` this is refused, and the error tells you to shadow the whole
declaration instead. The distinction is real: `strandedness` has exactly three values and
a fourth is a bug, while `organism` can never be enumerated and a registry that pretends
otherwise is wrong.

## Load order is not optional

The four kinds are not independent:

```
measurements ──▶ vocabularies ──▶ contracts ──▶ rules
```

A measurement derives a `measurement.<id>` type; contracts validate against the vocabulary
including those; rules validate against all three. Load them in the wrong order and the
failure appears inside some contract rather than where the mistake is.

If you are writing code against this, use the one function:

```python
from mendel_resolver import layers

loaded = layers.load(["examples", "./lab-registry"])
loaded.registry, loaded.rules, loaded.vocabulary, loaded.measurements
```

## Starting a layer

```bash
mkdir -p lab-registry/{contracts,rules,vocabularies,measurements}
```

Add only what you are changing. A layer that ships two contracts and nothing else is
completely normal, and is the case this is built around.

## Keeping it private

A layer is a directory. Keep it in a private git repository, mount it in your cluster, or
hold it on a share — Mendel only needs a path. Publishing upstream is a separate, deliberate
act, and a laboratory that never publishes anything is the expected case rather than a
degraded one.
