# Code and documentation organisation — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` and drive this
> yourself, sequentially, task by task. **Do not use `subagent-driven-development`** — that is
> the operator's standing instruction in `CLAUDE.md`, not a preference. Work in a worktree.
> Steps use `- [ ]` for tracking.

**Goal:** make the repository navigable — five packages in `comeni-core` instead of 24 flat
modules, the three files over 850 lines split, the working notes out of `docs/`, and the
documentation written for the operator it actually has.

**Architecture:** pure reorganisation. No new capability, no schema change, no CLI change. The
code moves by lifecycle stage so the directory a reader opens and `ARCHITECTURE.md` agree; the
documentation splits into what a reader consumes (`docs/`) and the record of how it got here
(`notes/`).

**Tech Stack:** Python 3.12, pydantic v2, pytest, `uv`. No new dependencies.

**Spec:** [`docs/internal/specs/2026-08-16-code-and-documentation-organisation.md`](../specs/2026-08-16-code-and-documentation-organisation.md).
Read it before Task 1; every task below argues from a section of it.

## Global Constraints

- **The oracle is the gate, not `make check`.** `uv run python tools/refactor_oracle.py` must
  exit 0 at the end of **every** task. Tasks 1–5 are pure relocation and must not move a digest
  at all. A moved digest is a behaviour change hiding in a large diff, and it is the only real
  risk in this work.
- **`make verify`, not `make check`.** This plan touches `resolve.py`, `router.py`, `rules.py`,
  `mendel_compiler/cli.py`, `mendel_compiler/emit.py` and `comeni_core/pipeline.py` — all six of
  the files `CLAUDE.md` names as unverifiable by `make check` alone.
- **No back-compat module shims.** `comeni_core.pipeline` does not survive as an alias.
  `comeni_core/__init__.py`'s re-exported *names* are unchanged and are the public surface; the
  module paths are internal and move. Two ways to spell one thing is how the two come to
  disagree.
- **Invariant 1.** Nothing here adds an import to a pure package. Task 1 moves files *within*
  `comeni-core`, so `tests/test_purity.py`'s allowlist is unaffected — it keys on the top-level
  module name (`comeni_core`), not on the path.
- **Every guard that names a path as a string is reverted and watched** (Task 5). A rename can
  disable a guard by pointing it at a file that no longer exists, and the failure is silent in
  the direction nobody investigates: the gate goes green *faster*. That is A67's exact shape.
- **Line length 100.** `uv run ruff check .` clean at every commit.
- **`git mv`, never delete-and-create.** `git log --follow` is how the next person finds out why
  a file looks the way it does, and this plan touches almost every file in the repository.

---

## Task 0: the oracle

**Already done** — `tools/refactor_oracle.py` is committed with the spec, and it has been watched
failing (changing featureCounts' `min_mqs` default moved `pipeline.yml` and `nextflow.config` and
correctly left `main.nf` alone).

- [ ] **Step 1: Confirm it agrees before anything moves**

Run: `uv run python tools/refactor_oracle.py`
Expected: exit 0, three digests matching `f1f2d7e5e9cca6a3`, `76355bbf9f10d6e6`,
`72ddb081638edf76`.

If it does **not** agree, stop: `main` has moved since 7315347 and the baseline in the tool
needs re-recording with a stated reason before this plan is safe to run.

---

## Task 1: `comeni-core`'s five packages

**Spec:** Part one. 24 flat modules, 5,541 lines, no grouping.

**Files:**
- Move: 21 modules into 5 subpackages (`git mv`)
- Keep at top level: `__init__.py`, `yaml_strict.py`, `diagnostics.py`, `diagnostics.yml`,
  `profile.pyi`, `py.typed`
- Modify: **79 files, 355 import lines** across `packages/`, `tests/`, `tools/`

**Interfaces:**
- Produces: `comeni_core.declared.*`, `comeni_core.goal.*`, `comeni_core.plan.*`,
  `comeni_core.artifact.*`, `comeni_core.spell.*`
- `comeni_core/__init__.py`'s exported names are **unchanged** — later tasks and all external
  consumers keep using `from comeni_core import Pipeline`.

> **`goal/goal.py` and `profile.pyi`.** The `goal` group contains a module also called `goal`,
> so the import becomes `from comeni_core.goal.goal import Goal`. That reads oddly and is
> correct: the alternative is a package whose `__init__` re-exports, which is the shim this plan
> forbids. `profile.pyi` must move **with** `profile.py` or every type checker loses the stub —
> a `.pyi` replaces its module rather than adding to it.

- [ ] **Step 1: Create the packages**

```bash
cd packages/comeni-core/src/comeni_core
for pkg in declared goal plan artifact spell; do
  mkdir -p $pkg
  printf '"""%s"""\n' "placeholder — Step 3 writes the real docstring" > $pkg/__init__.py
done
```

