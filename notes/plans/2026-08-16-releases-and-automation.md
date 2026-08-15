# Releases, tags and automation — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` — task by task, in a
> worktree, driven by you rather than farmed to subagents (`CLAUDE.md`, *How to start
> implementing*). Steps use `- [ ]` for tracking.

**Goal:** the repository can cut a per-package release, its Actions are current and pinned, and
`emitted_by` names the package that actually raises each code.

**Architecture:** Five tasks in dependency order. The Actions bump comes first because it is the
only task whose failure mode is *CI stops working*, and everything after it depends on CI being
trustworthy. `emitted_by` next, because the release notes depend on it. Then constraints, then
the workflow, then the documentation that tells a human how to use any of it.

**Tech Stack:** GitHub Actions, Dependabot, `uv build`, pytest, ruff.

**Spec:** [`notes/specs/2026-08-16-releases-and-automation.md`](../specs/2026-08-16-releases-and-automation.md)

## Global Constraints

- **Work in a worktree.** This plan runs in `.worktrees/release-automation`.
- **Actions are pinned by SHA with the version in a trailing comment.** Never a bare tag.
- **No version bumps.** Everything stays `0.1.0`; this ships machinery, not a release.
- **No PyPI, no signing, no release-please.** Spec §4 and §7.
- **`make verify`** closes Tasks 2 and 3 — both touch `comeni-core`.
- **Every guard is watched failing** and gets a ledger row.
- **The tag format is `<package>-v<version>`**, e.g. `comeni-core-v0.1.0`.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `.github/workflows/ci.yml`, `nightly.yml` | current, SHA-pinned actions | 1 |
| `.github/dependabot.yml` | weekly grouped updates for actions and uv | 1 |
| `comeni_core/diagnostics.py` | `EmittedBy.CORE` | 2 |
| `comeni_core/diagnostics.yml` | ~20 corrected labels | 2 |
| `tests/test_diagnostics_ownership.py` | the guard that derives the answer | 2 |
| `packages/*/pyproject.toml` | version constraints on inter-package deps | 3 |
| `tests/test_packaging.py` | a released package declares what it imports | 3 |
| `.github/workflows/release.yml` | tag → verify → build → Release | 4 |
| `tools/changelog_section.py` | extract one package's section | 4 |
| `docs/guides/releasing.md` | the bump policy and the procedure | 5 |
| `CHANGELOG.md` | per-package sections; two stale claims repaired | 5 |

---

## Task 1: the Actions are current, pinned, and stay that way — **done**

> **Corrections, 2026-08-16.** Step 5 could not run as written: CI triggers on `main` and on a
> pull request, so a push to this branch produced no run at all. Dispatched with
> `gh workflow run ci.yml --ref release-automation` instead.
>
> **And the evidence it produced was narrower than the step claimed.** Zero deprecation warnings,
> but from `ci.yml` — which never uses `nf-core/setup-nextflow`. That action is a **composite**
> with no Node runtime of its own, and its internals are where the old warning came from. Verified
> by reading its manifest at the pinned SHA: its `subaction` and the `actions/setup-java` it pins
> are both `node24`, as are checkout, upload-artifact and setup-uv.
>
> **`tests/test_workflow_pins.py` was added and the plan did not call for it.** Bumping pins by
> hand once is not a mechanism; three guards hold the pinning, the version comment, and the fact
> that the scan reached anything.

**Files:**
- Modify: `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`
- Create: `.github/dependabot.yml`

- [x] **Step 1: Confirm the SHAs before pinning them**

Resolved 2026-08-16. **Re-resolve rather than trusting this table** — a plan is written before it
runs, and a SHA copied from a stale note is worse than a tag:

```bash
for r in actions/checkout actions/upload-artifact astral-sh/setup-uv nf-core/setup-nextflow; do
  t=$(gh api repos/$r/releases/latest --jq .tag_name)
  echo "$r  $t"
done
```

