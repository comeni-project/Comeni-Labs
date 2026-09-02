# Registry layers

Your laboratory has tools nobody else has, conventions nobody else shares, and rules that
came out of your own validation work. A layer is how you ship those without forking
anything.

## What a layer is

**A directory of files, each of which says what it is.** Every file carries a `declares:`
line, and a vocabulary or a measurement carries an `id:` beside it:

```yaml
declares: contract
id: mylab/sortmerna@4.3.6
```

**Where you put the file is up to you.** The loader reads the `declares:` line, never the
path, so you can arrange a layer for whoever has to read it. The public registry groups a
tool's files together, and copying that is a good default:

```
lab-registry/
├─ registry.yml                      the layer's name and version
├─ measurements/                     your declared measurements
├─ types/                            your types and their states
├─ rules/<name>.rule.yml             your tier-3 decisions
└─ tools/mylab/sortmerna/            one tool, its contract and any type only it produces
   └─ sortmerna.contract.yml
```

Every kind stacks. Any may be absent — a layer holding one contract inherits everything
else from below.

This changed with comeni-registry#1. A layer used to be one directory *per kind*, because
the directory was how the loader knew what a file was — so working on one tool meant
navigating three trees. If you have an older layer, add `declares:` to each file and it
will load wherever it already sits; `MD0010` names any file you miss.

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

## Starting a layer

```bash
mkdir -p lab-registry
printf 'name: my-lab\nversion: "0.1.0"\n' > lab-registry/registry.yml
```

Then add files wherever you want them, each carrying its `declares:` line. There are no
directories to create first — that is the point of comeni-registry#1.

Add only what you are changing. A layer that ships two contracts and nothing else is
completely normal, and is the case this is built around.

## Documenting a layer

```bash
uv run mendel docs --registry ./lab-registry --out lab-registry/docs/tools
```

One page per tool, from your own files. A private overlay usually cannot load on its own — it
names types the base layer declares — so stack the base underneath it:

```bash
uv run mendel docs --registry registry/ --registry ./lab-registry --out docs/tools
```

`--check` writes nothing and exits 1 if a page has gone stale, which is what the public
registry runs in CI.

## Keeping it private

A layer is a directory. Keep it in a private git repository, mount it in your cluster, or
hold it on a share — Mendel only needs a path. Publishing upstream is a separate, deliberate
act, and a laboratory that never publishes anything is the expected case rather than a
degraded one.
