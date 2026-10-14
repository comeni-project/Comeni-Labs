# Your lab's own tools

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

Every declaration needs a `declares:` field. Existing layer files can keep their
locations when this field is added; `MD0010` identifies a file that lacks it.

```bash
uv run mendel build --goal my-goal.yml \
  --registry registry/ \
  --registry ./lab-registry \
  --out build/
```

`--registry` is repeatable and **later layers win**. Give none and the base layer is used
alone.

## Starting a layer

```bash
mkdir -p lab-registry
printf 'name: my-lab\nversion: "0.1.0"\n' > lab-registry/registry.yml
```

Add declaration files in the layout your lab will maintain, each carrying its
`declares:` field. No per-kind subdirectory is required by the loader.

Add only what you are changing. A layer that ships two contracts and nothing else is
completely normal, and is the case this is built around.

## Documenting a layer

```bash
uv run mendel docs --registry ./lab-registry --out lab-registry/docs/tools
```

One page per tool, from your own files. A private overlay usually cannot load on its own — it
names types the base layer declares — so stack the base underneath it:

```bash
uv run mendel docs --registry registry/ --registry ./lab-registry --out docs/reference/tools
```

`--check` writes nothing and exits 1 if a page has gone stale, which is what the public
registry runs in CI.

## Keeping it private

A layer is a directory. Keep it in a private git repository, mount it in your cluster, or
hold it on a share — Mendel only needs a path. Publishing upstream is a separate, deliberate
act, and a laboratory that never publishes anything is the expected case rather than a
degraded one.

For the design and constraints, see [Registry layers and replacement](../../explanation/registry-layers.md).