| action | version | SHA as of 2026-08-16 |
|---|---|---|
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/upload-artifact` | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `astral-sh/setup-uv` | v10.0.1 | `20cfd1bf945f4377ade1205e4dbc17946fc9a30d` |
| `nf-core/setup-nextflow` | v3.0.1 | `893c28b667aedeba26e37f296d260ccc5bc4d914` |

- [x] **Step 2: Rewrite every `uses:` as a pinned SHA**

Each becomes, exactly:

```yaml
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: true
```

Both files, every occurrence. The trailing comment is not decoration: it is what makes the line
readable and what Dependabot rewrites when it bumps the pin.

- [x] **Step 3: Check the workflows still parse and still name real jobs**

```bash
uv run python -c "
import yaml, pathlib
for p in sorted(pathlib.Path('.github/workflows').glob('*.yml')):
    d = yaml.safe_load(p.read_text())
    print(p.name, '->', list(d['jobs']))
    for job in d['jobs'].values():
        for step in job.get('steps', []):
            u = step.get('uses')
            assert not u or '@' in u and len(u.split('@')[1]) == 40, f'not pinned: {u}'
print('every action is pinned by SHA')
"
```

Expected: both files list their jobs, and `every action is pinned by SHA`.

- [x] **Step 4: Write `.github/dependabot.yml`**

```yaml
# Without this the Actions go stale by exactly the mechanism that produced them being three to
# five majors behind: nothing was watching, and a deprecation warning on every run is easy to
# stop reading.
#
# Grouped, so a quiet week is one pull request rather than nine. Ungrouped Dependabot is how
# people end up ignoring Dependabot.
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    groups:
      actions:
        patterns: ["*"]
    commit-message:
      prefix: "build"

  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
    groups:
      python:
        patterns: ["*"]
    commit-message:
      prefix: "build"
```

- [x] **Step 5: Push and read the run**

CI must pass **and** the Node 20 deprecation warnings must be gone. That warning is the symptom
this task exists to clear, so read the log rather than only the green tick.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "build: every action current and pinned by SHA, plus dependabot"
```

---

## Task 2: `emitted_by` names the package that raises — **done**

> **Correction, 2026-08-16.** The plan's pattern matched only a code *leading* a string, which
> put all nine conformance codes into `UNLOCATABLE` — the list meant for codes nothing can see,
> where they would have sat unexamined. They use `code="MD0100"` on a `Diagnostic` object.
> Widening the pattern shrank that list from fifteen entries to one, and `MD0202` is the
> survivor: the only code with `refuses: false`, printed as a report line without a colon.
>
> The colon is what separates a mention from an emission, and that assumption got its own test
> rather than a comment. Twenty-three labels were relabelled from the guard's own output rather
> than a hand-copied list.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.py`, `diagnostics.yml`
- Create: `tests/test_diagnostics_ownership.py`

**Interfaces:**
- Produces: `EmittedBy.CORE`; a corrected registry; `_raising_package(code) -> str | None`.

- [x] **Step 1: Write the guard first, and let it report the truth**

`tests/test_diagnostics_ownership.py`:

```python
"""`emitted_by` names the package that raises the code, and this derives it from the source.

The field's docstring said *"Which subsystem raises it"* and was false for roughly a third of
the registry — `EmittedBy` had no `core`, so every code raised in `comeni-core` claimed
`compiler` or `resolver` instead. Six of the nine added on 2026-08-16 were wrong that way, and
they were written wrong because the vocabulary offered no truthful option.

**Absent and mismatched are reported separately.** Some codes have no f-string raise site —
`MD0100` is not a failure, and others are constructed through a `Diagnostic` object. A check
that called those wrong would be switched off within a week.
"""

import pathlib
import re

from comeni_core.diagnostics import REGISTRY

ROOT = pathlib.Path(__file__).parent.parent
PACKAGE_OF = {
    "core": "comeni-core",
    "resolver": "mendel-resolver",
    "compiler": "mendel-compiler",
    "forge": "mendel-forge",
    "api": "mendel-api",
}


def _raising_packages(code: str) -> set[str]:
    """Packages whose source builds a message *starting with* this code."""
    pattern = re.compile(rf"""["'](?:\{{[^}}]*\}} )?{code}:""")
    found = set()
    for path in sorted((ROOT / "packages").rglob("src/**/*.py")):
        if pattern.search(path.read_text()):
            found.add(path.relative_to(ROOT / "packages").parts[0])
    return found


def test_every_locatable_code_is_owned_by_the_package_that_raises_it():
    wrong = []
    for code, spec in sorted(REGISTRY.items()):
        raising = _raising_packages(code)
        if not raising:
            continue  # absent, not mismatched — see the module docstring
        expected = PACKAGE_OF[spec.emitted_by.value]
        if expected not in raising:
            wrong.append(f"{code}: emitted_by={spec.emitted_by.value} but raised in {sorted(raising)}")
    assert wrong == [], "these codes name the wrong package:\n    " + "\n    ".join(wrong)


