# Documentation compaction: implementation plan (#118)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans, in one hand
> (`CLAUDE.md`: subagents for review and design only). Tick each step as it completes; record any
> step carried out differently in the execution record at the end.

**Goal:** `CLAUDE.md` becomes a ≤ 300-line working brief with no dead paths, the journal is
compacted into `docs/notes/now.md` by written rules, and two checks in `make check` keep it so.

**Architecture:** Content moves, and nothing true is deleted. History goes to `now.md` and the
journal's archive, arguments go to `docs/design/invariants.md`, the brief keeps rules and pointers.
Two small tools, a path check and a size budget, are written first and watched failing, so the
*before* is measured, and they join `make check` last, when they pass.

**Tech stack:** Markdown, Python 3.12 tools under `tools/`, pytest under `tests/repo/`, `make`,
`git worktree`, the `claude-md-management:claude-md-improver` skill.

**Spec:** [`docs/superpowers/specs/2026-09-28-docs-compaction-design.md`](../specs/2026-09-28-docs-compaction-design.md).
**Issues:** #118, under 14.11 (#130), Task 14 (#119). Each task below is a sub-issue of #118.

## Global constraints

- `CLAUDE.md` ≤ **300** lines; `docs/notes/now.md` ≤ **150**. Compact, never raise the limit.
- **Nothing true is thrown away.** Anything removed from `CLAUDE.md` is in `invariants.md` or
  `now.md`, in an archive, or named as dropped with its reason in the commit message.
- **Raw journal entries are moved, never edited.** Corrections go in `now.md`.
- **Removing a worktree needs the operator to see the list first.** Keep and name any with
  uncommitted work. Never `--force`.
- `CLAUDE.md`'s own writing rules still apply to what it keeps: lead with what the reader gets, no
  provenance in a task page.
- The new checks join `make check` **only in the last task**, when they pass. Until then the
  branch stays green.

## Review focus

1. **A path check that cries wolf.** A command line, a glob, a URL or a `module.attr` in
   backticks reported as a dead path, until nobody reads the output (`check_links.py` records
   that trap). Pinned in Task 2's tests.
2. **A path check that passes on nothing.** A regex that matches no tokens reports zero dead
   paths on any file. Task 2 asserts it finds the 29 in today's `CLAUDE.md` before any fix.
3. **A worktree holding uncommitted work** removed with it. Task 1 checks `git status` in each,
   and never forces.
4. **An invariant whose argument is lost in the move.** Task 6's line-by-line check against the
   old file.
5. **`now.md` stating something the code no longer does.** Each line cites its entry, and Task 4
   spot-checks five claims against the code.

---

### Task 1 (#155): the worktrees

**Files:** none in the repo; `.worktrees/` and `.claude/worktrees/` shrink.

- [x] **Step 1: List them**, with their branch, whether that branch is merged into `main` or
  `living-pipeline-design`, and whether the tree is clean:

```bash
git worktree list --porcelain | awk '/^worktree /{print $2}' | tail -n +2 | while read w; do
  b=$(git -C "$w" rev-parse --abbrev-ref HEAD)
  merged=no
  for base in main living-pipeline-design; do
    git merge-base --is-ancestor "$b" "$base" 2>/dev/null && merged="into $base"
  done
  dirty=$(git -C "$w" status --porcelain | wc -l)
  printf '%-70s %-40s merged:%-30s uncommitted:%s\n' "$w" "$b" "$merged" "$dirty"
done
```

- [x] **Step 2: Show the operator the table**, and wait. Proposed for removal: merged, 0
  uncommitted. Kept and named: anything else.
- [x] **Step 3: Remove the approved ones** with `git worktree remove <path>` (never `--force`),
  then `git worktree prune`. Branches stay.
- [x] **Step 4:** `git worktree list` shows only what was kept. Record the removed paths in the
  execution record.

### Task 2 (#156): the path check

**Files:**
- Create: `tools/check_doc_paths.py`, `tests/repo/test_doc_checks.py`