- [ ] **Step 2: Move the modules**

```bash
cd packages/comeni-core/src/comeni_core
git mv contract.py measurement.py vocabulary.py roles.py registry.py layered.py layer.py declared/
git mv goal.py profile.py profile.pyi premise.py goal/
git mv ir.py decision.py tiers.py plan/
git mv pipeline.py lockfile.py digest.py egress.py gates.py artifact/
git mv marks.py routes.py directives.py spell/
```

Leaves `__init__.py`, `yaml_strict.py`, `diagnostics.py`, `diagnostics.yml`, `py.typed`.

- [ ] **Step 3: Write each package's `__init__.py`**

Each is a docstring and nothing else — **no re-exports**, or the shim ban is broken one
directory down. Example, `declared/__init__.py`:

```python
"""What a registry layer holds: contracts, measurements, vocabularies, roles.

Grouped by lifecycle stage so this directory and `ARCHITECTURE.md`'s five stages agree — a
reader asking "where is a contract validated" should not have to know our type names first.

`layered.py` and `layer.py` live here rather than beside the loaders that use them because
stacking is a property *of* declared data: invariant 11 says every kind stacks through one
mechanism, and that mechanism belongs with the kinds.

**No re-exports.** `comeni_core/__init__.py` is the public surface and this is not a second
one — two ways to spell one thing is how the two come to disagree.
"""
```

Write the other four in the same shape:

- `goal/` — "What was asked for, and what the data measurably looks like. A shape, never data
  (invariant 15)."
- `plan/` — "What was decided: the IR, the record of each ambiguity, and the tier ladder every
  decision exits at."
- `artifact/` — "What is shipped. `pipeline.yml` is the save file, and everything here is either
  part of it or the evidence it carries."
- `spell/` — "How a value is written down: the marked string types, the routes that carry a
  value to a tool, and the directives Nextflow accepts."

- [ ] **Step 4: Rewrite every import**

```bash
cd "$(git rev-parse --show-toplevel)"
python - <<'PY'
import pathlib, re

GROUPS = {
    "declared": ["contract", "measurement", "vocabulary", "roles", "registry", "layered", "layer"],
    "goal": ["goal", "profile", "premise"],
    "plan": ["ir", "decision", "tiers"],
    "artifact": ["pipeline", "lockfile", "digest", "egress", "gates"],
    "spell": ["marks", "routes", "directives"],
}
MOVED = {module: group for group, modules in GROUPS.items() for module in modules}

changed = 0
for path in pathlib.Path(".").rglob("*.py"):
    if ".venv" in path.parts or ".worktrees" in path.parts:
        continue
    text = original = path.read_text()
    for module, group in MOVED.items():
        text = re.sub(
            rf"\bcomeni_core\.{module}\b", f"comeni_core.{group}.{module}", text
        )
    # `comeni_core.goal.goal` is correct; guard against a second pass doubling a prefix.
    text = re.sub(r"comeni_core\.(\w+)\.\1\.", r"comeni_core.\1.", text)
    if text != original:
        path.write_text(text)
        changed += 1
print(f"{changed} files rewritten")
PY
```

Expected: `79 files rewritten`.

- [ ] **Step 5: Fix the path-shaped strings this script cannot see**

`tools/generate_types.py` and `tests/test_generated_types.py` name
`packages/comeni-core/src/comeni_core/profile.pyi`; it is now under `goal/`.
`tests/test_purity.py`'s `ATTRIBUTE_EXEMPT_PATH` is unchanged (`yaml_strict.py` did not move).
`tests/test_construction.py` and `tests/test_purity_runtime.py` name module paths — **leave them
for Task 5**, which reverts and watches each one.

```bash
sed -i 's|comeni_core/profile.pyi|comeni_core/goal/profile.pyi|' tools/generate_types.py tests/test_generated_types.py
```

- [ ] **Step 6: Run everything**

Run: `uv run ruff check . && make verify && uv run python tools/refactor_oracle.py`
Expected: PASS, and **three digests unmoved**.