def test_the_unlocatable_codes_are_a_known_list():
    """A code with no f-string raise site is fine; a *growing* list of them is not.

    Pinned rather than counted, so adding a code that this cannot see is a decision somebody
    makes explicitly instead of a number quietly going up.
    """
    absent = sorted(code for code in REGISTRY if not _raising_packages(code))
    assert absent == UNLOCATABLE, (
        "the set of codes with no locatable raise site moved:\n"
        f"    new: {sorted(set(absent) - set(UNLOCATABLE))}\n"
        f"    gone: {sorted(set(UNLOCATABLE) - set(absent))}"
    )
```

`UNLOCATABLE` is filled in at Step 3, from what the run actually reports.

- [x] **Step 2: Run it and read the report**

Run: `uv run pytest tests/test_diagnostics_ownership.py -v`
Expected: the first test **FAILS** with roughly twenty lines. Keep that output — it is the work
list for Step 4, and it is also the evidence for the ledger row.

- [x] **Step 3: Add `EmittedBy.CORE`**

```python
    CORE = "core"
    """`comeni-core` — the types, the declared-data loaders, and `pipeline.yml` itself.

    Missing until 2026-08-16, and its absence is why roughly a third of the registry named the
    wrong package: `pipeline.py` holds the artifact's validators, so `MD0207`, `MD0212` and the
    rest raise here while being *about* a file the compiler writes. With no truthful option the
    label drifted to whichever subsystem the code felt like it belonged to, which is a vocabulary
    teaching people to lie to it.
    """
```

Then fill `UNLOCATABLE` from Step 2's run, sorted.

- [x] **Step 4: Correct every label the guard names**

One `emitted_by:` per entry. **No message, band, or `says` changes** — this is a label repair and
mixing it with wording changes would make the diff unreviewable.

- [x] **Step 5: Run, watch pass, then regenerate the docs**

```bash
uv run pytest tests/test_diagnostics_ownership.py -v
make docs && make links
git diff --stat docs/reference/diagnostics.md
```

Expected: tests pass, and **`docs/reference/diagnostics.md` is unchanged** — the generated page
groups by `concern`, not by `emitted_by`. If that file moves, something other than a label
changed and the diff needs reading.

- [x] **Step 6: Watch both guards fail**

Set one corrected code back to its wrong package → the first test fails and names it. Add a code
to `diagnostics.yml` with no raise site → the second fails saying the unlocatable set moved. Two
ledger rows.

- [x] **Step 7: Fix the stale header while here**

`diagnostics.yml`'s comment still says *"`docs/reference/cli.md`'s table is GENERATED from this
file"*. It has been `docs/reference/diagnostics.md` since issue #41. One line.

- [x] **Step 8: `make verify`, commit**

```bash
git add -A
git commit -m "fix: emitted_by names the package that raises the code"
```

---

## Task 3: a released package declares what it needs — **done**

**Files:**
- Modify: `packages/mendel-resolver/pyproject.toml`, `packages/mendel-compiler/pyproject.toml`
- Create: `tests/test_packaging.py`

- [x] **Step 1: Write the failing test**

```python
"""A released package must declare a version for every workspace package it imports.

In a `uv` workspace `dependencies = ["comeni-core"]` resolves to the checkout and is fine. As a
*released* artifact it is meaningless: a `mendel-compiler` tarball would accept any
`comeni-core`, including one predating a type it imports. Independent versions are only real if
the constraints are.
"""

WORKSPACE = {"comeni-core", "mendel-resolver", "mendel-compiler"}


def test_every_workspace_dependency_carries_a_lower_bound():
    unbounded = []
    for path in sorted((ROOT / "packages").glob("*/pyproject.toml")):
        data = tomllib.loads(path.read_text())
        for dep in data["project"]["dependencies"]:
            name = re.split(r"[><=!~\[]", dep)[0].strip()
            if name in WORKSPACE and not re.search(r">=\s*\d", dep):
                unbounded.append(f"{path.parent.name}: {dep!r}")
    assert unbounded == [], (
        "these depend on a workspace package with no lower bound, so a released "
        "artifact would accept any version:\n    " + "\n    ".join(unbounded)
    )
