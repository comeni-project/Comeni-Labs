# A layer is files, not folders — implementation plan

> **REQUIRED SUB-SKILL:** `superpowers:executing-plans`. Task by task, in a worktree.

**Goal:** a declared file says what it is, so a layer can be arranged for a human to read.

**Architecture:** Five tasks, ordered so **every one ends green in both repositories**. The
trick is to separate *announcing* a kind from *depending* on it: files gain `kind:` and `id:`
while the directories still exist and the old loader still works (Tasks 1–2); only then does the
loader switch to reading content (Task 3); only then do the files move (Task 4). No step needs a
dual-reader, because no step has the loader and the layout disagreeing.

**Spec:** [`notes/specs/2026-08-16-a-layer-is-files-not-folders.md`](../specs/2026-08-16-a-layer-is-files-not-folders.md)

## Global Constraints

- **Two repositories.** `comeni-registry` holds the data; `Comeni-Labs` pins it as a submodule.
  A registry change lands, gets tagged, and the engine PR bumps the pointer.
- **`steps:` and `main.nf` must not move.** Only the layer digest may. Recorded before Task 1 and
  checked at every task, as issue #46 taught.
- **`kind:` is optional until Task 3 and required after.** That is what keeps Task 2 green.
- **Every guard watched failing**, with a ledger row.
- **New codes `MD0010`–`MD0012`**, declared *and emitted* in the same task — a declared code that
  nothing raises now fails a test.

---

## Task 1: the models accept `kind:` and `id:`

**Files:** `comeni_core/declared/{contract,vocabulary,measurement,roles}.py`,
`mendel_resolver/rules/format.py`

- [ ] **Step 1: Record the canary**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/L0 --gate lint
sha256sum /tmp/L0/main.nf /tmp/L0/pipeline.yml
```

- [ ] **Step 2: Write the failing tests**

One per kind: a file carrying `kind:` and (for vocabulary and measurement) `id:` loads, and the
declared id wins over the filename.

```python
def test_a_vocabulary_may_declare_its_own_id(tmp_path):
    """Until now the type id came from the filename, so a type could not be moved or renamed
    without being renamed. An explicit `id:` is what makes the file portable."""
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "anything.yml").write_text(
        "kind: vocabulary\nid: genome.index.star\nstates: []\n"
    )
    loaded = layers.load(layer)
    assert "genome.index.star" in loaded.vocabulary.types


def test_the_filename_still_works_when_no_id_is_declared(tmp_path):
    """Task 3 makes `id:` required. Until then both work, which is what keeps the registry
    green while it is being migrated one file at a time."""
```

- [ ] **Step 3: Accept both**

`_parse_type` and `_parse_measurement` take `id` from the document when present and fall back to
the filename. Every declared model gains an optional `kind:` field that it **ignores** — accepted
so a migrated file loads, unused until Task 3.

**`extra="forbid"` is why this step exists at all**: without it, adding `kind:` to a registry file
would fail to load, and the migration could not be done incrementally.

- [ ] **Step 4: Run, watch pass, watch fail**

Remove the `id` fallback → the filename tests fail. Remove the `id` lookup → the new tests fail.

- [ ] **Step 5: `make verify`, canary, commit**

---

## Task 2: the registry declares what its files are

**Repository:** `comeni-registry`. **Directories do not move in this task.**

- [ ] **Step 1: Add `kind:` to all 36 files, and `id:` to the 22 that need one**

Twelve contracts get `kind: contract`; ten vocabularies get `kind: vocabulary` and
`id: <filename>`; twelve measurements get `kind: measurement` and `id: <filename>`; `roles.yml`
gets `kind: role`; `rules/rnaseq.yml` gets `kind: rule`.

Scripted, then **read the diff** — the same instruction that caught three corruptions in the
`coded()` conversion, and for the same reason.

- [ ] **Step 2: Check it against the engine before tagging**

From the `Comeni-Labs` worktree, with the submodule pointed at the migration branch:

```bash
git -C registry checkout <branch>
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/L2 --gate lint
diff /tmp/L0/main.nf /tmp/L2/main.nf     # must be empty
```

The layer digest **will** move — the files changed. `main.nf` must not.

- [ ] **Step 3: Tag `v0.3.0` and push**

A feature by `docs/guides/releasing.md`'s rule: new fields consumers can rely on.

- [ ] **Step 4: Bump the pointer, `make verify`, commit**

---

## Task 3: the loader reads the file, not the folder

**Files:** `comeni_core/declared/layered.py` (`stack`, `DeclaredKind`, `declared_entries`),
`mendel_resolver/layers.py`, `comeni_core/diagnostics.yml`, ~29 test files

- [ ] **Step 1: Write the failing tests**

```python
def test_a_layer_may_be_arranged_any_way_at_all(tmp_path):
    """The point of the whole change: one flat folder, and it loads."""
    layer = tmp_path / "flat"
    layer.mkdir()
    (layer / "registry.yml").write_text("name: flat\n")
    (layer / "anything.yml").write_text(CONTRACT)          # kind: contract inside
    (layer / "whatever.yml").write_text(TYPE)              # kind: vocabulary inside
    assert layers.load(layer).registry.contracts


