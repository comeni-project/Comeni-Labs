# The registry leaves — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` — task by task,
> in a worktree, driven by you rather than farmed to subagents (`CLAUDE.md`, *How to start
> implementing*). Steps use `- [ ]` for tracking.

**Goal:** `registry/` becomes a git submodule of `comeni-project/comeni-registry` at the same
path, and the drift subsystem is deleted rather than repointed.

**Architecture:** A plain submodule pinned to a SHA, mounted where the directory already is, so
all 33 test files that load `ROOT / "registry"` stay byte-identical. The one new failure mode — a
clone without `--recurse-submodules` leaves the directory empty — is answered by one legible
refusal in two places rather than 33 confusing test failures.

**Tech Stack:** git submodules, GNU make, GitHub Actions, pytest.

**Spec:** [`notes/specs/2026-08-16-the-registry-leaves.md`](../specs/2026-08-16-the-registry-leaves.md)

## Global Constraints

- **Work in a worktree**, never the main checkout. This plan runs in `.worktrees/issues-43-46`.
- **The submodule pins `fb2ded9`**, tagged `v0.2.0` on `comeni-project/comeni-registry`. Already
  pushed on 2026-08-16; do not re-push.
- **URL is `https://github.com/comeni-project/comeni-registry`** — HTTPS, not SSH, so a CI runner
  and an anonymous clone both work.
- **`make verify`, not `make check`**, closes Tasks 1 and 3: this changes where `registry/` comes
  from, and `test_counts.py` is the only thing that runs a tool against it.
- **Every new guard is watched failing** and gets a row in
  [`notes/audits/guard-ledger.md`](../audits/guard-ledger.md). That is A14's condition.
- **No count goes into prose.** `make residue` and `make check` derive their own.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `.gitmodules` | the URL and path of the one submodule | 1 |
| `registry/` | gitlink to `fb2ded9`, replacing 37 tracked files | 1 |
| `Makefile` | `registry-present` prerequisite; `drift` deleted | 2 |
| `mendel_resolver/layers.py` | `load()` refuses an empty layer directory | 2 |
| `tests/test_registry_submodule.py` | the guard, and that it fires | 2 |
| `tools/check_registry_drift.py` | **deleted** | 3 |
| `tests/test_registry_drift.py` | **deleted** | 3 |
| `.github/workflows/ci.yml` | `submodules: true` at two sites | 3 |
| `.github/workflows/nightly.yml` | `submodules: true`; `registry-drift` job deleted | 3 |
| `LICENSE-DATA` | **deleted** — no CC-BY data remains here | 4 |
| `CLAUDE.md`, `README.md`, `docs/guides/contributing.md`, `ARCHITECTURE.md` | prose | 4 |
| `notes/journal/2026-08-16-evening.md` | appended: what this found | 4 |

---

## Task 1: the submodule replaces the directory — **done, and it found a defect**

> **Correction, 2026-08-16.** Step 5 compared file digests and passed; the defect was one level
> up. The submodule puts `LICENSE`, `README.md` and a `.git` *file* beside the declared kinds,
> and `.git` reads `gitdir: …/worktrees/issues-43-46/modules/registry` — so the **layer digest**
> became machine-dependent while every file was byte-identical. `make verify` stayed green.
>
> Caught by building the spine on `main` and on the branch and diffing `pipeline.yml`, which is
> what Step 5 should have said in the first place. **The step is rewritten below to compare the
> artifact rather than the files**, and the fix — an allowlist in `declared_entries()`, shared by
> the digest and by `layers.load()`'s symlink scan — is Task 1's real content.
>
> It also nearly reintroduced A9: `is_dir()` follows a symlink, so a `contracts/` linked out of
> the layer would have been walked rather than refused. Three watched reverts.

**Files:**
- Create: `.gitmodules`
- Replace: `registry/` (37 tracked files → one gitlink)

**Interfaces:**
- Produces: `registry/` at the same path with the same contents, sourced from the submodule.
  Every later task and all 33 test files depend on that path being unchanged.

- [x] **Step 1: Record what the directory holds now, to compare against**

```bash
find registry -type f | sort | sha256sum
find registry -type f | wc -l          # expect 37
```

Write both numbers down. Step 5 compares against them.

- [x] **Step 2: Remove the tracked copy**

```bash
git rm -r --cached registry
rm -rf registry
```