```

- [x] **Step 2: Run and watch it fail**

Expected: FAIL, naming `mendel-resolver: 'comeni-core'` and `mendel-compiler: 'comeni-core'`,
`'mendel-resolver'`.

- [x] **Step 3: Add the bounds**

```toml
dependencies = ["comeni-core>=0.1.0", "pydantic>=2.9", "pyyaml>=6.0"]
```

```toml
dependencies = [
  "comeni-core>=0.1.0",
  "mendel-resolver>=0.1.0",
  "pydantic>=2.9",
  "jinja2>=3.1",
  "pyyaml>=6.0",
]
```

**A lower bound and no upper.** A cap on a package released from this same repository would be a
promise to bump it in lockstep, which is the thing independent versioning exists to avoid.

- [x] **Step 4: Run, watch pass, and confirm the lock still resolves**

```bash
uv run pytest tests/test_packaging.py -v
uv sync --locked
```

`--locked` is the point: if `uv.lock` needs regenerating, that is a change to commit rather than
one to discover in CI.

- [x] **Step 5: Watch the guard fail**

Drop `>=0.1.0` from one dependency, confirm the test names it, restore. Ledger row.

- [x] **Step 6: Confirm each package still builds and tests alone**

```bash
for p in comeni-core mendel-resolver mendel-compiler; do
  uv build --package $p --out-dir /tmp/dist-$p
  uv run pytest packages/$p/tests -q
done
```

Expected: three sdists and three wheels, and 172 / 162 / 28 passing. This is the claim
per-package releases rest on, and it is checked here rather than assumed.

- [x] **Step 7: `make verify`, commit**

```bash
git add -A
git commit -m "build: workspace dependencies carry version bounds"
```

---

## Task 4: the release workflow — **done**

**Files:**
- Create: `.github/workflows/release.yml`, `tools/changelog_section.py`
- Create: `tests/test_changelog_section.py`

- [x] **Step 1: Write `tools/changelog_section.py` test-first**

```python
def test_it_extracts_one_package_section(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n"
        "## [0.2.0] - 2026-09-01\n\n"
        "### comeni-core\n\n- a thing\n\n"
        "### mendel-compiler\n\n- another thing\n\n"
        "## [0.1.0] - 2026-08-01\n\n"
        "### comeni-core\n\n- the first thing\n"
    )
    assert section(changelog, "comeni-core", "0.2.0") == "- a thing"


def test_a_missing_section_is_an_error_not_an_empty_release(tmp_path):
    """A release with empty notes is worse than a refused release: it looks finished."""
    ...
    with pytest.raises(SystemExit):
        section(changelog, "mendel-resolver", "0.2.0")
```

- [x] **Step 2: Implement it, run, watch pass**

Read the file, find `## [<version>]`, then the `### <package>` heading under it, return the lines
until the next heading at the same level or above. Exit non-zero with a message naming both the
package and the version when there is no such section.

- [x] **Step 3: Write `.github/workflows/release.yml`**

```yaml
name: Release

# Tag-driven, one package per tag: `comeni-core-v0.2.0`. The tag *is* the request; nothing
# here decides a version. See docs/guides/releasing.md for the bump policy.
on:
  push:
    tags: ["*-v*"]

permissions:
  contents: write        # cutting a Release writes to the repository

jobs:
  release:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: true

      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          enable-cache: true

      - name: Split the tag into a package and a version
        id: tag
        run: |
          ref="${GITHUB_REF_NAME}"
          echo "package=${ref%-v*}" >> "$GITHUB_OUTPUT"
          echo "version=${ref##*-v}" >> "$GITHUB_OUTPUT"

      - name: The tag and the package's own version must agree
        run: |
          declared=$(uv run python -c "
          import tomllib, pathlib
          p = pathlib.Path('packages/${{ steps.tag.outputs.package }}/pyproject.toml')
          print(tomllib.loads(p.read_text())['project']['version'])
          ")
          if [ "$declared" != "${{ steps.tag.outputs.version }}" ]; then
            echo "tag says ${{ steps.tag.outputs.version }}, pyproject says $declared."
            echo "A tag is a claim about a version; the two disagreeing is a release-time MD0223."
            exit 1
          fi

      - name: The full gate, before anything is published
        run: make check

      - name: Build
        run: uv build --package ${{ steps.tag.outputs.package }} --out-dir dist

      - name: Notes, from the changelog
        run: |
          uv run python tools/changelog_section.py \
            ${{ steps.tag.outputs.package }} ${{ steps.tag.outputs.version }} > NOTES.md

      - name: Cut it
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          gh release create "${GITHUB_REF_NAME}" dist/* \
            --title "${{ steps.tag.outputs.package }} ${{ steps.tag.outputs.version }}" \
            --notes-file NOTES.md
```