def test_moving_a_file_changes_nothing(tmp_path):
    """Two layers with identical files in different folders load identically — and, since the
    digest covers names, they digest *differently*. Both are intended: the layout is free, and
    a layer's digest still pins exactly which bytes were at which path."""


def test_MD0010_a_declared_file_must_say_what_it_is(tmp_path): ...
def test_MD0011_a_declared_file_must_name_a_kind_that_exists(tmp_path): ...
def test_MD0012_a_vocabulary_must_declare_its_id(tmp_path): ...
```

- [ ] **Step 2: Declare `MD0010`–`MD0012`, and emit them through `coded()`**

Both directions are tested now, so declaring without emitting fails.

- [ ] **Step 3: `stack()` buckets by declared kind**

It stops taking `layer.path / kind.which.value` and instead reads every `.yml`/`.yaml` under the
layer once, groups by the `kind:` each declares, and hands each `Kind` its own bucket. The load
*order* in `layers.load()` is unchanged — it is about how kinds depend on each other.

`declared_entries()` becomes every declared file plus `registry.yml`.

- [ ] **Step 4: `_every_file_is_claimed` becomes "every file names a known kind"**

Its docstring must record what weakened: it caught a misspelled `contract/` directory by
construction, and now catches a misspelled `kind:` by inspection. Spec §4.

- [ ] **Step 5: Fixtures**

Every fixture that writes a declared file needs `kind:`, and vocabulary/measurement fixtures need
`id:`. **Directory structure in fixtures can stay** — it stops meaning anything but breaks
nothing, so 174 path references do not have to move.

- [ ] **Step 6: Run, watch pass, watch each new code fail, ledger**

- [ ] **Step 7: `make verify`, canary — `main.nf` unchanged, digest moved**

---

## Task 4: the registry adopts the convention

**Repository:** `comeni-registry`. **Now the files move.**

- [ ] **Step 1: Rearrange per the spec's §3 tree**

`git mv` only — no content changes in this task, so the diff is a pure rename and reviewable as
one.

- [ ] **Step 2: Prove the move changed nothing but the digest**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/L4 --gate lint
diff /tmp/L0/main.nf /tmp/L4/main.nf                      # empty
diff <(grep -v 'digest:' /tmp/L0/pipeline.yml) <(grep -v 'digest:' /tmp/L4/pipeline.yml)
```

- [ ] **Step 3: The registry's own README documents the convention**

It is the first thing a contributor to that repository reads, and the convention is not enforced
by anything — so if it is not written there, it does not exist.

- [ ] **Step 4: Tag `v0.4.0`, bump the pointer, `make verify`**

---

## Task 5: the documents

- [ ] **Step 1: Invariant 11 in `CLAUDE.md`** — rewritten per spec §4, keeping everything it is
  actually about and recording what weakened.
- [ ] **Step 2: `ARCHITECTURE.md`** — the declared-data section and the load order.
- [ ] **Step 3: `docs/reference/*-schema.md`** — `kind:` and `id:` on each, and a line saying the
  layout is free.
- [ ] **Step 4: `docs/guides/registry-layers.md`** — the convention, with the tree.
- [ ] **Step 5: `contributing.md`** — where to put a new file.
- [ ] **Step 6: Journal, final gate, one PR each side.**

## Self-review

- **Every task ends green in both repositories**, which is the whole reason for five tasks
  rather than two. Tasks 1–2 are additive; Task 3 flips the loader when every file already
  announces itself; Task 4 moves files when nothing reads their path.
- **The canary is recorded before Task 1** and checked at 2, 3 and 4 — because "only the digest
  moves" is precisely the claim issue #46 made and got wrong.
- **One thing the spec left open, decided here:** two identical layers in different folders
  digest *differently*, because the digest hashes names. That is correct — a layer's digest pins
  which bytes were at which path — and Task 3 Step 1 asserts it so nobody later "fixes" it.