**Interfaces:**
- Produces: `dead_paths(text: str, root: Path) -> list[tuple[int, str]]`, and `main()` checking
  `FILES = ["CLAUDE.md", "docs/notes/now.md", "docs/design/invariants.md"]` (a missing file in
  that list is skipped until it exists, so the tool can be written before the files).

- [x] **Step 1: The failing tests**

```python
"""The two checks that keep CLAUDE.md short and its paths real (#118)."""

import sys
from pathlib import Path

from support.paths import ROOT  # the repository root, per tests/README.md

sys.path.insert(0, str(ROOT / "tools"))  # how test_architecture.py imports check_links
import check_doc_paths as cdp  # noqa: E402
import check_doc_sizes as cds  # noqa: E402  (Task 3 creates it; until then this import fails)


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "here.md").write_text("x")
    (tmp_path / "packages" / "p" / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "packages" / "p" / "src" / "pkg" / "mod.py").write_text("x")
    return tmp_path


def test_a_dead_path_is_reported_with_its_line(tmp_path):
    root = _tree(tmp_path)
    text = "one\nsee `docs/design/gone.md`\nand `docs/design/here.md`\n"
    assert cdp.dead_paths(text, root) == [(2, "docs/design/gone.md")]


def test_a_package_module_path_resolves_under_src(tmp_path):
    root = _tree(tmp_path)
    assert cdp.dead_paths("`pkg/mod.py` and `pkg/mod.py:12`", root) == []


def test_what_is_not_a_path_is_not_reported(tmp_path):
    """Review focus 1: a checker whose output is mostly noise stops being read."""
    root = _tree(tmp_path)
    text = ("`uv run pytest tests/guards/` `https://x.org/a.md` `registry/tools/**/main.nf` "
            "`comeni_core.layered.stack()` `--registry X` `<package>-v<version>` "
            "`git show 83c873d^:docs/design/wiener.md`")
    assert cdp.dead_paths(text, root) == []


def test_it_finds_the_dead_paths_in_claude_md_as_it_was():
    """Review focus 2: a regex matching nothing passes every file. Measured before the cleanup."""
    before = (ROOT / "tests" / "fixtures" / "claude-md-2026-09-28.md").read_text()
    assert len(cdp.dead_paths(before, ROOT)) >= 20
