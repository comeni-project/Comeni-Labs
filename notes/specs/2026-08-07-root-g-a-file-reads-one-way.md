# Root G — a file can be read only one way

**Spec, 2026-08-07.** Closes A31, and the half of A26 that root B does not take. Root G in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `7f918b1`.

---

## The problem

Plan 1.7 landed this rule, three times over, at some cost:

> **A hash over concatenated fields means nothing unless each field can be read only one way.**

It was applied to digests and stopped there. **A file has the same property, and nothing checks
it.** `yaml.safe_load` silently keeps the last of duplicated mapping keys. `extra="forbid"`
(A10) cannot see it, because the duplicate is collapsed before Pydantic is reached — and the
digest then pins the *parsed model*, so the digest is perfectly consistent with what runs and
warns nobody that the file has two readings.

```
$ sed -n '10p' dupkey/contracts/nf-core/hisat2-align.yml
priority: 0
$ tail -1 dupkey/contracts/nf-core/hisat2-align.yml
priority: 999
$ … registry.get('nf-core/hisat2/align@2.2.2').priority
loaded priority = 999
```

**Where this bites is not the parser, it is the review.** Federation's curated tier is *a named
human signs off*, and a human signs off on a diff hunk. A second `priority:` two hundred lines
below the first is outside the hunk and inside the build.

There are **7** `yaml.safe_load` call sites, none strict:

```
comeni_core/vocabulary.py      comeni_core/contract.py       comeni_core/measurement.py
comeni_core/layer.py           mendel_resolver/rules.py      mendel_compiler/modulespec.py
mendel_compiler/cli.py         (the goal file)
```

Note the last: **a goal file** is read the same loose way, and `mendel upgrade` reads a goal a
stranger wrote.

---

## The design

### 1. One strict loader, used everywhere

```python
# comeni_core/yaml_strict.py

class _StrictLoader(yaml.SafeLoader):
    """`SafeLoader`, except a repeated mapping key is an error rather than a silent
    last-wins. Audit A31."""

def load(text: str, *, where: Path) -> object:
    """Parse declared data. Raises naming the file, the key and both line numbers."""
```

All 7 call sites move to it. The error must name **the file, the key and both line numbers** —
a duplicate is a thing a person has to go and look at, and "duplicate key" without a location is
a worse experience than the silence it replaces.

`modulespec.py` reads vendored nf-core `meta.yml` — files this project does not author. Strict
loading may reject a third-party file that has always "worked". **That is worth knowing and is
not a reason to exempt it:** a `meta.yml` with two readings is a conformance check against a file
whose contents are ambiguous. If a real vendored module trips it, that is a finding about the
module, and the sweep in verification will say so.

### 2. Anchors and aliases: measured, then decided

Reviewer 2 recorded YAML anchors and billion-laughs expansion as an **untested hypothesis**, and
it stays one until someone runs it. This spec's task list includes *measuring* it — construct an
alias-bearing contract and an expansion bomb, see what the loaders do — and only then deciding
whether `_StrictLoader` also refuses anchors.

Refusing them outright is tempting and probably right (declared data has no need to alias), but
**recording an untested hypothesis as a fix is the thing this whole exercise is against.**

### 3. Unclaimed files belong to root B

The other half of A26 — a `.yaml` file no loader reads, a vocabulary nested one directory deep —
is file *discovery*, which is root B's `stack()`. It is named here only so the boundary is
explicit: **G says a file that is read is read one way; B says every file in a layer is read.**

---

## Verification

Root I applies.

| probe | expected |
|---|---|
| a contract with a repeated `priority:` | **refused**, naming file, key and both lines |
| a repeated key in a vocabulary, measurement, rule, `registry.yml`, goal | refused, each |
| every file in the shipped `registry/` | **loads unchanged** |
| every vendored `meta.yml` under `vendor/modules/` | loads — or a finding, recorded rather than exempted |
| a YAML anchor in a contract | *measured first*, then specified |
| an expansion bomb | *measured first* |
| `make verify` | green, including the counts matrix |

The third and fourth rows are the ones that decide whether this ships as written: a strict loader
that rejects the project's own data is a strict loader nobody keeps.

---

## Blast radius

Small and wide: one new module, 7 import sites, no behaviour change for well-formed files.
The risk is concentrated entirely in the two "loads unchanged" rows above.

---

## What this spec does not cover

- **File discovery** — root B.
- **Whether a duplicate key should be a warning rather than an error.** It should not: A10 already
  made this argument for `extra="forbid"` one level up — *a key that is ignored is a key that can
  be misspelled in silence, and a key that is overridden is worse, because it can be misspelled
  deliberately.*
