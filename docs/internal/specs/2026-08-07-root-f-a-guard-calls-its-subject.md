# Root F — a guard calls its subject, it does not re-implement it

**Spec, 2026-08-07.** Closes A21. Root F in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

Verified against the code at `7f918b1`. **Found independently by both round-two reviewers**,
which is why it has one number.

---

## The problem

`digest_of_directory` hashes each entry as:

```python
hasher.update(_FILE)                              # domain separation, added by 6c4fe14
… hasher.update(chunk) …
parts.append(f"{_hex(name.encode())}:{hasher.hexdigest()}")   # name hashing, added by 8d27cf4
```

`test_a_filename_cannot_forge_an_entry_boundary` builds its forged filename from
`hashlib.sha256(b"alpha").hexdigest()` — **without** `_FILE`. That is not the hash the
implementation computes, so the forged directory cannot collide with the honest one whether or
not names are hashed, and the assertion is `!=`.

Reverting the fix the test is named for leaves **12 passed**. Rebuilding the forgery with the
prefix collides on the reverted code and does not collide on the shipped code — so **the digest
is sound and the test that proves it is not.**

**Neither commit is wrong. The interaction is.** `6c4fe14` added domain separation and silently
disarmed the guard protecting `8d27cf4`. A test that hard-codes its subject's internals has an
expiry date nobody wrote down.

---

## The design

### 1. Factor the entry hash, and have both callers use it

```python
def entry_hash(name: str, content: bytes) -> str:
    """The digest of one entry, as `digest_of_directory` computes it.

    Public so a test can construct a forgery the way the implementation constructs an
    entry. A guard that re-derives this format passes as soon as the format moves, which
    is audit A21: `6c4fe14` added `_FILE` and disarmed the guard for `8d27cf4` without
    either commit being wrong.
    """
```

`digest_of_directory` streams its file content, so the shared function takes the finished digest
rather than the bytes for the large path — the exact signature is an implementation detail, and
the requirement is only that **the test cannot express a forgery the implementation would not
produce.**

### 2. Rewrite the test to call it

```python
alpha = entry_hash("a.yml", b"alpha")
(forged / f"a.yml:{alpha}\nb.yml").write_text("beta")
assert digest_of_directory(honest) != digest_of_directory(forged)
```

### 3. Sweep for the class

A21 is not a typo, it is a category: **any guard that constructs its input the way production
constructs it will drift the same way.** The sweep is the deliverable, not the single fix.

Candidates to inspect, from the same pattern:

- `tests/test_digest.py` — the other 11 tests, several of which build expected digests
- `tests/test_lockfile.py` — pins contract digests
- `tests/test_registry_drift.py` — compares two layers
- `tools/generate_types.py` and `tests/test_generated_types.py` — the stub check re-derives the
  stub's shape
- `tests/test_conformance.py` — M0101–M0107 construct module specs

For each: does the test *call* the code under test to build its fixture, or does it *restate*
what that code does? Restating is a finding.

---

## Verification

Root I applies, and here it is the whole method.

| probe | expected |
|---|---|
| revert `_hex(name.encode())` → `name` | **the forgery test fails**, naming boundary forgery |
| revert `_FILE` domain separation | a test fails — today none does, for the file/symlink split |
| the shipped registry | digest unchanged, byte-for-byte |

The second row is the one to watch: A21 is about `_FILE` being *added* and disarming a guard.
The symmetric question — does anything fail if `_FILE` is *removed*? — has never been asked, and
the domain-separation fix (`6c4fe14`) may have the same problem A21 describes.

---

## Blast radius

Tiny. `comeni_core/digest.py` (extract one function),
`packages/comeni-core/tests/test_digest.py` (one test), plus whatever the sweep turns up — which
is the part that is not tiny, and is the reason this spec exists rather than a one-line fix.

---

## What this spec does not cover

`Lockfile.drift_against` is the other site of guard drift in this codebase and is reverted
deliberately under root B, where the layer identity it depends on is changing anyway.