```

- [x] **Step 2: Freeze the *before*:** `cp CLAUDE.md tests/fixtures/claude-md-2026-09-28.md`. The
  fixture is the measured starting point, and Task 6 checks the rewrite against it. Run the tests:
  `uv run pytest -q tests/repo/test_doc_checks.py`. Expected: FAIL, `No module named
  'check_doc_paths'`. Until Task 3 exists, comment out the `check_doc_sizes` import line and
  restore it there.
- [x] **Step 3: Implement**

```python
"""Every backticked repository path in the agent brief and its two companions exists (#118).

`make links` checks Markdown links, and CLAUDE.md cites paths in backticks, which is how 29 dead
references to docs deleted on 2026-09-02 went unseen. This checks those.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["CLAUDE.md", "docs/notes/now.md", "docs/design/invariants.md"]
_TICK = re.compile(r"`([^`\n]+)`")
_EXT = (".md", ".py", ".yml", ".yaml", ".toml", ".ts", ".tsx", ".json", ".nf", ".html", ".sh")


def _looks_like_path(token: str) -> bool:
    if any(c in token for c in " *{}<>$^") or "://" in token or token.startswith(("-", "~", "/")):
        return False
    bare = re.sub(r":\d+(-\d+)?$", "", token)
    return "/" in bare or bare.endswith(_EXT)


def _exists(token: str, root: Path) -> bool:
    bare = re.sub(r":\d+(-\d+)?$", "", token).rstrip("/")
    if (root / bare).exists():
        return True
    return any((src / bare).exists() for src in root.glob("packages/*/src"))


def dead_paths(text: str, root: Path) -> list[tuple[int, str]]:
    dead = []
    for number, line in enumerate(text.splitlines(), start=1):
        for token in _TICK.findall(line):
            if _looks_like_path(token) and not _exists(token, root):
                dead.append((number, token))
    return dead


def main() -> int:
    failed = 0
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            continue
        for number, token in dead_paths(path.read_text(), ROOT):
            print(f"{name}:{number}: `{token}` does not exist")
            failed += 1
    if failed:
        print(f"{failed} dead path(s). Fix the path, or cite a removed file as `git show <commit>^:<path>`.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Run the tests.** Expected: 4 passed. Then run the tool on today's `CLAUDE.md`
  (`uv run python tools/check_doc_paths.py`) and **read the whole output**. Every line must be a
  real dead path. A false positive means tightening `_looks_like_path` and adding it to the third
  test, not ignoring it. Record the count; the spec measured 29.
- [x] **Step 5: Commit**: `test(docs): the path check, and the before it measures — #118`.
  It does **not** join `make check` yet.

### Task 3 (#157): the size budget

**Files:**
- Create: `tools/check_doc_sizes.py`
- Modify: `tests/repo/test_doc_checks.py`

- [x] **Step 1: The failing tests**

Restore the `import check_doc_sizes as cds` line at the top of the file, then add:

```python
def test_the_budget_names_the_file_and_says_compact(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x\n" * 301)
    out = cds.over_budget(tmp_path, {"CLAUDE.md": 300})
    assert out == [("CLAUDE.md", 301, 300)]


def test_the_budget_for_claude_md_is_three_hundred():
    assert cds.BUDGETS == {"CLAUDE.md": 300, "docs/notes/now.md": 150}
```

- [x] **Step 2: Run to see them fail.**
- [x] **Step 3: Implement**

```python
"""A line budget for the files every session reads first (#118). Compact, don't raise it."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGETS = {"CLAUDE.md": 300, "docs/notes/now.md": 150}


def over_budget(root: Path, budgets: dict[str, int]) -> list[tuple[str, int, int]]:
    out = []
    for name, limit in budgets.items():
        path = root / name
        if path.exists():
            lines = len(path.read_text().splitlines())
            if lines > limit:
                out.append((name, lines, limit))
    return out


def main() -> int:
    over = over_budget(ROOT, BUDGETS)
    for name, lines, limit in over:
        print(f"{name} is {lines} lines, over its budget of {limit}. Compact it "
              f"(docs/notes/compaction.md); don't raise the limit.")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Run the tests** (expected: pass), then the tool (expected: `CLAUDE.md is 1441
  lines`). Commit: `test(docs): a line budget for the brief — #118`.

### Task 4 (#158): the compaction rules, and the first compaction

**Files:**
- Create: `docs/notes/compaction.md`, `docs/notes/now.md`, `docs/notes/journal/archive/`
- Move: every `docs/notes/journal/archive/2026-*.md`, and `docs/notes/journal/archive/2026-09-05-the-forge-walk.md`, into
  `archive/`
- Modify: `docs/notes/journal/README.md`, `docs/notes/README.md`

- [x] **Step 1: Write `compaction.md`** from spec §5, as a page a stranger could follow: the two
  layers; when (a step or substep closes, or five entries are pending); the four operations with
  the spec's examples; move to `archive/` and extend `now.md`'s *compacted through* line; raw
  entries moved, never edited; the same four operations for memory; `CLAUDE.md` is never a
  target.
- [x] **Step 2: Write `now.md`'s frame:** a title, *Compacted through: (none yet)*, and topic
  headings: *What the product is now* · *Task 14 and the walk* · *The forge* · *Wiener (run and
  watch)* · *The stack and how to run it* · *Decided, and not to reopen* · *Open decisions* ·
  *Known traps*.
- [x] **Step 3: Fold the entries in, oldest first:** the loose forge-walk note, then each journal
  entry by date. For each fact, ADD, UPDATE, DELETE or NOOP against what `now.md` already holds.
  Every line ends with its source, e.g. `(2026-09-06)`. Keep to 150 lines. Where a fact
  cannot be kept short, `now.md` says it in a line and the archive holds the long form.
- [x] **Step 4: Spot-check five claims** against the code (review focus 5), e.g. *`make dev` runs
  the APIs from a baked image*, *MI0207 exists*, *there are twelve measurements*. Any line the
  code contradicts is a DELETE or an UPDATE, noted in the execution record.
- [x] **Step 5: Move the entries** with `git mv` into `docs/notes/journal/archive/`, and set
  *Compacted through: 2026-09-28*.
- [x] **Step 6: Rewrite `journal/README.md`** to say what the directory is now (raw entries not
  yet compacted, `archive/` for the rest, `now.md` for what is true), and remove its
  *newest entry is …* pointer. A named pointer is what went stale in August. Update
  `docs/notes/README.md` to list `now.md` and `compaction.md`.
- [x] **Step 7:** `uv run python tools/check_doc_paths.py` for `now.md` (expected: no dead paths
  in it), `uv run python tools/check_doc_sizes.py` (expected: only `CLAUDE.md` over). Commit:
  `docs: the compaction rules, and the journal's first compaction into now.md — #118`.

### Task 5 (#159): `docs/design/invariants.md`

**Files:**
- Create: `docs/design/invariants.md`

- [x] **Step 1: Copy each invariant's full text** from `tests/fixtures/claude-md-2026-09-28.md`
  (*Invariants*, 1–15), plus *The four tiers* and *The three protection profiles* tables, under
  one heading per invariant, numbered as today, with an anchor (`## 11. The registry is a stack`)
  the brief can link to.
- [x] **Step 2: Remove only what is no longer true or no longer argument.** Counts that
  `CLAUDE.md` itself says drift (*"exactly two"* … *"fourteen"*) go, and so does history that
  `now.md` holds. Word for word everywhere else.
- [x] **Step 3: Replace every dead citation** with `git show 83c873d^:<path>` (for example
  `git show 83c873d^:docs/design/wiener.md` §3.1), or with the live path where the file moved
  (`docs/handbook/reference/glossary.md`, `docs/internals/releasing.md`).
- [x] **Step 4:** `uv run python tools/check_doc_paths.py` (expected: none in `invariants.md`),
  `make links`. Commit: `docs(design): the invariants' arguments, moved out of the brief — #118`.

### Task 6 (#160): `CLAUDE.md` rewritten as a brief

**Files:**
- Modify: `CLAUDE.md`

- [x] **Step 1: Run the `claude-md-management:claude-md-improver` audit** on `CLAUDE.md`, read
  its report, and record anything it finds that the spec does not already cover.
- [x] **Step 2: Rewrite to the spec's seven-part shape** (§4): *What this is* · *How we work* ·
  *Invariants* (one line each, linking `docs/design/invariants.md#…`) · *The system in a
  paragraph each* · *Commands* · *Gotchas* · *Where to look* (`now.md` first, then `journal/`,
  the issue tree #119, `invariants.md`, `ARCHITECTURE.md`, `docs/design/authoring-protocol.md`).
  Use the improver for the rewrite, and hold it to that shape.
- [x] **Step 3: The line-by-line check** (review focus 4). Walk `tests/fixtures/claude-md-2026-09-28.md`
  section by section and tick each rule, command and gotcha as **kept** (in the brief), **moved**
  (in `invariants.md` or `now.md`, name where), or **dropped** (with the reason). Paste the
  dropped list, with reasons, into the commit message body.
- [x] **Step 4:** `uv run python tools/check_doc_paths.py` (expected: 0 dead paths),
  `uv run python tools/check_doc_sizes.py` (expected: pass), `make links`. Commit:
  `docs: CLAUDE.md as a working brief — 1,441 lines to N — #118`.

### Task 7 (#161): archive the finished plans, and wire the checks in

**Files:**
- Move: `docs/superpowers/plans/2026-09-02-the-wiki-scaffolding.md`,
  `docs/superpowers/plans/2026-09-04-forge-mvp.md` → `docs/superpowers/plans/archive/`
- Modify: `Makefile`, any doc linking the moved plans (`grep -rn "2026-09-02-the-wiki-scaffolding\|2026-09-04-forge-mvp" --include=*.md .`)

- [x] **Step 1: `git mv`** the two plans and repoint every link the grep finds.
- [x] **Step 2: Add the checks to `make check`:**

```make
check: registry-present lint test types docs docs-status links doc-paths doc-sizes  ## everything CI runs on a pull request (~1 min, no Docker)

doc-paths:      ## every backticked path in CLAUDE.md, now.md and invariants.md exists
	uv run python tools/check_doc_paths.py

doc-sizes:      ## CLAUDE.md ≤ 300 lines, now.md ≤ 150 — compact, don't raise
	uv run python tools/check_doc_sizes.py
```

  and list both in the `.PHONY` line.
- [x] **Step 3: Watch each fail through `make`:** add a line `` `docs/design/gone.md` `` to
  `CLAUDE.md`, see `make doc-paths` name it, and remove it. Append 400 blank lines, see
  `make doc-sizes` fail, and remove them.
- [x] **Step 4:** `make check MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel`
  (expected: only the five known base failures). Commit:
  `chore(docs): the path and size checks join make check; finished plans archived — #118`.
- [x] **Step 5:** tick this plan, fill in the execution record, and close #118 and its task
  sub-issues with the commits.

---

## Execution record

| Task | What was done differently from the plan | Why |
|---|---|---|
| 1 | 11 worktrees removed (the plan said 12; the 12th is the main checkout). The six `agent-*` needed `--force`, **operator-approved**: their only untracked content was scratch and four design-audit drafts byte-identical to `014a169`. The five others hold the `registry` submodule, which `git worktree remove` refuses even with `--force`, so their directories were deleted after checking each `registry/` was clean and on `comeni-registry`'s `main`, then `git worktree prune`. An empty root-owned `.run/wiener` needed a container to delete. | git refuses worktrees containing submodules |
| 2 | Measured **140** before a second rule, **101** after: a bare filename (no directory) is live if any tracked file has that name (`tokens.test.ts` is; `wiener.md` is not), and a bare extension (`.nf`) is not a path. Two tests added for them. The remaining non-paths (tool ids like `samtools/sort`, scheme-less URLs, directories named relative to a context like `rules/`) stay reported; the rewrite qualifies them or takes them out of backticks. The spec's "29" counted only design/notes paths. | noise vs. strictness: a stricter heuristic would miss `notes/journal/` |
| 4 | Compaction read each entry's opening plus its decision, open, next and trap sections (the narrative is superseded by later entries). Five carried claims were spot-checked: four still true (forge digest `String(64)`, `ABORTED` counted as failed, no scope control on the canvas, `submitted_by` hardcoded), and **one UPDATE**: the mendel `api` and `worker` now mount `./packages` (`api` reloads); only `ai-worker` and `wiener-api` are baked. `CLAUDE.md`'s and the plans' links to journal entries were repointed to `archive/` so `make links` stays green until Task 6. `now.md` is 122 lines. | the plan's step 4 said check claims; one was stale |
| 5 | Word for word from the frozen file, with four kinds of edit only: three dead citations became `git show 83c873d^:…` (wiener.md, clinical-data-protection.md, the forge phase-2 spec); the old per-kind directory names (`contracts/`, `rules/`, `vocabularies/`), which no longer exist, were rephrased; one moved path (`registry/tools/nf-core/star/align/contract.yml`); and one paragraph restating invariant 14's count drift and ending on a now-false *and now ten* was removed. List items became `###` headings so the brief can link to each. | the spec's allowed edits |
| 7 | No links needed repointing: the only ones to the moved plans are in archived journal entries (moved, never edited, and outside `make links`) and in this plan's own description of the move. Both checks watched failing through `make` (a planted dead path; 400 blank lines) and `CLAUDE.md` restored byte-identical. `make check`: 2,787 passed, the five base failures; the targets after `test` run individually, all ok. | archive entries are append-only |
| 1 | **Trap, recorded:** `git -C <worktree> submodule deinit` clears `submodule.registry` in the *shared* `.git/config`, which de-initialised the main checkout's `registry` (files intact). Restored with `git submodule init registry`. Never deinit inside a worktree. | the config is shared between worktrees |
