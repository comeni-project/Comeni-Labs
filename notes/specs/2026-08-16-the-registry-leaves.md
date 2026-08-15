# The registry leaves — `registry/` becomes a submodule

**Issue [#46](https://github.com/comeni-project/Comeni-Labs/issues/46). Written 2026-08-16,
against the tree at `ae61fa5`.**

`registry/` holds 37 files under CC-BY-4.0 in a repository whose code is Apache-2.0, and an
identical copy lives at `github.com/comeni-project/comeni-registry`. Two copies that must agree
is a standing hazard, and `tools/check_registry_drift.py` exists only because of it.

## 1. What the operator asked for

Four goals, all of them stated on the issue:

1. **Repo hygiene** — Comeni-Labs is code; the registry is data under a different licence.
2. **Independent release** — the registry versions and signs separately, so a laboratory can pin
   a registry version without pinning an engine version.
3. **Kill the drift problem.**
4. **Prove the layer is portable** — `CLAUDE.md` claims loading a layer from anywhere is "a path
   change and nothing else". Doing it is the test of that claim.

Goal 3 is the one that shapes the design. Drift is not *detected better* here; it is **made
impossible**, because there stops being a second copy. The whole drift subsystem is deleted
rather than kept and pointed somewhere new.

## 2. The mechanism: a plain submodule at the same path

`registry/` becomes a git submodule of `comeni-project/comeni-registry`, pinned to a commit SHA,
mounted at the path it already occupies.

**Every one of the 33 test files that loads `ROOT / "registry"` stays byte-identical.** That is
the entire argument for this shape over the alternatives — a fetch-to-`.registry/` target or a
published data package would each rewrite 33 files and change what `mendel build --root .`
means. A submodule changes where the bytes come from and nothing about where they are.

**Plain, not branch-tracking.** `.gitmodules` records the URL and the path; the SHA lives in the
tree. Moving it is `git submodule update --remote` followed by a commit, and the SHA appears in
that commit's diff — a registry change becomes a reviewable line in the engine's history rather
than something that happens invisibly on the next fetch.

**The prerequisite is already done.** `comeni-registry`'s `main` was three commits behind — it
lacked `roles/`, the rewritten rule format, and the twelve-measurement vocabulary. Those landed
on 2026-08-16 and the layer is tagged **`v0.2.0`** at `fb2ded9`. A submodule pins a SHA, so a
stale remote would have pinned a registry that cannot build the spine.

## 3. What is deleted

**The drift subsystem, entirely:**

- `tools/check_registry_drift.py`
- `tests/test_registry_drift.py`
- `make drift`, and its line in `make verify`
- the `registry-drift` job in `.github/workflows/nightly.yml`

The tool's own docstring says it exists because "`registry/` here and
github.com/comeni-project/comeni-registry hold the same layer today". After this they do not hold
the same layer — they *are* the same layer. Keeping a drift check would be checking a copy
against itself.

**`make drift` also retires a mechanism that has already failed once.** Its
`REGISTRY ?= ../comeni-registry` resolved to `.worktrees/comeni-registry` when run from a
worktree — which is where `CLAUDE.md` requires the work to happen — so it printed "skipped"
rather than failing, and Plan 1.15 Task 0 edited all twelve contracts under a green
`make verify`. **That was repaired in the round-four issues work** and the fix, using
`--git-common-dir`, is live today; it is cited twice in the guard ledger as the archetype of a
check disabled by its own default. Deleting the target removes the shape rather than the bug:
an optional check that skips when its input is missing is a check that reports success for the
wrong reason, and the submodule leaves nothing optional to miss.

**Root `LICENSE-DATA` goes too.** It exists for CC-BY-4.0 registry data, and after this there is
no CC-BY-4.0 data in the repository. `comeni-registry` carries its own `LICENSE`. Leaving a
licence file for content that is not present is a claim about nothing.

## 4. The failure mode this introduces, and the guard for it

`git clone` without `--recurse-submodules` leaves `registry/` **empty**. Today that produces 33
test failures whose messages are about missing contracts, and a `mendel build` that reports it
cannot route the goal. None of them says *the submodule is not checked out*.

This is the single most likely thing to bite a new contributor, and it is the case the repository
would normally refuse legibly. **A check that runs before anything else and says one thing:**

```
registry/ is empty — the registry is a submodule and was not checked out.

    git submodule update --init

`git clone --recurse-submodules` avoids this; see docs/guides/contributing.md.
```

It belongs in the `Makefile` as a prerequisite of `check`, `verify` and `static`, because a
contributor's first command is `make check` rather than a pytest invocation, and in
`mendel_resolver.layers.load()` so a direct `mendel build` gets the same sentence. Loading is
also where issue #49's `MD0000` band belongs, so this refusal is written as prose now and is a
candidate to become a code when that band is filled — recorded here so the two are not designed
twice.

**It must be watched failing**, per A14: empty the submodule directory, run `make check`, read
the message. A guard for a state nobody has produced is a guard nobody has tested.

## 5. What changes in CI

`actions/checkout@v4` gains `submodules: true` at four sites — two jobs in `ci.yml`, two in
`nightly.yml`. The `registry-drift` job is deleted rather than updated.

**The pull-request lane stays offline in the sense that matters.** It fetches a pinned SHA from
GitHub during checkout, which is the same network the code checkout already uses; no test reaches
the network, and invariant 1's guards are untouched. `--gate stub` and `--gate test` still need
Docker and still run nightly.

## 6. What changes for a contributor

Registry data — a contract, a rule, a measurement — is the most valuable contribution and now
goes to a **different repository**. `docs/guides/contributing.md` currently sends it here.

That is a real cost and it is worth naming: a change that touches both the engine and the
registry becomes two pull requests, and the engine one cannot merge until the registry one does.
It is the direct consequence of goal 2, and the alternative — keeping registry data in the engine
repo so it can ride along — is the thing the issue asked to stop.

## 7. What is explicitly not in scope

- **No change to the loader.** `layers.load()` takes layer roots and knows nothing about git.
  Invariant 11 is untouched. If this needs a loader change, the claim that a layer is portable
  was false.
- **No automation that bumps the pin.** A bot moving the registry pointer would move what a
  pipeline resolves to without a human reading the diff, which is invariant 2's shape of mistake.
- **No signed-tag verification.** `comeni-registry` has signed tags in the plan
  (`federation.md` §3); checking a signature at load time is its own design and its own spec.

## 8. Success criterion

`make verify` passes from a fresh `git clone --recurse-submodules`, with `registry/` supplied
entirely by the submodule; `make check` from a clone *without* it refuses in one legible sentence
rather than 33 failures; and `git grep -l 'registry'` over `tests/` shows the same files it does
today, unmodified.