`--cached` first and `rm -rf` second, deliberately: if the submodule add fails, `git checkout
registry` brings the files back.

- [x] **Step 3: Add the submodule pinned to the tag's commit**

```bash
git submodule add https://github.com/comeni-project/comeni-registry registry
cd registry && git checkout fb2ded9 && cd ..
git add registry .gitmodules
```

`git submodule add` checks out the remote default branch; the explicit `checkout` is what pins
the SHA rather than whatever `main` happens to be at clone time.

- [x] **Step 4: Confirm `.gitmodules` says exactly this**

```ini
[submodule "registry"]
	path = registry
	url = https://github.com/comeni-project/comeni-registry
```

No `branch =` line. The spec's §2 argues why: moving the pin should be a reviewable line in a
commit diff, not something that happens on the next fetch.

- [x] **Step 5: Confirm the bytes did not move**

```bash
find registry -type f -not -path 'registry/.git*' | sort | sha256sum
```

Expected: **the same digest as Step 1**, and the file count is 37 plus `LICENSE` and `README.md`
which the standalone repo carries and the vendored copy did not.

If the digest differs, stop. The submodule is pinned to the wrong commit, and every downstream
task would be building on a registry nobody compared.

- [x] **Step 6: Run the full gate**

Run: `make verify`
Expected: PASS. **This is not sufficient and Task 1 proved it** — see the correction above.
The claim "a pure relocation" is about the *artifact*, so test the artifact:

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --out /tmp/sub  --gate lint
git -C ../.. stash list >/dev/null  # build the same goal on main, in the main checkout
diff /tmp/sub/pipeline.yml /tmp/main/pipeline.yml
```

Expected: **no output.** A relocation that changes one byte of `pipeline.yml` is not a
relocation, and the layer digest is the byte most likely to move.

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "build: registry/ is a submodule pinned at v0.2.0 (#46)"
```

---

## Task 2: an empty registry refuses legibly — **done**

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py` — `load()`
- Modify: `Makefile` — a `registry-present` prerequisite
- Create: `tests/test_registry_submodule.py`

**Interfaces:**
- Consumes: `registry/` from Task 1.
- Produces: `mendel_resolver.layers.load()` raises `ValueError` with the sentence below when a
  layer directory exists but holds no `DeclaredKind` subdirectory.

- [x] **Step 1: Write the failing test**

`tests/test_registry_submodule.py`:

```python
"""An unchecked-out submodule says so, rather than failing 33 times about contracts.

`registry/` is a git submodule since issue #46. `git clone` without `--recurse-submodules`
leaves it as an empty directory that exists — so every "does the path exist" check passes,
the loader finds no contracts, and the failure surfaces as `cannot route this goal` or as a
contract count of zero. None of those name the cause.
"""

import pathlib

import pytest
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent


def test_an_empty_layer_directory_names_the_submodule(tmp_path):
    empty = tmp_path / "registry"
    empty.mkdir()
    with pytest.raises(ValueError) as caught:
        layers.load(empty)
    assert "submodule" in str(caught.value)
    assert "git submodule update --init" in str(caught.value)


def test_a_directory_with_kinds_is_not_mistaken_for_an_empty_one():
    """The real registry must not trip the check. Watched by reverting the `any()` to `all()`."""
    loaded = layers.load(ROOT / "registry")
    assert loaded.registry.contracts
```

- [x] **Step 2: Run it and watch it fail**

Run: `uv run pytest tests/test_registry_submodule.py -v`
Expected: FAIL — the first test raises nothing, because `load()` on an empty directory currently
returns a `Layers` with an empty registry rather than raising.

- [x] **Step 3: Implement the refusal**

In `packages/mendel-resolver/src/mendel_resolver/layers.py`, inside `load()`, at the top of the
`for layer in layers:` loop — **before** the symlink scan, so the cheaper and more likely
diagnosis comes first:

```python
    for layer in layers:
        if layer.is_dir() and not any(
            (layer / kind.value).is_dir() for kind in DeclaredKind
        ):
            raise ValueError(
                f"{layer} holds no registry data — it has none of the "
                f"{len(DeclaredKind)} declared kinds in it.\n"
                "\n"
                "If this is `registry/`, it is a git submodule and was not checked out:\n"
                "\n"
                "    git submodule update --init\n"
                "\n"
                "`git clone --recurse-submodules` avoids this. See docs/guides/contributing.md."
            )
