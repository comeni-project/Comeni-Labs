# Root D — the verdict comes from the artifact, and the diff explains it

**Spec, 2026-08-07.** Closes A28. Root D in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `69283ba`.

---

## The problem

`diff_ir` compares `node.contract_id`, `binding.value.value`, and the selection's tier and
reason. It does **not** compare `ir.edges`, `ir.profile`, `ir.shadowed`, `ir.unverified`,
`from_layer` or `displaced_layer` — several of which the emitter reads. So `mendel upgrade`
printed *"no changes: this pipeline re-resolves identically"* while `main.nf` had demonstrably
changed, twice: once for A27's injection, once for a bundle published against two layers and
upgraded against one.

**This is root A's shape again.** `diff_ir` enumerates the fields it knows about, so every field
added to the IR is a new blind spot, silently. Plan 1.8 added four.

The serious case is edges. `resolve.py` records in its own comment that wiring `.bai` into
featureCounts was *"valid Nextflow, no flag, and `-stub-run` cannot catch it"*. `mendel upgrade`
cannot catch it either.

---

## Why the obvious fix is wrong

Reviewer 2 proposed comparing the emitted bytes against the bundle. The direction is right and
the mechanism is not: **the bundle carries no emitted artifact** — only `goal`, `ir`,
`decisions`, `lockfile`, `gate`. To get the old bytes you must re-emit the old IR, which needs
the registry as it was.

Tested:

```
$ # publish, then delete one contract from the registry, then re-emit the bundle's own IR
re-emitting the OLD ir: KeyError: 'nf-core/samtools/sort@1.21.0'
```

A contract removed from the registry is **one of the two cases `mendel upgrade` exists to
report**, and re-emitting dies on exactly it. This is not a new hazard: Plan 1.7's journal
records that `drift_against` *"crashed on the two cases it exists to report"*, for the same
reason — it tried to reconstruct the old world from the new registry. Building the upgrade
verdict on a re-emit reintroduces that bug class.

**Do not reconstruct the past. Record it.**

---

## The design

### 1. The bundle records what it emitted

```python
class EmittedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NfPath        # "main.nf", "nextflow.config"
    digest: Digest      # sha256:<64 hex>


class Emitted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[EmittedFile]   # sorted by name, so the list reads one way only
```

`PublishBundle.emitted: Emitted | None`. `mendel publish` fills it from the files it actually
wrote — the generated ones only, never the copied `modules/` tree, which is vendored rather than
emitted.

Sorted by name for Plan 1.7's rule: *a hash over concatenated fields means nothing unless each
field can be read only one way*. Every field is a marked string, so it satisfies root A's leaf
allowlist and may cross the door.

This makes the bundle **self-verifying** independently of upgrade: a recipient can check that the
pipeline they were handed is the pipeline the bundle describes. That property does not exist
today at all.

### 2. The verdict comes from the digest; the diff explains it

`mendel upgrade` re-emits with the *current* registry, digests what it wrote, and compares to
`previous.emitted`. No dependency on the old registry, so the `KeyError` case above cannot arise.

```
the generated pipeline is byte-identical to the bundle
```
or
```
the generated pipeline differs:  main.nf
  samtools_sort: nf-core/samtools/sort@1.21.0 -> lab/rival/sorter@9.9.9  (tier 2) …
```

`diff_ir` becomes the **explanation** rather than the evidence. It cannot go stale as fields are
added, because it is no longer what answers the question.

### 3. A disagreement is reported, not hidden — and this is the point

If the digest differs and `diff_ir` returns nothing, the tool says so explicitly:

```
the generated pipeline differs: main.nf
  but no IR change explains it. Either the compiler itself changed since this
  bundle was published, or the diff has a blind spot. Both are worth knowing.
```

**A guard that reports its own blind spots.** This is A14's class — a check that cannot fail is
indistinguishable from a check that passes — closed structurally here rather than by protocol.
Today a diff blind spot is silent by construction; after this it is a printed sentence.

The message names both causes deliberately, so a reader is not misled into assuming a diff bug
when a compiler change is equally likely.

### 4. `diff_ir` is extended anyway

The verdict no longer depends on it, but an explanation that omits half the pipeline is a poor
explanation. Add:

- **edges**, keyed `(to_node, to_port)`, reporting a changed source — the `.bai` case
- **tier**, so a same-value move from tier 2 to tier 4 is visible; a reviewer must see that

Not added: `profile`, `shadowed`/`displaced`, `unverified`. Those are reported by their own
mechanisms — `DRIFT` lines, root B's `OVERLAY` block — and duplicating them here would give two
places to disagree, which is the defect A22 is made of.

### 5. Drift, changes and the artifact are three separate statements

They already are, and that separation is correct and stays:

| line | answers |
|---|---|
| `DRIFT` | the registry moved underneath the lockfile |
| the verdict | **the emitted pipeline moved** |
| `diff_ir` changes | *why* it moved, per node and parameter |

Drift can be non-empty with an identical artifact (a contract edited in a way this pipeline does
not use) — that is worth knowing and is why drift was split out in Plan 1.7. The new line is the
one that was missing.

---

## Verification

Root I applies. Each probe watched failing before its guard is kept.

| probe | expected |
|---|---|
| upgrade against an unchanged registry | *byte-identical*, and `diff_ir` empty |
| bundle published against two layers, upgraded against one | **differs**, and the change is named |
| a hand-edited `reason` in the bundle (A27's case) | **differs** — today this prints "no changes" |
| an edge rewired (`samtools_sort.bam` → `samtools_index.bai` into featurecounts) | differs, and `diff_ir` names the edge |
| a same-value tier move, 2 → 4 | `diff_ir` names it |
| digest differs, `diff_ir` empty | the **unexplained** message, naming both causes |
| a contract deleted from the registry, then upgrade | reports drift and a verdict — **no `KeyError`** |
| `Emitted` on a payload | satisfies root A's allowlist |
| a bundle published before this field existed (`emitted: None`) | upgrade still runs, and says the bundle predates the check rather than claiming identity |

The last row matters: `None` must not read as "identical". An absent record is no evidence, the
same distinction `PublishBundle.gate` already makes for A4.

---

## Blast radius

- `comeni_core/egress.py` — `Emitted`, `EmittedFile`, `PublishBundle.emitted`.
- `comeni_core/digest.py` — reuse `digest_of` for the model; no new hashing.
- `mendel_compiler/cli.py` — publish fills it after the gate; upgrade compares and prints.
- `mendel_resolver/diff.py` — edges and tier.
- `tests/test_publish.py` — the exact-key-set assertion changes again, deliberately, as it did
  for `gate`.

Small, and mostly additive. The one subtlety is ordering in `publish`: emit → gate → digest →
bundle, so the recorded digest is of the files that actually passed.

---

## What this spec does not cover

- **An emitter version in the bundle**, which would let the unexplained message distinguish "the
  compiler changed" from "the diff is blind". There is no version scheme yet; the message names
  both causes instead. Worth revisiting when one exists.
- **`drift_against`'s own correctness.** It is the site of A21-shaped guard drift and is reverted
  deliberately under root B, not here.
- **Verifying a bundle against files on disk** as a user-facing verb. The data now supports it;
  whether `mendel verify <bundle> <dir>` should exist is a product question, not this fix.