If a digest moved, the rewrite changed behaviour — `git diff` the non-import lines and stop.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(core): five packages by lifecycle stage, not 24 flat modules (#41)"
```

---

## Task 2: split `pipeline.py`

**Spec:** Part one, the three splits. 1,116 lines doing three jobs.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/artifact/pipeline.py`
- Create: `artifact/materialise.py`, `artifact/load.py`
- Test: existing — `tests/test_pipeline_file.py`, `tests/test_pipeline_totality.py`

**Interfaces:**
- Produces: `artifact.materialise.of(ir, registry, vocab, measurements, layers, *, goal)`,
  called by `Pipeline.of`; `artifact.load` holds the `MD02xx` validators.
- Consumes: everything Task 1 produced.

> **`Pipeline.of` stays a classmethod on `Pipeline`.** `tests/test_construction.py` asserts it is
> the only validating constructor, and moving the *entry point* would need that guard rewritten
> — which is a change to what the guard guards, not to where code lives. The classmethod becomes
> a two-line delegation to `materialise.of`.

- [ ] **Step 1: Create `artifact/materialise.py`**

Move these, unchanged, out of `pipeline.py`: `_ext_args`, `_no_flags_why`, `_meta_entry`,
`_why`, `_settings`, `_call`, `_inputs`, `_channels`, `_default_entry`, and the body of
`Pipeline.of`.

```python
"""Building a `Pipeline` from a resolved IR. The one direction that reads the registry.

Split out of `pipeline.py` because that file was doing three jobs — what the artifact *is*,
how it is built, and what a file must satisfy to be read back — and only this one needs a
registry, a vocabulary and a measurement set. A reader asking "where does `ext_args` get its
premise" was reading 1,116 lines to find out.

`Pipeline.of` stays on `Pipeline` and delegates here: `tests/test_construction.py` asserts it is
the only validating constructor, and that guard is about the entry point rather than the code
behind it.
"""
```

- [ ] **Step 2: Create `artifact/load.py`**

Move `_param_refs`, `_IDENT_CHARS`, and the validators that refuse a *file* rather than
describing a model — `_backfill_provenance_a_v1_file_never_had` and `_readable_and_unambiguous`
stay on `Pipeline` (a pydantic validator cannot move off its model), but their **helpers** move
here.

```python
"""What a `pipeline.yml` must satisfy to be read back. The `MD0200`–`MD0224` band.

These answer a different question from the models beside them: a `Step` says what a step *is*,
and this says what a step somebody hand-edited must still be. The pydantic validators stay on
their models — they cannot move — and everything they call lives here, which is where the
refusals a reader meets are actually written.
"""
```

- [ ] **Step 3: Reduce `Pipeline.of` to a delegation**

```python
    @classmethod
    def of(cls, ir, registry, vocab, measurements=None, layers=(), *, goal) -> "Pipeline":
        """The **only** validating constructor. See `materialise.of` for the body.

        Kept here rather than exposed as a bare function because
        `tests/test_construction.py` asserts nothing else builds one, and that guard names
        this spelling. The docstring that argues why `goal` is keyword-only and required
        moved with the body.
        """
        from comeni_core.artifact import materialise

        return materialise.of(
            ir, registry, vocab, measurements=measurements, layers=layers, goal=goal
        )
```

The function-local import is deliberate and is the one in this plan: `materialise` imports
`Pipeline`, so a module-level import here is a cycle. Say so in a comment.

- [ ] **Step 4: Run everything**

Run: `uv run ruff check . && make verify && uv run python tools/refactor_oracle.py`
Expected: PASS, digests unmoved.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(core): pipeline.py was doing three jobs (#41)"
```

---

## Task 3: split `rules.py`

**Spec:** Part one. 1,170 lines; the validator alone is ~450 of them.

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/rules/` with `__init__.py`, `format.py`,
  `table.py`, `validate.py`
- Delete: `rules.py` (via `git mv` into `rules/format.py`, then split)
- Test: existing — `packages/mendel-resolver/tests/test_rules.py`

**Interfaces:**
- Produces: `mendel_resolver.rules.format` (`Effect`, `DecisionTarget`, `DecisionRow`,
  `Decision`, `Fired`, `Aggregate`, `Transform`, `Derivation`, `Pin`, `Predicate`),
  `mendel_resolver.rules.table` (`RuleTable`, `_key_of`), `mendel_resolver.rules.validate`
  (`RuleValidationError`, every `_validate*`, `_check_*`, `_uncovered_*`, `_computed_over`,
  `_domain_of`, `_fillers_by_role`, `_sole_premise`).
- **`rules/__init__.py` re-exports the public names.** This is the one exception to the shim
  ban and it is not a shim: `rules` was a *module* and becomes a *package*, so its `__init__`
  is the module's own surface rather than a second spelling of a third module's. 19 files import
  `from mendel_resolver.rules import …` and every one of them keeps working.

- [ ] **Step 1: Turn the module into a package**

```bash
cd packages/mendel-resolver/src/mendel_resolver
mkdir rules
git mv rules.py rules/format.py
```

- [ ] **Step 2: Move `RuleTable` and stacking into `table.py`**

Cut from `format.py`: `_key_of`, `class RuleTable`, `_premises_read`, `_applies_to`, `_GOAL_FACTS`.

```python
"""Loading, stacking and querying a rule table.

Split from the models because they answer different questions: `format.py` says what a rule
*is*, and this says how the ones on disk become the ones in force. `Policy.REPLACE` applies per
key, and the key space is namespaced — `derive:<fact>`, `presence:<role>`,
`param:<role>:<name>` — which is what lets both layers live in one directory.
"""
```

- [ ] **Step 3: Move every refusal into `validate.py`**

Cut from `format.py`: `RuleValidationError`, `_comparison`, `_computed_over`,
`_fillers_by_role`, `_validate_target`, `_domain_of`, `_validate_rows`, `_sole_premise`,
`_uncovered_interval`, `_uncovered_values`, `_check_exhaustive`, `_validate`, `_check_when`,
`_ORDERED`, `_OPS`.

```python
"""Every way a rule table is refused at load. The `MD0300`–`MD0315` band.

Its own module because this is where a rule author's error comes from, and it was ~450 lines
buried under the models. Spec §5: everything is refused at load, because the moment a defect
becomes indistinguishable from an absence the diagnostic stops being possible.

`_comparison` lives here rather than beside the evaluator on purpose — the load-time validator
and the runtime matcher must agree on what counts as a comparison, and two copies of that
predicate is how a rule passes validation and then fails to fire.
"""
```

- [ ] **Step 4: Write `rules/__init__.py`**

```python
"""Tier 3: two layers of declared data, and every way they are refused at load.

A package rather than a module since #41 — `rules.py` was 1,170 lines and the validator alone
was ~450 of them. The three parts answer different questions:

| module | question |
|---|---|
| `format` | what a rule *is* |
| `table` | how the ones on disk become the ones in force |
| `validate` | why yours was refused |

**These re-exports are the module's own surface, not a shim.** `rules` was a module and is now
a package, so `from mendel_resolver.rules import RuleTable` means what it always meant. The
plan's ban is on a *second* spelling of a third module's name.
"""

from mendel_resolver.rules.format import (
    Aggregate, Decision, DecisionRow, DecisionTarget, Derivation, Effect, Fired, Pin,
    Predicate, Transform,
)
from mendel_resolver.rules.table import RuleTable
from mendel_resolver.rules.validate import RuleValidationError

__all__ = [
    "Aggregate", "Decision", "DecisionRow", "DecisionTarget", "Derivation", "Effect",
    "Fired", "Pin", "Predicate", "RuleTable", "RuleValidationError", "Transform",
]
```

- [ ] **Step 5: Run everything**

Run: `uv run ruff check . && make verify && uv run python tools/refactor_oracle.py`
Expected: PASS, digests unmoved. No caller outside the package should need editing — if one
does, `__init__` is missing a name.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(resolver): rules.py splits into format, table and validate (#41)"
```

---

## Task 4: split `cli.py`

**Spec:** Part one. 851 lines, and the decomposition is **not** one module per verb.

> **Corrected against the code, 2026-08-16.** The spec and the approved design both said "one
> module per verb". `_build()` is one procedural flow: `explain` returns early having loaded
> nothing; `emit` and `publish` return early having loaded no registry; and `build`, `upgrade`
> and `profile` **share the whole resolution path** — layers, conformance, resolver, `resolve`,
> `Pipeline.of`, write, gate, report. Six modules would duplicate that flow three times, which
> is worse than the 851 lines. Split by *what the verb does to a pipeline* instead.

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/cli/` with `__init__.py`, `parse.py`,
  `resolve_verbs.py`, `artifact_verbs.py`, `report.py`
- Test: existing — `tests/test_pipeline_file.py`, `tests/test_upgrade.py`,
  `tests/test_conformance_cli.py`, `tests/test_publish.py`

**Interfaces:**
- Produces: `mendel_compiler.cli.main(argv)` — unchanged signature, and the console-script entry
  point in `pyproject.toml` keeps pointing at it.

- [ ] **Step 1: Turn the module into a package**

```bash
cd packages/mendel-compiler/src/mendel_compiler
mkdir cli
git mv cli.py cli/__init__.py
```

- [ ] **Step 2: Move the parser into `parse.py`**

Cut the whole `argparse` block out of `_build` into `def parser() -> argparse.ArgumentParser`.
Every `help=` string moves verbatim — several of them carry the argument for why a flag exists
(`--dry-run` is `verify`; `--force` names the directory as another pipeline's evidence) and
losing one would lose the reason.

- [ ] **Step 3: Move the two artifact verbs into `artifact_verbs.py`**

Cut `_emit_verb`, `_publish_verb`, `_refuse_a_divergent_directory`.

```python
"""`emit` and `publish`: the verbs that read a `pipeline.yml` and load no registry.

Together because that is what they have in common and it is the interesting thing about them —
`emit` rebuilds the Nextflow from the artifact alone, which is the whole claim the artifact
makes, and `publish` certifies a directory that already exists. Neither resolves anything.
"""
```

- [ ] **Step 4: Move the shared resolution flow into `resolve_verbs.py`**

Cut everything from `loaded = layers.load(...)` to the final `return 0`, plus `_profiling_goal`.

```python
"""`build`, `upgrade` and `profile`: the three verbs that resolve.

One module because they are one flow with three entry conditions, not three flows. `upgrade`
replays a previous artifact's decisions before resolving; `profile` swaps the goal for one that
measures; `build` does neither. Everything after that — conformance, resolution,
materialisation, the gate — is the same code, and splitting it per verb would copy it three
times.
"""
```

- [ ] **Step 5: Move the printing into `report.py`**

Cut `_report_upgrade`, `_verdict`, `_frozen_against_moved_contracts`, `_displacement_line`.

```python
"""What the verbs print, as distinct from what they do.

`OVERLAY`, `ANSWERED` and `REVIEW` are three different questions — what an installed layer
changed, what a person already settled, and what still needs deciding — and folding any of them
into the others is the defect `cli.py`'s own comments warn about.
"""
```

- [ ] **Step 6: Leave `main`, `_with_pointer` and `_blame` in `cli/__init__.py`**

They are the entry point and the error surface, which is what a reader opens `cli/` for.

- [ ] **Step 7: Run everything**

Run: `uv run ruff check . && make verify && uv run python tools/refactor_oracle.py`
Expected: PASS, digests unmoved.

**`make verify` is mandatory here**, not `make check`: `cli.py` is one of the six files
`CLAUDE.md` names, and `tests/test_counts.py` is the only thing that runs a tool.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(compiler): cli.py splits by what a verb does to a pipeline (#41)"
```

---

## Task 5: the guards that name a path as a string

**Spec:** Part one, the last subsection. A rename can disable a guard by pointing it at a file
that no longer exists, and the gate then goes green **faster** — A67's exact shape.

**Files:**
- Modify: `tests/test_construction.py`, `tests/test_purity_runtime.py`
- Modify: `tools/generate_types.py`, `tests/test_generated_types.py` (already done in Task 1
  Step 5 — confirm)
- Modify: `tests/test_purity.py` (`ATTRIBUTE_EXEMPT_PATH` — confirm unchanged)

- [ ] **Step 1: Update the paths**

```bash
cd "$(git rev-parse --show-toplevel)"
sed -i \
  -e 's|comeni_core/measurement.py|comeni_core/declared/measurement.py|' \
  -e 's|comeni_core/profile.py|comeni_core/goal/profile.py|' \
  -e 's|comeni_core/pipeline.py|comeni_core/artifact/pipeline.py|' \
  tests/test_construction.py
sed -i \
  -e 's|"comeni_core/layered.py"|"comeni_core/declared/layered.py"|' \
  tests/test_purity_runtime.py
```

- [ ] **Step 2: Add the guard-of-the-guard**

A path that names nothing is the defect. Add to `tests/test_construction.py`:

```python
def test_every_exempted_path_names_a_file_that_exists():
    """A67's shape, in the file that exempts spellings rather than the one that scans them.

    `PIPELINE_READERS` is keyed by path and exempts named spellings inside those files. A key
    that matches no file exempts nothing — and silently: the scan finds fewer things to check
    and the gate goes green *faster*, which is the one direction nobody investigates. Issue
    #41 moved every module in `comeni-core`, so this is the day it would have happened.
    """
    root = pathlib.Path(__file__).parent.parent
    missing = sorted(key for key in PIPELINE_READERS if not (root / key).exists())
    assert missing == [], (
        "these exempted paths name files that do not exist, so they exempt nothing:\n  "
        + "\n  ".join(missing)
    )
```

The constant is `PIPELINE_READERS`, a `dict[str, frozenset[str]]` keyed by repository-relative
path — checked against the code on 2026-08-16, because an earlier draft of this plan invented a
`PERMITTED` that does not exist.

Add the equivalent to `tests/test_purity_runtime.py` for its frame paths.

- [ ] **Step 3: Watch each one fail**

For each of the four files, point one path at a name that does not exist, run the guard,
confirm it **fails** rather than passing on an empty scan, and restore. Record a row per guard
in `docs/internal/audits/guard-ledger.md` under a new heading
`## Issue #41 — the guards that name a path`.

- [ ] **Step 4: Run everything**

Run: `uv run ruff check . && make verify && uv run python tools/refactor_oracle.py`
Expected: PASS, digests unmoved.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: a guard that names a path must name one that exists (#41)"
```

---

## Task 6: `docs/internal/` becomes `notes/`

**Spec:** Part two, the tree and the link cost. 69 of the 94 markdown files under `docs/`.

**Files:**
- Move: `docs/internal/` → `notes/`
- Create: `tools/check_links.py`
- Modify: `Makefile` (`check` gains `links`), and every file with a link that crosses the move

- [ ] **Step 1: Write the link checker first**

It has to exist *before* the move, or the move is verified by hand and nobody can re-verify it.

```python
"""Every relative markdown link resolves to a file that exists.

Nothing checked this before issue #41, which is why the move it was written for is worth doing
*with* a checker rather than without one: a mechanical repair verified by hand is a repair
nobody can re-verify next time. 73 relative links live inside the directory being moved and 43
point into it from outside.

Anchors (`#section`) are not checked — that needs a markdown parser and the failure mode is a
reader scrolling, not a reader hitting a 404.

**Two scoping decisions, both learned by running it first.**

Fenced code blocks are skipped. `assert x == [actual, expected]` is not a link, and a first
draft reported eleven of them — a checker whose output is mostly noise is a checker people stop
reading.

`notes/` is not checked, only `docs/` and the root. A plan naming a file its own tasks create is
*correct* at the moment it executes and broken until then, so checking the record would make
`make check` red for the duration of every plan. The cost of a broken link differs by audience:
in `docs/` a reader hits a 404, and in `notes/` a future reader reads a dated document that
already says it describes work not yet done.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent.parent
LINK = re.compile(r"\[[^\]]*\]\((?!https?:|mailto:|#)([^)#]+)")
CHECKED = ("docs", ".")


def _prose(text: str) -> str:
    """The file with fenced code blocks blanked out."""
    kept, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        kept.append("" if fenced else line)
    return "\n".join(kept)


def _markdown() -> list[pathlib.Path]:
    found = sorted((ROOT / "docs").rglob("*.md"))
    return found + sorted(p for p in ROOT.glob("*.md"))


def main() -> int:
    broken = []
    for path in _markdown():
        for target in LINK.findall(_prose(path.read_text())):
            if not (path.parent / target.strip()).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target.strip()}")
    for line in broken:
        print(line)
    print(f"{len(broken)} broken link(s)")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it on the tree as it stands**

Run: `uv run python tools/check_links.py`

Record the count. **If it is not zero, fix those links in this step and commit them
separately** — a pre-existing break repaired inside the move commit is a break nobody can tell
from one the move caused.

- [ ] **Step 3: Move**

```bash
git mv docs/internal notes
```

- [ ] **Step 4: Repair**

Run the checker, fix what it names. The pattern: links that crossed *out* of `internal/` lost a
level (`../../design/x.md` → `../docs/design/x.md`), sibling links inside are unchanged.

Then the 43 references pointing *in*:

```bash
grep -rln "docs/internal" --include='*.md' --include='*.py' . | grep -v .worktrees \
  | xargs sed -i 's|docs/internal/|notes/|g'
```

- [ ] **Step 5: Write `notes/README.md`**

```markdown
# Working notes

**Not documentation.** `docs/` is what a reader or an agent consumes; this is the record of how
the repository got here — dated, append-only where it says so, and kept in the repository
because a decision explained only in a conversation is a decision lost.

| | |
|---|---|
| `journal/` | **start here.** What happened, what is next, what a fresh reader gets wrong. Newest first |
| `plans/` | one per plan, with each task's corrections recorded inline |
| `audits/` | four guard rounds and one design audit, plus `guard-ledger.md` — A14's closure condition |
| `specs/` | the argument behind each plan. Read the spec before the plan |

It moved out of `docs/` on 2026-08-16 (issue #41): 69 of 94 markdown files lived here, so `ls
docs/` showed the working notes before it showed anything a reader wanted.
```

- [ ] **Step 6: Wire the checker into `make check`**

```makefile
check: lint test types docs links  ## everything CI runs on a pull request (~1 min, no Docker)

links:          ## every relative markdown link resolves
	uv run python tools/check_links.py
```

Add `links` to `.PHONY`.

- [ ] **Step 7: Watch it fail**

Break one link deliberately, run `make links`, confirm it names the file and the target, restore.
Record the row in the guard ledger.

- [ ] **Step 8: Run everything**

Run: `uv run ruff check . && make verify && uv run python tools/refactor_oracle.py`
Expected: PASS, digests unmoved (no Python moved in this task).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "docs: the working notes leave docs/, and links are checked (#41)"
```

---

## Task 7: the diagnostics get their own page

**Spec:** Part two. *"i cant easily find the error codes"* — they are two-thirds of the way down
a page about the CLI.

**Files:**
- Modify: `tools/generate_diagnostics_doc.py`
- Create: `docs/reference/diagnostics.md` (generated)
- Modify: `docs/reference/cli.md` (loses the table, gains a pointer)

- [ ] **Step 1: Point the generator at the new file**

Change `DOC` to `docs/reference/diagnostics.md` and give the generated file a header the
generator writes:

```markdown
# Diagnostic codes

Every code Mendel can emit, what it says, and whether it refuses. Run `mendel explain <code>`
for the long form — the fix, and the argument for why it is refused at all.

| band | concern |
|---|---|
| `MD0100`–`MD0199` | a contract disagrees with its module |
| `MD0200`–`MD0299` | the pipeline file — a setting, an override, or the format |
| `MD0300`–`MD0399` | routing and resolution |

<!-- generated by tools/generate_diagnostics_doc.py — do not edit -->
```

- [ ] **Step 2: Replace the table in `cli.md` with a pointer**

```markdown
## Diagnostics

Every code, with what it says and whether it refuses, is in
[`diagnostics.md`](diagnostics.md). For any one of them:

    uv run mendel explain MD0104
```

- [ ] **Step 3: Regenerate and check**

Run: `uv run python tools/generate_diagnostics_doc.py && make docs && make links`
Expected: PASS.

- [ ] **Step 4: Watch the freshness check fail**

Edit `docs/reference/diagnostics.md` by hand, run `make docs`, confirm it refuses, restore.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: the error codes get their own page (#41)"
```

---

## Task 8: the front door, and a README per directory

**Spec:** Part two. The current front door is organised by document type, which helps only a
reader who already knows which type they need.

**Files:**
- Modify: `docs/README.md`
- Create: `docs/guides/README.md`, `docs/reference/README.md`, `docs/concepts/README.md`,
  `notes/plans/README.md`, `notes/audits/README.md`, `notes/specs/README.md`
- Confirm: `docs/design/README.md` and `notes/journal/README.md` exist — **those two do; the six
  above do not.** Checked 2026-08-16, because an earlier draft of this plan said `audits/` had
  one and it does not.

- [ ] **Step 1: Rewrite `docs/README.md` to route by reader**

Three doors, in this order:

```markdown
# Documentation

## I am driving Mendel

An agent, or a person doing what an agent does: turning a question into a goal, building a
pipeline, and tuning it.

1. [Driving Mendel](guides/driving-mendel.md) — the loop, end to end
2. [`pipeline.yml`, field by field](reference/pipeline-schema.md) — the save file
3. [Diagnostic codes](reference/diagnostics.md) — why something was refused

## I am running a pipeline Mendel produced

3. [Getting started](guides/getting-started.md)
4. [Measuring your data](guides/measuring-your-data.md)
5. [Privacy and egress](concepts/privacy-and-egress.md) — what leaves, and through which door

## I am changing Mendel

6. [`ARCHITECTURE.md`](../ARCHITECTURE.md) — the five stages, against real types
7. [Contributing](guides/contributing.md)
8. [The design arguments](design/) — why it works this way
9. [Working notes](../notes/) — how it got here
```

- [ ] **Step 2: Write the six missing directory READMEs**

Six, not nine: `docs/`, `docs/design/` and `notes/journal/` already have one.

Each answers *what is in here and which file do I open first*. Not a file listing — `ls` already
does that. Example, `docs/reference/README.md`:

```markdown
# Reference

What each declared file may contain, field by field, and what the CLI does.

**Start with [`pipeline-schema.md`](pipeline-schema.md)** if you are driving Mendel: it is the
file you read and edit, and everything else here describes an input to producing one.

| | |
|---|---|
| `pipeline-schema.md` | the save file — every step, setting and reason |
| `diagnostics.md` | every code, and whether it refuses |
| `cli.md` | the verbs and their flags |
| `goal-schema.md` | what you ask for |
| `contract-schema.md` `rule-schema.md` `measurement-schema.md` `vocabulary-schema.md` | what a registry layer holds |
```

- [ ] **Step 3: Check**

Run: `make links && make check`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: the front door routes by reader, and every directory says what it holds (#41)"
```

---

## Task 9: `driving-mendel.md`, and the root

**Spec:** Part two and Part three.

**Files:**
- Create: `docs/guides/driving-mendel.md`
- Move: `CONTRIBUTING.md` → `docs/guides/contributing.md`, plus a root stub
- Delete: `CODE_OF_CONDUCT.md`

- [ ] **Step 1: Write `docs/guides/driving-mendel.md`**

The loop, as a sequence, with real commands and real output. Sections:

1. **Produce a goal** — `Goal` holds type ids, states and declared measurements. A shape, never
   data (invariant 15). Show `examples/rnaseq-goal.yml`.
2. **Build** — `mendel build --goal … --out build/ --gate lint`, and what the three summary
   lines mean (`OVERLAY`, `ANSWERED`, `REVIEW`).
3. **Read the save file** — `why:` beside every value; `tier` and `review_level`; `premise` and
   what `origin: asserted` obliges you to check.
4. **Change one thing** — edit a `value:` *and* its `why.reason`, because `MD0223` refuses a
   value whose reason was written about a different one.
5. **Rebuild from the file** — `mendel emit build/pipeline.yml --out build/`, no registry and no
   network.
6. **Answer a tier-4 question in the file** — `human_override` and `override_reason`, and why
   the tier stays 4 while the review clears.
7. **Re-resolve against a moved registry** — `mendel upgrade --dry-run`.

Every command in it must be one this repository can actually run; verify each before committing.

- [ ] **Step 2: Move `CONTRIBUTING.md` and stub the root**

```bash
git mv CONTRIBUTING.md docs/guides/contributing.md
cat > CONTRIBUTING.md <<'EOF'
# Contributing

See [`docs/guides/contributing.md`](docs/guides/contributing.md).

This stub stays at the root because GitHub reads this path to offer contributing guidelines on
a pull request — removing it would drop an affordance rather than ceremony.
EOF
```

- [ ] **Step 3: Delete `CODE_OF_CONDUCT.md`**

```bash
git rm CODE_OF_CONDUCT.md
grep -rn "CODE_OF_CONDUCT" --include='*.md' . | grep -v .worktrees
```

Remove every reference the grep finds.

- [ ] **Step 4: Check**

Run: `make links && make check && uv run python tools/refactor_oracle.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: write down the loop, and clear the root (#41)"
```

---

## Task 10: `CLAUDE.md`, and closing out

**Spec:** Part three. 723 lines, the largest file in the repository and the file most likely to
be read *in full* by an agent — so the same complaint applies to it.

**Files:**
- Modify: `CLAUDE.md`
- Delete: `tools/refactor_oracle.py`
- Create: `notes/journal/2026-08-16-evening.md`

- [ ] **Step 1: Restructure `CLAUDE.md` with the skill**

**REQUIRED SUB-SKILL:** `claude-md-management:revise-claude-md`. This is the operator's
instruction, given 2026-08-16.

Last, deliberately: it describes the layout every task above changed, so doing it first would
mean writing it twice. What must be true when it is done:

- every path it names exists (`make links` covers the markdown ones; check the rest by hand)
- the `docs/internal/` references are `notes/`
- the module paths in Invariants and Gotchas match the five packages
- no count is asserted in prose that a tool could derive — `len(DeclaredKind)`,
  `make residue`, `tests/test_egress.py`'s literal list

- [ ] **Step 2: Delete the oracle**

```bash
git rm tools/refactor_oracle.py
```

Run it one last time before deleting, and paste the three digests into the journal entry: they
are the evidence that eleven tasks of relocation changed nothing.

- [ ] **Step 3: Write the journal entry**

`notes/journal/2026-08-16-evening.md`. What it must carry: the three digests, unmoved; what the
oracle caught if anything; the `cli.py` correction (the design said one module per verb and the
code said otherwise); the link-checker count before and after; and what is *not* done —
`ARCHITECTURE.md` still describes five stages that now have directories, and whether those two
should be generated from each other is a question this plan did not answer.

- [ ] **Step 4: Final verification**

```bash
uv run ruff check . && make verify && make links
```

Expected: PASS. The oracle is gone by now, so this is the last gate.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: CLAUDE.md matches the layout, and the oracle retires (#41)"
```

---

## Related issues, and what was checked

- **#41** is closed by this plan.
- **#43 (data storage)** is untouched and out of scope.
- **A67** is the finding Task 5 generalises: a guard that names a path can be disabled by a
  rename, silently, in the direction that makes the gate faster.
- **A14**: every new guard in Tasks 5, 6 and 7 gets a ledger row. `make residue` will move.

## Self-review

Checked against the spec, 2026-08-16:

- Every spec section has a task. Part one → Tasks 1–5; Part two → Tasks 6–9; Part three →
  Tasks 9–10; the oracle → Task 0 and Task 10 Step 2.
- **One correction the code forced**, recorded in Task 4 rather than smuggled: the spec's "one
  module per verb" is wrong, because three verbs share the whole resolution flow. The split is
  by what a verb does to a pipeline.
- **One exception to the shim ban**, argued in Task 3: `rules/__init__.py` re-exports, because
  `rules` was a module and becomes a package — its `__init__` is its own surface, not a second
  spelling of something else's.
- **One function-local import**, in Task 2 Step 3: `Pipeline.of` → `materialise`, because
  `materialise` imports `Pipeline`. Named so it is a decision rather than something a reader
  finds and 'fixes'.
