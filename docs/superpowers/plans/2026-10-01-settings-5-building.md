# Settings 5 — Building: pacing and tier 4 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Settings → Building shows the two choices the consultant build will read, *pacing* and *tier 4*, honestly greyed as *designed, not built* until 14.7.8 reads them, and 14.7.8 is told exactly what to lift.

**Architecture:** Two declarations in `comeni_core/settings/catalogue.py`, both with `unavailable=Designed(...)`, in a Building section between Appearance and Models. No consumer is written here: a control nothing reads would be false (spec §7). The handover to 14.7.8 is a comment on #136 and a line in the consultant spec.

**Tech Stack:** Python 3.12, pydantic 2, pytest; the menu from part 3 draws it unchanged.

**Spec:** `docs/superpowers/specs/2026-10-01-settings-design.md` (§7, *Pacing is declared greyed until something reads it*). Issue #117, part 14.7.5.5 of #181. Needs parts 1 and 3.

## Global Constraints

- A setting may never change the pipeline that gets built. Pacing changes how the build talks; tier 4 changes who answers a choice, and an answer by a model is always flagged (invariant 6).
- `Designed` is resolved before the environment (part 1's resolver), so `COMENI_BUILD_PACING` set in `.env` still shows *designed*, never *pinned*.
- #117 stays open until 14.7.8 lifts the mark; this part does not close it.

## Review Focus

1. **`COMENI_BUILD_PACING` set in `.env` before 14.7.8:** the row says *designed*, not *pinned*. Pinned in Task 1.
2. **A stored pacing value from a future build, then a rollback:** the row still resolves (a stored value is ignored while `Designed`). Pinned in Task 1.
3. **The menu's order:** Building sits second, between Appearance and Models. Pinned in Task 1.
4. **14.7.8 forgetting to lift the mark:** the handover names the exact edit and the test to flip. Task 2.
5. **Help text that promises behaviour that does not exist yet:** each help says what the choice *will* do and that it arrives with the consultant build. Task 1 (read in the golden diff).

---

### Task 1: The Building section

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/settings/catalogue.py`
- Modify: `packages/comeni-core/tests/test_settings_catalogue.py` (append)
- Regenerate: `packages/comeni-core/tests/golden/settings-menu.json`

**Interfaces:**
- Consumes: `Setting`, `Section`, `Catalogue`, `Designed` (part 1); `APPEARANCE`, `MODELS`, `PRIVACY` (parts 1 and 4).
- Produces: `PACING`, `TIER4_ANSWERS`, `BUILDING` in `comeni_core.settings.catalogue`. 14.7.8 consumes `PACING` by name (`settings.get(PACING)` → `"together" | "stop_where_needed" | "ask"`).

- [x] **Step 1: Write the failing tests** (append)

```python
from comeni_core.settings import Designed, Source, resolve
from comeni_core.settings.catalogue import BUILDING, CATALOGUE, PACING, TIER4_ANSWERS


def test_building_sits_between_appearance_and_models():
    assert [s.key for s in CATALOGUE.sections][:3] == ["appearance", "building", "models"]
    assert BUILDING.settings == (PACING, TIER4_ANSWERS)


def test_pacing_says_designed_even_when_env_and_a_stored_value_are_set():
    got = resolve(PACING, {"building.pacing": "together"}, {"COMENI_BUILD_PACING": "together"})
    assert (got.value, got.source, got.locked) == ("ask", Source.DEFAULT, True)
    assert isinstance(got.reason, Designed)


def test_tier4_shows_todays_behaviour_designed():
    got = resolve(TIER4_ANSWERS, {}, {})
    assert got.value == "stop" and isinstance(got.reason, Designed)
```

- [x] **Step 2: Run them to verify they fail**

Run: `uv run pytest packages/comeni-core/tests/test_settings_catalogue.py -q`
Expected: FAIL, `ImportError: cannot import name 'BUILDING'`

- [x] **Step 3: Declare them** (in `catalogue.py`, after `APPEARANCE`)

```python
CONSULTANT = "arrives with the consultant build (14.7.8)"

PACING = Setting.choice(
    key="building.pacing",
    label="Pacing",
    help=(
        "How the build walks you through its steps: together, step by step, or set up at once "
        "and stopping only where it needs you. Ask me every time asks at the start of each build."
    ),
    options=[
        ("together", "Go through it together"),
        ("stop_where_needed", "Set it up, stop only where you need me"),
        ("ask", "Ask me every time"),
    ],
    default="ask",
    env="COMENI_BUILD_PACING",
    unavailable=Designed(where=CONSULTANT),
)

TIER4_ANSWERS = Setting.choice(
    key="building.tier4",
    label="Choices no rule settles",
    help=(
        "What happens at a tier-4 choice, where no rule decides. In the consultant build it "
        "always stops for you; letting a model propose the answer, always flagged as a model's, "
        "is designed."
    ),
    options=[("stop", "Always stop for me"), ("model", "Let a model answer, flagged")],
    default="stop",
    env="COMENI_BUILD_TIER4",
    unavailable=Designed(where="a model answering tier 4 in the consultant build is designed"),
)

BUILDING = Section(key="building", title="Building", order=2, settings=(PACING, TIER4_ANSWERS))
```

Add `BUILDING` to `CATALOGUE`'s sections, export the three names from `__init__.py`.

- [x] **Step 4: Regenerate the golden menu, read the diff, run the package**

Run: `SETTINGS_GOLDEN=update uv run pytest packages/comeni-core/tests/test_settings_catalogue.py -q && git diff packages/comeni-core/tests/golden/settings-menu.json | head -80`
Expected: PASS; the diff adds the `building` section with both rows `locked: true` and a `designed` reason. Read both help texts as a researcher would.

Run: `uv run pytest packages/comeni-core packages/mendel-api/tests/test_settings_routes.py -q 2>&1 | tail -2`
Expected: PASS

- [x] **Step 5: Look at it**

With the stack up (`make dev`), open `/settings/building`: two rows, each with *not built*; the ⓘ says what the choice will do and *Designed, not built yet: arrives with the consultant build (14.7.8).* Screenshot at 1280px and 390px for the operator.

- [x] **Step 6: Commit**

```bash
git add packages/comeni-core/src/comeni_core/settings/ packages/comeni-core/tests/test_settings_catalogue.py packages/comeni-core/tests/golden/settings-menu.json
git commit -m "feat(settings): Building — pacing and tier 4, designed until 14.7.8 reads them (#117)"
```

---

### Task 2: Hand pacing to 14.7.8

**Files:**
- Modify: `docs/superpowers/specs/2026-09-28-the-consultant-design.md` (§ *Plan and pacing*)

- [x] **Step 1: Say it in the consultant spec**

At the end of the *Plan and pacing* paragraph that introduces `session.pacing`, add:

```markdown
**Pacing is a setting since 14.7.5** (`comeni_core.settings.catalogue.PACING`, declared
`Designed` until this substep). 14.7.8 removes its `unavailable=`, reads
`installation().get(PACING)` at the start of a build, asks the question only when it is `ask`,
and flips `test_pacing_says_designed_even_when_env_and_a_stored_value_are_set` to assert the
stored value wins. `TIER4_ANSWERS` stays designed.
```

- [x] **Step 2: Tell #136 and #117**

```bash
gh issue comment 136 --body "From 14.7.5.5: pacing is a declared setting, \`comeni_core.settings.catalogue.PACING\`, greyed as designed until this substep reads it. To lift it: remove its \`unavailable=\`, read \`installation().get(PACING)\` when a build starts, ask the pacing question only when it is \`ask\`, and flip \`test_pacing_says_designed_even_when_env_and_a_stored_value_are_set\`. The consultant spec's *Plan and pacing* says the same."
gh issue comment 117 --body "Declared in Settings → Building (14.7.5.5), greyed as designed. Stays open until 14.7.8 (#136) reads it."
```

- [x] **Step 3: Check the docs and commit**

Run: `make doc-paths doc-sizes links`
Expected: `0 broken link(s)`

```bash
git add docs/superpowers/specs/2026-09-28-the-consultant-design.md
git commit -m "docs(spec): pacing is a setting; what 14.7.8 lifts (#117, #136)"
```

---

## Execution record

Executed 2026-10-01, in one hand. Commits 52ac731..(this record).

- **Task 1, ruling:** the tier-4 reason read *"Designed, not built yet: … is designed"*; it now
  says *letting a model answer comes after the consultant build*. Walked headless at 390 px: both
  rows greyed, each marked *not built*.
- **Task 2:** the handover is in the consultant spec (*Plan and pacing*) and on #136; #117 stays
  open until 14.7.8 reads the setting.
- Review: with plan 6 (see its record); nothing found in this plan's own code.