**`make check`, not `make verify`:** `verify` needs Docker and the slow lane, and the nightly
workflow already covers it. A release blocked on a container pull is a release people stop
cutting. Record that as a decision rather than an omission.

- [x] **Step 4: Prove the refusal without cutting a release**

The version check is the part most worth testing and the hardest to test in CI. Do it locally:

```bash
uv run python - <<'PY'
import tomllib, pathlib
p = pathlib.Path('packages/comeni-core/pyproject.toml')
print(tomllib.loads(p.read_text())['project']['version'])
PY
```

Expected: `0.1.0`. Then confirm the shell comparison in the workflow rejects `0.2.0` against it —
run the two lines by hand with `steps.tag.outputs.version` substituted.

- [x] **Step 5: Check the workflow parses and is pinned**

Re-run Task 1 Step 3's script. It must now cover three files.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "build: a tag cuts a release, and refuses if it disagrees with the version"
```

---

## Task 5: the documentation, and the changelog — **done**

**Files:**
- Create: `docs/guides/releasing.md`
- Modify: `CHANGELOG.md`, `docs/guides/contributing.md`, `docs/guides/README.md`, `CLAUDE.md`

- [x] **Step 1: Write `docs/guides/releasing.md`**

Two halves, and the policy comes **first** because it is the part people get wrong:

```markdown
# Cutting a release

## Which number moves

| change | bump | example |
|---|---|---|
| a fix, a message, an internal refactor | `0.0.x` | `MD0223`'s wording |
| new behaviour, a new field, a new diagnostic code | `0.x.0` | `MD0001`–`MD0009`; `Pipeline.ai` |
| the artifact format moves, or a public surface breaks | `x.0.0` | `pipeline.yml` 3 → 4 |
```

Then the rules that are not obvious from the table — a new diagnostic code is a **feature**
because a runbook can cite it; a `SCHEMA_VERSION` bump is always **major** for `comeni-core`
because an older Mendel refuses a newer file (`MD0207`); and the bump is **judged, not derived**,
so a wrong bump is a review comment rather than a failing check.

Then the procedure: edit `CHANGELOG.md`, bump the `pyproject.toml`, commit, tag
`<package>-v<version>`, push the tag, watch the workflow.

- [x] **Step 2: Give `CHANGELOG.md` per-package sections, and fix two stale claims**

`[Unreleased]` gains `### comeni-core` / `### mendel-resolver` / `### mendel-compiler`
subheadings, which is the shape `changelog_section.py` reads.

Two sentences in the header are wrong: registry data *"moves to its own repository at Plan 1.7"*
— it moved on 2026-08-16 in issue #46 — and it *"lives in `examples/`"*, which stopped being true
several plans ago.

- [x] **Step 3: Link it from where a contributor looks**

`docs/guides/contributing.md` and `docs/guides/README.md` both gain a line. A guide nothing links
to is a guide nobody reads, which is what issue #41 was about.

- [x] **Step 4: `CLAUDE.md` — the tag scheme and the bump policy**

Short, in Distribution: tags are `<package>-v<version>`, versions are independent, the bump rule
in one line, and a pointer to the guide. **No counts.**

- [x] **Step 5: Final gate**

Run: `uv run ruff check . && make verify && make links`

- [x] **Step 6: One PR**

Nothing deferred. Anything a task finds and does not fix is filed as its own issue.

## Self-review

Checked against the spec, 2026-08-16:

- **Every spec section has a task.** §1 → Tasks 1–3; §2 → Tasks 3–4; §3 → Task 2; §4 → Tasks 1
  and 4; §5 → Task 5; §6 → Task 5 Step 1; §7's exclusions are respected.
- **One thing the spec left open, decided here:** the release workflow runs `make check`, not
  `make verify`. `verify` needs Docker and the slow lane, the nightly workflow covers it, and a
  release blocked on a container pull is a release people stop cutting. Task 4 Step 3 records it
  in the workflow itself rather than only here.
- **Task order is not arbitrary.** Actions first, because their failure mode is *CI stops
  working* and every later task's verification depends on CI being trustworthy.
- **The one step most likely to be skipped is Task 1 Step 5**, reading the log for the absence of
  the deprecation warning. A green tick is not the thing that task is for.