```

`len(DeclaredKind)` rather than a literal, for invariant 11's stated reason: the count said
"four" for six plans and was wrong the day `roles/` arrived.

`any()` rather than `all()`: a layer legitimately carries only some kinds — an overlay with one
contract and nothing else is the normal private-layer case, and demanding all five would refuse
every real overlay.

- [x] **Step 4: Run and watch it pass**

Run: `uv run pytest tests/test_registry_submodule.py -v`
Expected: PASS, both tests.

- [x] **Step 5: Watch the guard fail on its subject**

Change `any(` to `all(` in the code you just wrote and run the tests again.

Expected: `test_a_directory_with_kinds_is_not_mistaken_for_an_empty_one` FAILS — the real
registry has five kinds so `all()` passes there; use an overlay fixture if it does not fire.
Restore `any(`, and record both this and Step 2's failure in the guard ledger.

- [x] **Step 6: Add the Makefile prerequisite**

A contributor's first command is `make check`, not pytest. In `Makefile`, above `help:`:

```make
registry-present:
	@if [ ! -d registry/contracts ]; then \
	  echo "registry/ is empty — it is a git submodule and was not checked out."; \
	  echo; \
	  echo "    git submodule update --init"; \
	  echo; \
	  echo "\`git clone --recurse-submodules\` avoids this."; \
	  exit 1; \
	fi
```

and add `registry-present` as the first prerequisite of `check`:

```make
check: registry-present lint test types docs links  ## everything CI runs on a pull request (~1 min, no Docker)
```

Add `registry-present` to the `.PHONY` line.

- [x] **Step 7: Watch the Makefile guard fail**

```bash
mv registry /tmp/registry-hidden && mkdir registry
make check          # expect: the message above, exit 1, in under a second
rmdir registry && mv /tmp/registry-hidden registry
make check          # expect: PASS
```

Record it in the ledger. **This is the step that matters most in this task** — the guard exists
for a state that only occurs on someone else's machine, so producing that state here is the only
way it is ever tested.

- [x] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: an unchecked-out registry says so, in one sentence (#46)"
```

---

## Task 3: the drift subsystem is deleted — **done**

**Files:**
- Delete: `tools/check_registry_drift.py`, `tests/test_registry_drift.py`
- Modify: `Makefile` — remove `drift`, its `.PHONY` entry, the `REGISTRY` block, and its line
  in `verify`
- Modify: `.github/workflows/ci.yml` — `submodules: true` at lines 29 and 73
- Modify: `.github/workflows/nightly.yml` — `submodules: true` at 33, 61 and 76; delete the
  `registry-drift` job at line 20 and its second checkout at 36

- [x] **Step 1: Delete the tool and its test**

```bash
git rm tools/check_registry_drift.py tests/test_registry_drift.py
```

Both go: a drift check after this compares the submodule against itself, which passes for a
reason that has nothing to do with what it claims to measure — the exact failure mode the guard
ledger is for.

- [x] **Step 2: Strip the Makefile**

Delete the `drift:` target, the `REGISTRY ?=` block with its eleven-line comment, `drift` from
`.PHONY`, and this line from `verify`:

```make
	@$(MAKE) --no-print-directory drift
```

Update `verify`'s help text from `## check + slow + guards + drift` to
`## check + slow + guards — needs Docker, ~2 min. See CLAUDE.md`.

- [x] **Step 3: Give CI the submodule**

In `.github/workflows/ci.yml`, both checkout steps become:

```yaml
      - uses: actions/checkout@v4
        with:
          submodules: true
```

Same at all three remaining sites in `nightly.yml`.

- [x] **Step 4: Delete the nightly drift job**

Remove the whole `registry-drift:` job from `.github/workflows/nightly.yml` — its comment block,
its two checkouts, its uv step and its run step. `generated-docs` becomes the first job.

- [x] **Step 5: Check the workflows parse**

Run: `uv run python -c "import yaml,pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('both parse')"`
Expected: `both parse`.

- [x] **Step 6: Confirm nothing still calls the deleted tool**

Run: `grep -rn "check_registry_drift\|make drift" --include='*.py' --include='*.yml' --include='Makefile' --include='*.md' . | grep -v '^\./notes/'`
Expected: **no output.** `notes/` is excluded on purpose — the record correctly names a tool that
existed, the same scope decision `make links` and `test_architecture.py` make.

- [x] **Step 7: Full gate**

Run: `make verify`
Expected: PASS, and `verify` no longer prints a drift line.

- [x] **Step 8: Commit**

```bash
git add -A
git commit -m "build: delete the drift subsystem — there is one copy now (#46)"
```

---

## Task 4: the prose, and closing out — **done**

**Files:**
- Delete: `LICENSE-DATA`
- Modify: `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, `docs/guides/contributing.md`
- Modify: `notes/journal/2026-08-16-evening.md`

- [x] **Step 1: Delete `LICENSE-DATA` and repoint what cites it**

```bash
git rm LICENSE-DATA
```

Three live references, each of which becomes a pointer to the registry repo's own licence:

- `README.md:178`
- `docs/guides/contributing.md:113`
- `CLAUDE.md:430`

Each should say that registry data is CC-BY-4.0 **in `comeni-registry`**, which carries its own
`LICENSE`. Do not simply delete the sentence: the licence split is a real fact about the project
and a reader needs to know which repository holds which.

- [x] **Step 2: Redirect registry contributions**

`docs/guides/contributing.md:8` opens by calling registry data the most valuable contribution.
It now goes to a different repository. Say so in the first paragraph, with the two-pull-request
cost named rather than hidden — the spec's §6 is the argument, and it belongs in front of a
contributor rather than in a working note.

- [x] **Step 3: Update the architecture tree**

`CLAUDE.md`'s Architecture block currently reads:

```
registry/      one directory per DeclaredKind + registry.yml — THE LAYER
```

It is now a submodule, and the paragraph below it says the layer is "ready to extract" — which is
past tense as of this plan. Both need rewriting, and `ARCHITECTURE.md`'s account of the load
order should say where the layer comes from.

- [x] **Step 4: Append to the journal entry**

`notes/journal/2026-08-16-evening.md` already covers issue #41 from today. Append a section for
#43 and #46: the decision that data stays in files, the submodule pin and its tag, what the
drift deletion removed, and anything these tasks found that the plan did not predict.

- [x] **Step 5: Final gate**

Run: `uv run ruff check . && make verify && make links`
Expected: PASS.

- [x] **Step 6: Prove the success criterion in §8 of the spec**

```bash
cd /tmp && rm -rf clone-test
git clone --recurse-submodules https://github.com/comeni-project/Comeni-Labs clone-test
```

This clones `main`, which does not have the submodule yet — so run it against the branch:

```bash
git clone --recurse-submodules -b issues-43-46 \
  https://github.com/comeni-project/Comeni-Labs /tmp/clone-test
cd /tmp/clone-test && uv sync && make check
```

Expected: PASS, with `registry/` populated entirely by the submodule. **Then the negative case:**

```bash
git clone -b issues-43-46 https://github.com/comeni-project/Comeni-Labs /tmp/clone-bare
cd /tmp/clone-bare && make check
```

Expected: the one-sentence refusal from Task 2, exit 1, not a test failure.

This step requires the branch to be pushed, so push before running it.

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: the registry lives elsewhere, and the prose says so (#46)"
```

---

## How it lands

**One branch, one PR**, closing #46 and carrying #43's decision commit. Four tasks, each with its
corrections recorded inline in this file. Anything a task discovers and does not fix is filed as
its own issue rather than left as a note.

## Self-review

Checked against the spec, 2026-08-16:

- **Every spec section has a task.** §2 → Task 1; §4 → Task 2; §3 and §5 → Task 3; §6 → Task 4;
  §8 → Task 4 Step 6.
- **§7's three exclusions are respected**: no loader change beyond a refusal that reads the
  directory it was already given; no pin automation; no signature checking.
- **One thing the spec did not anticipate, recorded rather than smuggled:** Task 2's refusal
  lands in `load()`, which is `mendel-resolver` — a **pure** package. It adds no import and
  reaches nothing; `DeclaredKind` is already imported there. It is a `ValueError` rather than a
  diagnostic code because `MD0000`–`MD0099` is empty, which is issue #49; when that band is
  filled this refusal is its first candidate.
- **Task 1 Step 5 is the load-bearing verification** and is written as a stop rather than a
  check: a wrong pin would leave every later task building on a registry nobody compared.
