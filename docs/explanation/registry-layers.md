# Registry layers and replacement

## The intuition first

The public registry should hold broadly reusable knowledge. Your lab layer holds local
knowledge: private tools, local containers, validated defaults, and rules your lab is willing to
defend but may not want to publish.

Layering lets you keep both. The base registry can say what the community knows; your layer can
say what your lab knows. Comeni loads them together, with later layers winning when they
deliberately replace something below.

Typical reasons to create a layer:

| Need | Layer change |
|---|---|
| private module | add a contract |
| newer pinned module version | shadow the lower contract |
| lab default differs from public default | add or replace a rule |
| local organism or assay vocabulary | extend an extensible measurement |

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
1 overlay reroute(s) — an installed layer changed what the layers below it would do:
  OVERLAY  contracts: nf-core/samtools/sort@1.22.0 from my-lab over
           nf-core/samtools/sort@1.21.0, displacing comeni-registry-examples
```

The layer is named by its `registry.yml`, not by its path — which is why `my-lab` appears
there rather than `./lab-registry`.

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
# base: measurements/organism.yml
declares: measurement
id: organism
kind: enum
extensible: true
values: [homo_sapiens, mus_musculus]
```

```yaml
# lab-registry/measurements/organism.yml
declares: measurement
id: organism
add_values: [ambystoma_mexicanum]
```

Without `extensible: true` this is refused, and the error tells you to shadow the whole
declaration instead. The distinction is real: `strandedness` has exactly three values and
a fourth is a bug, while `organism` can never be enumerated and a registry that pretends
otherwise is wrong.

## Load order is not optional

The kinds are not independent:

```
measurements ──▶ vocabularies ──▶ contracts ──▶ rules
```

A measurement derives a `measurement.<id>` type; contracts validate against the vocabulary
including those; rules validate against all three. Load them in the wrong order and the
failure appears inside some contract rather than where the mistake is.

If you are writing code against this, use the one function:

```python
from mendel_resolver import layers

loaded = layers.load(["registry", "./lab-registry"])
loaded.registry, loaded.rules, loaded.vocabulary, loaded.measurements
```

For instructions, see [Add a lab layer](../how-to/registry/add-layer.md).
