# Plan 1.10 — the pipeline file

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, sequentially,
> task by task. **Do not use `subagent-driven-development`** — that is the operator's standing
> instruction in `CLAUDE.md`, not a preference. Subagents are for review and design only.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `pipeline.ir.json`, `mendel.lock.yml` and `PublishBundle`'s on-disk form with one
human-readable, editable `pipeline.yml`, and make a resolved parameter actually reach the tool it
was resolved for.

**Architecture:** A new `comeni_core.Pipeline` materialises everything the emitter reads, so
`emit(pipeline)` takes one argument instead of four and needs no registry. Settings gain a declared
route (`via:` + `key:` + `template:`) so a resolved value composes into `ext.args` rather than into a
`params.<x>` line nothing reads. Diagnostics become data in `comeni_core/diagnostics.yml`, with
`docs/reference/cli.md` generated from it.

**Spec:** [`../specs/2026-08-07-the-pipeline-file.md`](../specs/2026-08-07-the-pipeline-file.md).
**It takes precedence over this plan and over the code.** Written against `ae92002`.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2, PyYAML, pytest, `uv`, Nextflow 25.10.4.

---

## Preconditions

**This plan does not start until a separate prerequisite PR has merged.** Decided 2026-08-09: a
mechanical rename inside a two-thousand-line feature diff is unreviewable, because nobody can tell
the substitution from the logic.

That PR contains exactly two things:

1. **`M0100`–`M0107` → `MD0100`–`MD0107`** across `conformance.py`, `cli.py`,
   `tests/test_conformance.py`, `tests/test_conformance_cli.py`, `tests/test_spine_contracts.py`,
   `tests/test_modulespec.py`, `docs/reference/cli.md`, `docs/design/conformance.md`, `CLAUDE.md`
   and `CHANGELOG.md`. **`docs/internal/journal/`, `docs/internal/audits/` and
   `docs/internal/plans/2026-08-05-conformance-checking.md` are not touched** — append-only, correct
   on their date. `docs/reference/cli.md` gains one line: the `MD` prefix arrived 2026-08-07 and
   older internal notes predate it.
2. **`tests/golden/spine/nextflow.config`**, with a test beside
   `test_matches_the_golden_file` in `packages/mendel-compiler/tests/test_emit.py`.

Acceptance for that PR: `make check` green, **441 passed**, count unchanged.

---

## Global Constraints

Every task's requirements implicitly include these. Values are copied verbatim from `CLAUDE.md` and
the spec.

- **`comeni-core`, `mendel-resolver` and `mendel-compiler` do not reach the network.** No new import
  may be network-shaped. `tests/test_purity.py` and `tests/test_purity_runtime.py` are the guards.
- **Determinism is a test.** Same `Goal` → byte-identical `.nf`. Anything that serialises a set needs
  a `field_serializer` that sorts, or `digest_of` becomes hash-seed dependent.
- **No field of `Pipeline` may be a bare `frozenset`.**
- **Every payload field must be a declared shape.** `tests/test_egress.py`'s
  `test_every_payload_field_is_a_declared_shape` walks recursively. No `Any`, no `object`, no `Path`,
  no bare `str`, no `abc.Mapping`, no `bytes`.
- **Six fields may hold free text**, and `tests/test_egress.py`'s `FREE_TEXT_FIELDS` names all six
  literally: `PromptRequest.prompt`, `GateFailure.tool_message`, and `reason` on `ResolvedValue`,
  `ParamDecision`, `ProducerDecision` and `SourceDecision`. **`CLAUDE.md`'s invariant 14 still says
  "exactly two" and is stale** — 1.9's A16 split took it from four to six, and that file's own comment
  says so. Task 12 corrects the invariant. The count must not change *from six* in this plan.
- **Mappings are written, lists are stored.** A `model_validator(mode="before")` normalises the
  ergonomic mapping form to a list, following `Constraints._accept_mapping`.
- **A code may never be renumbered.** A full band overflows into a new band.
- **`{value}` accepts `[A-Za-z0-9_.:+-]*`, `int`, `float`, `bool`.** Refuse, never escape.
- **Line length 100.** `uv run ruff check .` must be clean. `ruff format` is *not* a gate — do not
  run it across the repo.
- **`make verify`, not `make check`**, for any task touching `resolve.py`, `router.py`, `rules.py`,
  `mendel_compiler/cli.py` — and **`emit.py`, which this plan adds to that list** (Task 12).
- **Import modules, not symbols, where tests monkeypatch.** `from x import f` binds past a later
  patch of `x.f`.
- **Jinja: `{% endfor %}`, never `{%- endfor %}`.** With `trim_blocks` the dash collides every loop
  iteration onto one line.

---

## File structure

**Created**

| path | responsibility |
|---|---|
| `packages/comeni-core/src/comeni_core/diagnostics.yml` | the code registry: one entry per code |
| `packages/comeni-core/src/comeni_core/diagnostics.py` | load it, validate a code, expose `explain` |
| `packages/comeni-core/src/comeni_core/pipeline.py` | `Pipeline`, `Step`, `Setting`, `Channel`, `CallArg`, `RegistryProvenance`, `Via`, `ExtKey`, `Pipeline.of()` |
| `tools/generate_diagnostics_doc.py` | render the `cli.md` table; `--check` for CI |
| `tests/test_diagnostics_registry.py` | the registry's own guards |
| `tests/_walk.py` | the annotation walkers, extracted from `test_egress.py` so both use one |
| `comeni_core/directives.py` | the process directives Nextflow accepts, and the version read |
| `tests/test_pipeline_totality.py` | every replaced field has a home |
| `docs/reference/pipeline-schema.md` | `pipeline.yml` for a stranger |

**Modified**

| path | change |
|---|---|
| `comeni_core/marks.py` | `Mark.NF_TEMPLATE`, `NfTemplate` |
| `comeni_core/contract.py` | `Param` gains `via`, `key`, `template` |
| `comeni_core/tiers.py` | `ValueSource.HUMAN` |
| `comeni_core/ir.py` | `overrides()`; `needs_review()` excludes answered |
| `comeni_core/egress.py` | door 4's payload becomes `Pipeline`; `PublishBundle` retires |
| `mendel_resolver/resolve.py` | an override keeps the displaced tier, sets `source: human` |
| `mendel_resolver/replay.py` | a reported `stale` list; the orphan sweep |
| `mendel_compiler/emit.py` | `emit(pipeline)`; template composition; double-quoted `ext.args` |
| `mendel_compiler/conformance.py` | `where` replaces `contract_id`; `MD0108`; codes come from data |
| `mendel_compiler/cli.py` | writes `pipeline.yml`; `emit`/`upgrade --dry-run`/`--out` |
| `registry/contracts/nf-core/*.yml` | `via:`/`key:`/`template:` on both `seq_platform` params |
| `Makefile`, `.github/workflows/nightly.yml` | the doc freshness check |

---

## Task 1: the diagnostics registry is data

**Files:**
- Create: `packages/comeni-core/src/comeni_core/diagnostics.yml`
- Create: `packages/comeni-core/src/comeni_core/diagnostics.py`
- Create: `tests/test_diagnostics_registry.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/conformance.py` (delete `EXPLANATIONS`,
  point `explain` at the registry, validate `Diagnostic.code`)

**Interfaces:**
- Produces: `comeni_core.diagnostics.REGISTRY: dict[str, DiagnosticSpec]`;
  `DiagnosticSpec(code, emitted_by, concern, says, fires_on, refuses, fix, explanation)`;
  `comeni_core.diagnostics.explain(code: str) -> str`;
  `comeni_core.diagnostics.spec_for(code: str) -> DiagnosticSpec` raising `UnknownDiagnosticError`.

`diagnostics.yml` ships inside the wheel automatically — hatchling includes every file under
`packages = ["src/comeni_core"]`, which is how `py.typed` already ships.

- [ ] **Step 1: write the failing test**

```python
# tests/test_diagnostics_registry.py
"""The code registry is data, and a code that is not declared cannot be emitted.

Invariant 7's shape applied to diagnostics: a closed vocabulary. `EXPLANATIONS` was a Python
dict beside a hand-maintained table in `docs/reference/cli.md`, and the two could disagree
with nothing to notice.
"""

import pytest

from comeni_core import diagnostics


def test_every_existing_conformance_code_is_declared():
    for code in ("MD0100", "MD0101", "MD0102", "MD0103",
                 "MD0104", "MD0105", "MD0106", "MD0107"):
        assert code in diagnostics.REGISTRY, code


def test_a_spec_carries_a_fix_and_an_explanation():
    spec = diagnostics.spec_for("MD0104")
    assert spec.fix, "a diagnostic without a fix is half a diagnostic"
    assert spec.explanation


def test_an_undeclared_code_is_refused():
    with pytest.raises(diagnostics.UnknownDiagnosticError):
        diagnostics.spec_for("MD9999")


def test_says_is_one_line():
    """It is rendered into a markdown table row; a newline breaks the table silently."""
    for code, spec in diagnostics.REGISTRY.items():
        assert "\n" not in spec.says, code
```

- [ ] **Step 2: run it and watch it fail**

Run: `uv run pytest tests/test_diagnostics_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'comeni_core.diagnostics'`.

- [ ] **Step 3: write `diagnostics.yml` with the eight existing codes**

Copy each `says` from the current `docs/reference/cli.md` table and each `explanation` from the
current `EXPLANATIONS` dict in `conformance.py`, verbatim. Do not reword them in this task —
a rewording mixed into a move is a change nobody reviewed.

```yaml
# The diagnostic registry. One entry per code; `docs/reference/cli.md` is generated from it.
#
# `MD` is Mendel's deterministic core. Bands of one hundred group by concern, and a full band
# overflows into a new band rather than renumbering: a published code is something a laboratory
# runbook can cite. See docs/internal/specs/2026-08-07-the-pipeline-file.md §10.
MD0100:
  emitted_by: compiler
  concern: conformance
  says: "no module source to check against — **warns, never blocks**"
  fires_on: [build]
  refuses: false
  fix: |
    Vendor the module under `vendor/modules/`, or accept the contract as unverified.
  explanation: |
    The contract names a module whose source is not present, so nothing could check
    it. The build continues and the contract is marked unverified, which is recorded
    on the IR and reaches a publish bundle. A curator may refuse to curate an
    unverified contract: a claim about a module, with no module to check it against,
    is a claim without evidence.
```

…and the same shape for `MD0101`–`MD0107`.

- [ ] **Step 4: write the loader**

```python
# packages/comeni-core/src/comeni_core/diagnostics.py
"""The diagnostic registry, loaded from data.

One source, two consumers: `Diagnostic` validates its `code` against this, and
`tools/generate_diagnostics_doc.py` renders `docs/reference/cli.md` from it. A code that
exists in one and not the other was possible when the long form lived in a Python dict beside
a hand-maintained markdown table; it is now unrepresentable.
"""

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from comeni_core.loading import load_mapping_one_way  # root G's duplicate-key loader
from comeni_core.marks import Line, Text

_REGISTRY_FILE = Path(__file__).with_name("diagnostics.yml")


class UnknownDiagnosticError(KeyError):
    """A code nothing declares. Raised rather than returned: emitting an undeclared code is a
    programming error, not a user's mistake."""


class EmittedBy(StrEnum):
    COMPILER = "compiler"
    RESOLVER = "resolver"
    FORGE = "forge"
    API = "api"


class DiagnosticSpec(BaseModel):
    """What a code *is*, as opposed to what one occurrence of it says.

    `summary` and `detail` stay at the check site because they interpolate the actual
    mismatch — this contract, this declared value against that module's. Identity and
    standing advice are data, which is what makes the document renderable.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    emitted_by: EmittedBy
    concern: Line
    says: Line
    fires_on: list[str]
    refuses: bool
    fix: Text
    explanation: Text


def _load() -> dict[str, DiagnosticSpec]:
    raw = load_mapping_one_way(_REGISTRY_FILE)
    return {
        code: DiagnosticSpec(code=code, **body)
        for code, body in sorted(raw.items())
    }


REGISTRY: dict[str, DiagnosticSpec] = _load()


def spec_for(code: str) -> DiagnosticSpec:
    if code not in REGISTRY:
        raise UnknownDiagnosticError(
            f"{code} is not a declared diagnostic. Known: {', '.join(sorted(REGISTRY))}"
        )
    return REGISTRY[code]


def explain(code: str) -> str:
    """Long-form, after `rustc --explain`."""
    if code not in REGISTRY:
        return (
            f"{code} is not a diagnostic this version emits.\n"
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return f"{code}\n\n{REGISTRY[code].explanation.rstrip()}"
```

If root G's loader is not named `load_mapping_one_way`, find the equivalent in `comeni_core`
(1.9 Part G, "a declared file cannot be read two ways") and use it. **Do not call
`yaml.safe_load` directly** — it silently keeps the last of duplicate keys, which is exactly
the defect root G closed.

- [ ] **Step 5: run the test and watch it pass**

Run: `uv run pytest tests/test_diagnostics_registry.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 6: make `Diagnostic` validate its code, and delete `EXPLANATIONS`**

In `conformance.py`: delete the `EXPLANATIONS` dict, re-export `explain` from
`comeni_core.diagnostics`, and add to `Diagnostic`:

```python
    @field_validator("code")
    @classmethod
    def _declared(cls, code: str) -> str:
        diagnostics.spec_for(code)      # raises UnknownDiagnosticError
        return code
```

Add a test in `tests/test_diagnostics_registry.py`:

```python
def test_a_diagnostic_cannot_carry_an_undeclared_code():
    """The old guard was a test that every emittable code had an explanation. A test can only
    find codes on paths it executes; this makes the bad state unrepresentable."""
    from mendel_compiler.conformance import Diagnostic

    with pytest.raises(Exception):
        Diagnostic(code="MD9999", where="x", summary="s", detail="d", fix="f")
```

Note the field is `where`, not `contract_id` — that rename lands in Task 11. **Until then use
`contract_id=` in this test and change it in Task 11.**

- [ ] **Step 7: run the whole suite**

Run: `uv run pytest -q -m "not slow"`
Expected: 441 + 5 passed, 2 deselected.

- [ ] **Step 8: commit**

```bash
git add packages/comeni-core/src/comeni_core/diagnostics.yml \
        packages/comeni-core/src/comeni_core/diagnostics.py \
        packages/mendel-compiler/src/mendel_compiler/conformance.py \
        tests/test_diagnostics_registry.py
git commit -m "feat(core): the diagnostic registry is data, and an undeclared code cannot be emitted"
```

---

## Task 2: `cli.md`'s table is generated

**Files:**
- Create: `tools/generate_diagnostics_doc.py`
- Modify: `docs/reference/cli.md` (markers around the table)
- Modify: `Makefile` (a `docs` target, added to `check`)
- Modify: `.github/workflows/nightly.yml`

**Interfaces:**
- Consumes: `comeni_core.diagnostics.REGISTRY` from Task 1.
- Produces: `tools/generate_diagnostics_doc.py --check` exiting 1 when stale.

- [ ] **Step 1: put markers in `cli.md` around the existing table**

```markdown
<!-- BEGIN GENERATED DIAGNOSTICS -->
<!-- END GENERATED DIAGNOSTICS -->
```

Delete the hand-written table between them. Leave the prose above and the `MD0100` note below.

- [ ] **Step 2: write the failing test**

```python
# append to tests/test_diagnostics_registry.py
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_the_generated_table_is_current():
    """`make check` runs this. A generated artifact that drifts from its source is a lie with
    a timestamp — the same reason `tools/generate_types.py --check` exists."""
    result = subprocess.run(
        [sys.executable, "tools/generate_diagnostics_doc.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 3: run it and watch it fail**

Run: `uv run pytest tests/test_diagnostics_registry.py::test_the_generated_table_is_current -v`
Expected: FAIL — the tool does not exist, non-zero return.

- [ ] **Step 4: write the generator, mirroring `tools/generate_types.py`**

```python
#!/usr/bin/env python
"""Render the diagnostics table in `docs/reference/cli.md` from `comeni_core/diagnostics.yml`.

`--check` is what CI runs. Same shape as `tools/generate_types.py`: compare, exit 1 with the
command that fixes it. A second convention for one job is how one of them rots.
"""

import sys
from pathlib import Path

from comeni_core.diagnostics import REGISTRY

DOC = Path(__file__).parent.parent / "docs" / "reference" / "cli.md"
BEGIN = "<!-- BEGIN GENERATED DIAGNOSTICS -->"
END = "<!-- END GENERATED DIAGNOSTICS -->"

_HEADINGS = {
    "conformance": "A contract disagrees with its module",
    "pipeline-file": "The pipeline file — a setting, an override, or the format",
}


def table() -> str:
    lines: list[str] = []
    for concern, heading in _HEADINGS.items():
        codes = [s for s in REGISTRY.values() if s.concern == concern]
        if not codes:
            continue
        lines += [f"#### {heading}", "", "| Code | Says |", "|---|---|"]
        lines += [f"| `{s.code}` | {s.says} |" for s in sorted(codes, key=lambda s: s.code)]
        lines.append("")
    return "\n".join(lines)


def rendered() -> str:
    current = DOC.read_text()
    head, _, rest = current.partition(BEGIN)
    _, _, tail = rest.partition(END)
    return f"{head}{BEGIN}\n\n{table()}\n{END}{tail}"


def main() -> int:
    generated = rendered()
    if "--check" in sys.argv:
        if DOC.read_text() != generated:
            print(
                "docs/reference/cli.md is stale — run: "
                "uv run python tools/generate_diagnostics_doc.py"
            )
            return 1
        return 0
    DOC.write_text(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: generate, then run the test**

Run: `uv run python tools/generate_diagnostics_doc.py && uv run pytest tests/test_diagnostics_registry.py -v`
Expected: PASS. `git diff docs/reference/cli.md` shows the table regenerated with the same eight
codes — **read that diff**; if a `says` moved, the copy in Task 1 was not verbatim.

- [ ] **Step 6: wire it into `check` and nightly**

In `Makefile`, extend the existing `types` target's neighbourhood:

```make
docs:           ## fail if the generated diagnostics table is stale
	uv run python tools/generate_diagnostics_doc.py --check
```

and change `check: lint test types` to `check: lint test types docs`. Add `docs` to `.PHONY`.

In `.github/workflows/nightly.yml`, add a step running `make docs` against `main`. **No Action
commits anything** — decided 2026-08-09; a bypass on a protected branch exists forever, and a
self-healing `main` means nobody ever sees the drift.

- [ ] **Step 7: run `make check`**

Run: `make check`
Expected: green.

- [ ] **Step 8: commit**

```bash
git add tools/generate_diagnostics_doc.py docs/reference/cli.md Makefile \
        .github/workflows/nightly.yml tests/test_diagnostics_registry.py
git commit -m "feat(tools): the diagnostics table is generated, and CI checks it is current"
```

---

## Task 3: a setting declares its route

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/marks.py`
- Modify: `packages/comeni-core/src/comeni_core/contract.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MD0200`, `MD0201`, `MD0204`, `MD0205`)
- Modify: `registry/contracts/nf-core/star-align.yml`, `registry/contracts/nf-core/hisat2-align.yml`
- Test: `packages/comeni-core/tests/test_contract.py`

**Interfaces:**
- Produces: `comeni_core.pipeline.Via`, `comeni_core.pipeline.ExtKey` — **defined in
  `pipeline.py`**, which Task 4 creates. To avoid a circular import, put both enums in
  `comeni_core/routes.py` and have `pipeline.py` re-export them.
- Produces: `Param(name, tier_hint, default, via: Via, key: ExtKey | None, template: NfTemplate | None)`.
- Produces: `comeni_core.marks.NfTemplate`.

- [ ] **Step 1: write the failing tests**

```python
# packages/comeni-core/tests/test_contract.py
"""A setting that reaches nothing is refused at load.

The whole declared-param surface was two entries and both were dead: `star/align` and
`hisat2/align` each declared `seq_platform`, which resolved to a `params.<node>_<name>` line
in `main.nf` that no module reads. Issue #10.
"""

import pytest
from pydantic import ValidationError

from comeni_core.contract import Param
from comeni_core.routes import ExtKey, Via


def test_a_param_without_a_route_is_refused():
    with pytest.raises(ValidationError, match="MD0200"):
        Param(name="seq_platform", tier_hint=4)


def test_ext_requires_a_key():
    with pytest.raises(ValidationError, match="MD0205"):
        Param(name="seq_platform", via=Via.EXT, template="--x {value}")


def test_when_is_not_a_legal_key():
    """A setting that skips a process would let `steps:` describe a pipeline that does not
    run — a second routing mechanism competing with resolution."""
    with pytest.raises(ValidationError):
        Param(name="off", via=Via.EXT, key="when", template="{value}")


def test_a_template_must_mention_the_value():
    """Deadness wearing a bridge: renders real flags, discards the value, and is harder to
    spot than an honest no-op."""
    with pytest.raises(ValidationError, match="MD0204"):
        Param(name="seq_platform", via=Via.EXT, key=ExtKey.ARGS, template="--flag fixed")


def test_a_template_is_illegal_on_a_route_that_takes_no_argument_string():
    with pytest.raises(ValidationError, match="MD0204"):
        Param(name="p", via=Via.DIRECTIVE, template="--cpus {value}")


def test_a_routed_param_validates():
    p = Param(name="seq_platform", tier_hint=4, via=Via.EXT, key=ExtKey.ARGS,
              template="--outSAMattrRGline ID:${meta.id} 'PL:{value}'")
    assert p.key is ExtKey.ARGS
```

- [ ] **Step 2: run and watch them fail**

Run: `uv run pytest packages/comeni-core/tests/test_contract.py -v`
Expected: FAIL — `No module named 'comeni_core.routes'`.

- [ ] **Step 3: write `routes.py`**

```python
# packages/comeni-core/src/comeni_core/routes.py
"""Where a resolved value can land in the generated Nextflow.

Three emission sites, because those are the three places the compiler writes into. An earlier
draft claimed three values were exhaustive over *Nextflow's* destinations, which is false:
`task.ext.prefix` is in 8 of the 10 vendored modules and `task.ext.when` in all 10. The `ext`
scope is a keyspace, not a destination. A claim about the emitter is checkable; a claim about
Nextflow's surface was a guess.
"""

from enum import StrEnum


class Via(StrEnum):
    EXT = "ext"              # process { withName: X { ext.<key> = … } }
    META = "meta"            # channel .map { meta + [k: v], files }
    DIRECTIVE = "directive"  # process { withName: X { cpus = 12 } }


class ExtKey(StrEnum):
    ARGS = "args"
    ARGS2 = "args2"
    ARGS3 = "args3"
    PREFIX = "prefix"
    """`ext.when` is deliberately absent. It is a boolean that skips a process, so a setting
    could switch off a step while `steps:` and `inputs:` still describe it running. Whether a
    step exists is decided by resolving the goal.

    `args2`/`args3` are here on nf-core convention with no evidence in this repository — no
    vendored module reads them. Kept because an unused value costs nothing while adding one
    later costs a `version:` bump for every archived `pipeline.yml`, and `MD0108` refuses a
    contract naming a key its module does not read."""


TEMPLATED = frozenset({ExtKey.ARGS, ExtKey.ARGS2, ExtKey.ARGS3})
"""The keys whose value composes into an argument string. `prefix` names outputs and takes one
typed value; `cpus = "--cpus 12"` is not a thing."""
```

- [ ] **Step 4: add the `NfTemplate` mark**

In `marks.py`, add `NF_TEMPLATE = "nf-template"` to the `Mark` enum, then:

```python
_VALUE_CLASS = re.compile(r"^[A-Za-z0-9_.:+-]*$")


def _nf_template(value: str) -> str:
    """A flag fragment with exactly one Mendel substitution, `{value}`.

    Two interpolation systems meet here. `{value}` is Mendel's, substituted at emit time.
    `${…}` is Groovy's, evaluated by Nextflow at run time and passed through verbatim; a
    literal dollar is written `\\$`. Only the first is our problem.
    """
    if "\n" in value:
        raise ValueError("MD0204: a template is one line")
    return value


NfTemplate = Annotated[str, Mark.NF_TEMPLATE, AfterValidator(_nf_template)]


def substitutable(value: object) -> bool:
    """Whether `{value}` may carry this.

    Refuse rather than escape — escaping-for-context is the trap root C exists to close. The
    class is deliberately narrow, on the stated assumption that almost no tool setting needs a
    space or a slash. Loosening later is backward-compatible; tightening is not, so start
    strict. See MD0201 and the spec's §5.
    """
    if isinstance(value, bool | int | float):
        return True
    return isinstance(value, str) and bool(_VALUE_CLASS.match(value))
```

- [ ] **Step 5: extend `Param`**

```python
class Param(BaseModel):
    model_config = _NO_EXTRAS

    name: PortName
    tier_hint: int | None = None
    default: ParamValue = None
    via: Via
    """Mandatory. A setting with no declared route resolved to a `params.<node>_<name>` line
    that nothing read — the resolver ran, flagged tier 4, and the pipeline behaved identically
    whatever the answer was. Requiring this makes that unrepresentable rather than merely
    detectable."""
    key: ExtKey | None = None
    template: NfTemplate | None = None

    @model_validator(mode="after")
    def _route_is_complete(self) -> "Param":
        if self.via is Via.EXT and self.key is None:
            raise ValueError(f"MD0205: {self.name} declares via: ext without a key")
        if self.via is not Via.EXT and self.key is not None:
            raise ValueError(f"MD0205: {self.name} declares a key on via: {self.via}")
        templated = self.via is Via.EXT and self.key in TEMPLATED
        if templated and (self.template is None or "{value}" not in self.template):
            raise ValueError(
                f"MD0204: {self.name} routes to ext.{self.key} but its template does not "
                "mention {value}, so the resolved value would be discarded"
            )
        if not templated and self.template is not None:
            raise ValueError(
                f"MD0204: {self.name} routes to {self.via} which takes one value, not an "
                "argument string, so a template has nothing to compose into"
            )
        return self
```

`via` has no default, so a `Param` without one fails at load — which is `MD0200`. Add a
`missing`-error message check to the test by matching on `via` as well if pydantic's message
does not carry the code.

- [ ] **Step 5b: the legal directive names, and `MD0209`**

`MD0209` cannot ship without this list, and the list is why. An unknown directive inside a
`withName` block is **silently ignored by Nextflow** — verified by experiment on 25.10.4: a config
containing `process { withName: FOO { cpuz = 4 } }` ran to exit 0 with no error and no warning.
That is the exact failure this plan exists to remove, so `via: directive` without a name check
would install it.

It lives in `mendel-compiler` as code, not in the registry as data. `Vocabulary` is strictly
per-type and a directive list is not a type; putting it in a layer would mean a fifth member
beside `contracts/`, `rules/`, `vocabularies/` and `measurements/`, which collides with root B.
And the invariant-7 analogy does not hold: vocabularies are closed because a contract using an
undeclared *biological* state must fail, while Nextflow's directive set is toolchain fact that
changes on Nextflow's release cycle. No laboratory should be able to approve `cpuz` into it.

```python
# packages/mendel-compiler/src/mendel_compiler/directives.py
"""The process directives Nextflow accepts, and the version they were read against.

An unknown directive in a `withName` block is silently ignored — `withName: FOO { cpuz = 4 }`
runs to exit 0 with no diagnostic on 25.10.4. So this list is the only thing standing between a
typo and a resource setting that does nothing.

Code rather than registry data: this is a fact about the toolchain, not about biology, and it
moves when Nextflow moves. `modulespec.py` encodes toolchain facts the same way.
"""

NEXTFLOW_VERSION = "25.10.4"
"""The version this list was read against. A newer Nextflow may accept more; adding one is a
release of this package, which is the cost of the check."""

LEGAL_DIRECTIVES: frozenset[str] = frozenset({
    # READ THESE FROM THE NEXTFLOW DOCUMENTATION FOR NEXTFLOW_VERSION BEFORE COMMITTING.
    # The starter set below is from memory and MUST be verified against
    # https://www.nextflow.io/docs/latest/process.html#directives — the same discipline as
    # reading a process name out of `main.nf` rather than out of a plan.
    "accelerator", "afterScript", "arch", "array", "beforeScript", "cache",
    "clusterOptions", "conda", "container", "containerOptions", "cpus", "debug",
    "disk", "errorStrategy", "executor", "fair", "label", "machineType",
    "maxErrors", "maxForks", "maxRetries", "maxSubmitAwait", "memory", "module",
    "penv", "pod", "publishDir", "queue", "resourceLabels", "resourceLimits",
    "scratch", "secret", "shell", "spack", "stageInMode", "stageOutMode",
    "storeDir", "tag", "time",
})
"""`ext` is deliberately absent: `via: ext` handles that scope and a setting must not reach it
twice by two routes. Deprecated directives (`echo`, `validExitStatus`) are absent too — a
diagnostic that permits what Nextflow warns about is not doing its job."""
```

Add to `Param._route_is_complete`:

```python
        if self.via is Via.DIRECTIVE and self.name not in LEGAL_DIRECTIVES:
            raise ValueError(
                f"MD0209: {self.name} is not a process directive Nextflow {NEXTFLOW_VERSION} "
                "accepts. An unknown directive in a `withName` block is silently ignored, so "
                "this would be a setting that does nothing."
            )
```

That import points from `comeni-core` into `mendel-compiler`, which is the wrong direction.
**Put `directives.py` in `comeni_core` instead** — `Param` lives there and is what validates. The
docstring's argument is unaffected: it is still code rather than registry data.

- [ ] **Step 5c: write the failing test for it**

```python
def test_an_unknown_directive_is_refused():
    """Verified by experiment: `withName: FOO { cpuz = 4 }` runs to exit 0 with no diagnostic on
    Nextflow 25.10.4. Nothing else would catch this."""
    with pytest.raises(ValidationError, match="MD0209"):
        Param(name="cpuz", via=Via.DIRECTIVE)


def test_a_real_directive_validates():
    assert Param(name="cpus", via=Via.DIRECTIVE).via is Via.DIRECTIVE


def test_ext_is_not_reachable_as_a_directive():
    """Two routes to one scope is two writers for one destination, which MD0208 forbids
    downstream. Forbid it at the source instead."""
    with pytest.raises(ValidationError, match="MD0209"):
        Param(name="ext", via=Via.DIRECTIVE)
```

- [ ] **Step 6: add the four codes to `diagnostics.yml`**

| code | `says` |
|---|---|
| `MD0200` | a setting declares no `via:`, so nothing would carry its value |
| `MD0201` | a resolved value is outside the substitutable character class |
| `MD0204` | a `template:` never mentions `{value}`, or sits on a route that takes none |
| `MD0205` | `via:`/`key:` are not a legal pair — including `key: when` |
| `MD0209` | `via: directive` names something Nextflow silently ignores |

Each with `concern: pipeline-file`, `emitted_by: compiler`, `fires_on: [build, emit, upgrade]`,
`refuses: true`, and a `fix` and `explanation`.

**`MD0201`'s text, as a literal.** Not paraphrased: this is the one diagnostic whose reader is the
only person who can tell us a boundary was drawn wrong, and a message that merely forbids loses
that information forever.

```yaml
MD0201:
  emitted_by: compiler
  concern: pipeline-file
  says: "a resolved value is outside the substitutable character class"
  fires_on: [build, emit, upgrade]
  refuses: true
  fix: |
    Use letters, digits and `_ . : + -` only, or a number, or true/false.

    If your value legitimately needs a space or a slash, that is a case we assumed did not
    exist rather than one we decided to forbid. Please report it, with the tool and the flag:
    https://github.com/comeni-project/Comeni-Labs/issues
  explanation: |
    A template substitutes {value} into a string that becomes part of a shell command line.
    Rather than escape dangerous characters, Mendel refuses them: escaping-for-context is
    where injection bugs live, and a value that cannot contain a quote cannot close one.

    The class is deliberately narrow, on the stated assumption that almost no tool setting
    needs a space or a slash. That assumption has not been tested against a real
    counterexample, which is why this message asks for one.

    Loosening the class later is backward-compatible — every file that validated still
    validates. Tightening it is not, because files already on disk would stop loading. So it
    starts strict, and the three excluded classes are not equally cheap to admit later: a
    slash is inert here and needs only a wider pattern; a space needs the substituted value
    shell-quoted at emit time, which moves every ext.args string and every golden file; and a
    quote, dollar, backtick, semicolon or newline should stay excluded, because those are the
    reason the mechanism refuses rather than escapes.
```

**`MD0202`'s report line, as a literal.** It does not refuse — `upgrade` prints it and continues,
which is why the wording has to make the two digests distinguishable at a glance:

```python
# in cli.py's drift reporting
f"MD0202  {step.module}\n"
f"  the contract has changed since this pipeline froze its values\n"
f"    frozen:   {step.digest}\n"
f"    registry: {current_digest}\n"
f"  → `mendel upgrade` to adopt it, or keep the frozen values deliberately\n"
```

`drift` and `changes` stay separate categories, because a digest moving is not the same event as
a decision moving — Plan 1.7 established that distinction and it earns its keep here.

- [ ] **Step 7: route both real params**

```yaml
# registry/contracts/nf-core/star-align.yml
params:
  - name: seq_platform
    tier_hint: 4
    via: ext
    key: args
    template: "--outSAMattrRGline ID:${meta.id} 'PL:{value}'"
```

**Read the flag out of nf-core/rnaseq before writing it** — the exact `--outSAMattrRGline`
spelling is not verified in this repository, and the standing rule is to read process names and
flags out of module source rather than out of a plan. Same for `hisat2/align`, whose flag is
`--rg-id`/`--rg`, not `--outSAMattrRGline`.

- [ ] **Step 8: run the suite**

Run: `uv run pytest -q -m "not slow" && uv run ruff check .`
Expected: green. `tests/test_spine_contracts.py` compares contracts against modules on disk, so
a wrong flag surfaces here in milliseconds.

- [ ] **Step 9: commit**

```bash
git add packages/comeni-core/src/comeni_core/routes.py \
        packages/comeni-core/src/comeni_core/marks.py \
        packages/comeni-core/src/comeni_core/contract.py \
        packages/comeni-core/src/comeni_core/diagnostics.yml \
        packages/comeni-core/tests/test_contract.py registry/contracts/nf-core/
git commit -m "feat(core): a setting declares the route that carries it, and a dead one is refused"
```

---

## Task 4: `Pipeline`, and the mapping is total

**Files:**
- Create: `packages/comeni-core/src/comeni_core/pipeline.py`
- Create: `tests/test_pipeline_totality.py`
- Modify: `tests/test_construction.py` (`Pipeline` joins `DataProfile`)

**Interfaces:**
- Consumes: `Via`, `ExtKey` from Task 3.
- Produces: `Pipeline`, `Step`, `Setting`, `Channel`, `CallArg`, `RegistryProvenance`, `Why`,
  `Pipeline.of(ir, registry, vocab, measurements) -> Pipeline`.

**The types**, with every leaf a declared shape — `test_every_payload_field_is_a_declared_shape`
walks this recursively once Task 12 makes it door 4's payload:

```python
class Why(BaseModel):
    """Tier, who settled it, which layer, and the citation — in one place. This is the
    legibility the four-file split cannot provide."""
    model_config = ConfigDict(extra="forbid")
    tier: Tier
    source: ValueSource
    reason: Line
    from_layer: LayerName | None = None
    displaced_layer: LayerName | None = None


class Setting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: PortName
    value: ParamValue
    via: Via
    key: ExtKey | None = None
    template: NfTemplate | None = None
    why: Why


class CallArg(BaseModel):
    """One positional input of the process. Mirrors `NfInput`'s three shapes, written out —
    no shorthand, because root G's rule is that a file reads one way and `call:` is where a
    second reading produces a silently miswired pipeline rather than a parse error."""
    model_config = ConfigDict(extra="forbid")
    ports: list[PortName] = Field(default_factory=list)
    literal: ParamValue = None
    empty_width: int | None = None
    why: Why | None = None


class StepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    port: PortName
    from_: EdgeRef = Field(alias="from")
    states: list[StateName] = Field(default_factory=list)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: NodeId
    module: ContractId
    digest: Digest
    container: ContainerRef | None = None
    process: NfIdentifier
    include: NfPath
    why: Why
    inputs: list[StepInput] = Field(default_factory=list)
    call: list[CallArg] = Field(default_factory=list)
    settings: list[Setting] = Field(default_factory=list)


class Channel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type_id: TypeId
    params: list[PortName] = Field(default_factory=list)
    expression: GroovyExpression
    meta: list[MetaEntry] = Field(default_factory=list)


class RegistryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layers: list[LockedLayer] = Field(default_factory=list)
    displaced: list[Displacement] = Field(default_factory=list)
    unverified: list[ContractId] = Field(default_factory=list)


class Pipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    goal: Goal
    registry: RegistryProvenance = Field(default_factory=RegistryProvenance)
    steps: list[Step] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    emitted: Emitted | None = None
    gate: Gate | None = None
```

**`Pipeline` must not hold a `Registry`, `ModuleContract` or `Vocabulary`.** `registry.py`
carries a mapping and says it is legal *because* `Registry` is not payload-reachable —
"a mapping is legal here in a way it is not on the IR". `Pipeline.of()` takes a registry as an
argument; `Pipeline` must not have a field for one, or that premise silently stops holding.

- [ ] **Step 1: write the failing totality test**

```python
# tests/test_pipeline_totality.py
"""Every field of every type `Pipeline` replaces has a declared home in it.

Root D's finding applied to consolidation rather than to diffing: `diff_ir` enumerated the
fields it knew about, so every field added to the IR was a silent blind spot, and Plan 1.8
added four. Three drafts of the spec's own schema dropped five fields between them —
`LockedContract.container` among them, whose docstring says the `sealed` profile's
digests-required rule depends on it. Reviewing a three-types-into-one mapping by eye already
failed five times.
"""

from comeni_core import (
    DataProfile, Displacement, Emitted, EmittedFile, Goal, IRNode, Lockfile,
    LockedContract, LockedLayer, ParamDecision, PipelineIR, ProducerDecision,
    ResolvedValue, SourceDecision,
)
from comeni_core.pipeline import Pipeline
from tests._walk import reachable

REPLACED = [
    PipelineIR, IRNode, ResolvedValue, ParamDecision, ProducerDecision, SourceDecision,
    Lockfile, LockedContract, LockedLayer, Displacement, Emitted, EmittedFile, Goal,
    DataProfile,
]

NOT_CARRIED = {
    # field -> why. Every entry is a decision, not an oversight.
    "Lockfile.version": "the lockfile's own format version; `Pipeline.version` replaces it",
}


def _homes() -> set[str]:
    """Every field name reachable from `Pipeline`, at any depth."""
    return {
        name
        for model in reachable(Pipeline)
        for name in model.model_fields
    }


def test_every_replaced_field_has_a_home():
    homes = _homes()
    missing = [
        f"{m.__name__}.{name}"
        for m in REPLACED
        for name in m.model_fields
        if name not in homes and f"{m.__name__}.{name}" not in NOT_CARRIED
    ]
    assert missing == [], "these fields have nowhere to go in Pipeline:\n" + "\n".join(missing)


def test_no_field_of_pipeline_is_a_frozenset():
    """`digest_of` hashes `model_dump_json()`, and a set has no stable order. `digest.py` says
    it outright: anything new that serialises a set silently breaks digests and every lockfile
    made with them. `Pipeline` is what publish ships."""
    offenders = [
        f"{model.__name__}.{name}"
        for model in reachable(Pipeline)
        for name, field in model.model_fields.items()
        if "frozenset" in str(field.annotation)
    ]
    assert offenders == []
```

**The walkers are extracted, not rewritten.** `tests/test_egress.py` already contains
`_nested_models` and the breadth-first expansion inside `_payload_types`, and they exist because
the first version of that guard *"never looked inside `RepairRequest.ir`, and a payload serialised
a patient path and an SSN while this file reported green"*. A second copy that drifts from it
would reintroduce exactly that. So move both into `tests/_walk.py` and import them in both places:

```python
# tests/_walk.py
"""Annotation walkers shared by the egress guard and the totality test.

Extracted rather than duplicated. `_nested_models` is why `tests/test_egress.py` can see inside
`RepairRequest.ir` at all — its first version could not, and a payload serialised a patient path
while the guard reported green. Two copies of that logic, drifting, is the same defect waiting.
"""

import typing

from pydantic import BaseModel


def nested_models(annotation: object) -> list[type[BaseModel]]:
    """Every BaseModel mentioned anywhere in an annotation, however deeply wrapped."""
    found = []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.append(annotation)
    for arg in typing.get_args(annotation):
        found += nested_models(arg)
    return found


def reachable(*roots: type[BaseModel]) -> set[type[BaseModel]]:
    """Transitive closure over model fields, breadth-first.

    Same expansion `_payload_types` does. Exempting nested models would be the hole.
    """
    seen: set[type[BaseModel]] = set()
    queue = list(roots)
    while queue:
        model = queue.pop()
        if model in seen:
            continue
        seen.add(model)
        for annotation in typing.get_type_hints(model, include_extras=True).values():
            queue += [n for n in nested_models(annotation) if n not in seen]
    return seen
```

Then in `tests/test_egress.py`, delete the local `_nested_models` and the inline BFS, and import:

```python
from tests._walk import nested_models as _nested_models, reachable
```

`_payload_types()` becomes `reachable(*roots)`. **Run the egress guard immediately after this
extraction and before touching anything else** — it must still pass with the same count. An
extraction that changes what a guard can see is a weakened guard wearing a refactor's clothes.

`tests/` needs an `__init__.py` for `from tests._walk import …` to resolve, or use a
`conftest.py`-level `sys.path` insert if the repo's pytest layout prefers that. Check how
`tests/test_counts.py` imports its helpers and follow the same pattern.

- [ ] **Step 2: run and watch it fail**

Run: `uv run pytest tests/test_pipeline_totality.py -v`
Expected: FAIL — `No module named 'comeni_core.pipeline'`.

- [ ] **Step 3: write `pipeline.py` with the types above, and `Pipeline.of()` raising `NotImplementedError`**

- [ ] **Step 4: run the totality test and let it tell you what is missing**

Run: `uv run pytest tests/test_pipeline_totality.py::test_every_replaced_field_has_a_home -v`
Expected: FAIL, listing the fields with no home. **Add a field or a `NOT_CARRIED` entry with a
reason for each.** This is the step that catches what the eye missed — do not shortcut it by
adding a blanket allowlist.

- [ ] **Step 5: implement `Pipeline.of()`**

Materialise from the IR plus the three declared-data sources, then **assert the productive
rule**: a field is embedded only if `emit` reads it, or it is provenance no later registry
lookup recovers. No whole contracts, no `provenance:` blocks, no `meta.yml` prose.

- [ ] **Step 6: add `Pipeline` to the construction guard**

In `tests/test_construction.py`, extend the AST scan so `Pipeline(` outside
`comeni_core/pipeline.py` is an offence, with `Pipeline.of` the one allowed constructor. Same
mechanism that already stops anything but `MeasurementRegistry.profile()` building a
`DataProfile`. **The scan walks `packages/*/src` only, so tests may still hand-build a
pathological `Pipeline`** — which `test_a11_the_emitter_never_compares_two_resolved_values`
needs.

- [ ] **Step 7: run the suite**

Run: `uv run pytest -q -m "not slow" && uv run ruff check .`

- [ ] **Step 8: commit**

```bash
git add packages/comeni-core/src/comeni_core/pipeline.py \
        tests/test_pipeline_totality.py tests/test_construction.py
git commit -m "feat(core): Pipeline materialises everything the emitter reads, totally"
```

---

## Task 5: `emit` reads one file

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/templates/main.nf.j2`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (call through `Pipeline.of`)
- Modify: `tests/golden/spine/main.nf`, `tests/golden/spine/nextflow.config`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MD0208`)

**Interfaces:**
- Consumes: `Pipeline` from Task 4.
- Produces: `emit(pipeline: Pipeline) -> str`, `emit_config(pipeline: Pipeline) -> str`.

- [ ] **Step 1: write the failing tests**

```python
# packages/mendel-compiler/tests/test_emit.py — additions
def test_a_routed_setting_composes_into_ext_args():
    config = emit_config(_pipeline())
    assert '--outSAMattrRGline' in config
    assert 'withName: STAR_ALIGN' in config


def test_ext_args_is_double_quoted_so_groovy_interpolates():
    """`${meta.id}` must interpolate, and a single-quoted Groovy string does not."""
    config = emit_config(_pipeline())
    line = next(l for l in config.splitlines() if "STAR_ALIGN" in l)
    assert 'ext.args = "' in line, line


def test_two_settings_on_one_key_are_sorted_by_name():
    """With ONE setting the sort is unobservable, so a test with one cannot see a sort bug.
    This is `frozenset`-has-no-stable-order in a new place."""
    config = emit_config(_pipeline_with_two_args_settings())
    line = next(l for l in config.splitlines() if "STAR_ALIGN" in l)
    assert line.index("--alpha") < line.index("--zulu"), line


def test_no_dead_params_line_survives():
    """`params.star_align_seq_platform` was read by nothing. Issue #10."""
    assert "star_align_seq_platform" not in emit(_pipeline())
```

- [ ] **Step 2: run and watch them fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py -v`
Expected: FAIL — `emit_config()` takes three arguments.

- [ ] **Step 3: narrow both signatures and compose templates**

`_process_scope` becomes: for each step, group its `via: ext` settings by `key`, render each
template with `{value}` substituted, join name-sorted, prepend the contract's static `ext_args`
for `key: args`. Emit `ext.<key> = "…"` double-quoted. Refuse two writers for one destination
with `MD0208`.

Delete the `params` loop from `main.nf.j2` — those lines are the deadness this plan removes.

- [ ] **Step 4: substitute `{value}` safely**

```python
def _substitute(template: str, value: object) -> str:
    if not substitutable(value):
        raise ValueError(
            f"MD0201: {value!r} is outside the substitutable class. Use letters, digits and "
            "_ . : + - only, or a number, or true/false. If your value legitimately needs a "
            "space or a slash, that is a case we assumed did not exist — please report it."
        )
    return template.replace("{value}", str(value).lower() if isinstance(value, bool) else str(value))
```

- [ ] **Step 5: regenerate both golden files and read the diffs**

Run: `uv run pytest packages/mendel-compiler/tests/test_emit.py -v`, then update the goldens
from the actual output. **Read both diffs before committing** — that is what caught the Jinja
`{%- endfor %}` collision. Expect in `main.nf`: the `params.*` comment/assignment pair gone.
In `nextflow.config`: `ext.args` single→double quotes, and the `--outSAMattrRGline` fragment.

- [ ] **Step 6: `make verify`, not `make check`**

Run: `make verify`
Expected: green, including `tests/test_counts.py`. This task changes `emit.py`, and
`test_counts.py` is the only check that a setting reaches a tool.

- [ ] **Step 7: commit**

```bash
git add packages/mendel-compiler/ tests/golden/ \
        packages/comeni-core/src/comeni_core/diagnostics.yml
git commit -m "feat(compiler): emit reads one Pipeline, and a resolved setting reaches the tool"
```

---

## Task 6: `pipeline.yml` is the artifact

> **Done, 2026-08-09, with five corrections. Read these before Task 10 — three of them
> move work into it.**
>
> **1. `MD0213` does not refuse in `emit`; it refuses in the verbs that treat the generated
> files as evidence.** The step-1 test below asserted that editing `pipeline.yml` and running
> `mendel emit` is refused. That is backwards, and it makes the design impossible: `emit` is
> the verb that *cures* staleness, so refusing there means the file a reader is told to edit
> can never be edited. `emit` reports `MD0213` and regenerates; `publish` and a gated run are
> where it must refuse, and **that half lands in Task 10**, which is where those verbs get
> their new front door. `MD0214` does refuse in `emit`, because regenerating would destroy a
> hand edit — and a **deleted** file is rewritten rather than refused, which is the escape
> hatch its `fix:` names.
>
> **2. `pipeline.bundle.json` survives Task 6 and retires in Task 10.** `mendel.lock.yml` and
> `pipeline.ir.json` are gone as planned. The bundle is `upgrade --bundle`'s only input and
> nothing else reads it; deleting it here would leave `upgrade` broken across Tasks 7–9, and
> re-pointing `upgrade` needs `diff_ir` and `drift_against` to work from a `Pipeline` — which
> is Task 10's subject, not a side effect of this one.
>
> **3. `MD0212` was already taken.** Task 4 shipped it on `StepInput`'s exactly-one-origin
> rule. The spec's table assigns it to duplicates and the spec is the authority, so duplicates
> keep `MD0212` and the input rule became **`MD0215`** — renumbered while nothing had published
> it, which is the only moment renumbering is allowed.
>
> **4. `Pipeline.of` wrote `goal: {have: [], want: []}` into every file, and everything
> passed.** It defaulted the goal to `Goal(profile=ir.profile)`, which type-checks,
> round-trips, and satisfies the totality test — that test asks whether a field has a *home*,
> and it did. `goal` is now keyword-only with **no default**. A field present and empty is
> worse than a field absent in a file whose whole claim is that it records what was asked for,
> and Task 10's `upgrade` would have re-resolved an empty goal.
>
> **5. `_settings` silently drops a binding whose contract declares no such param.** Found by
> a guard of this task's own that passed for the wrong reason. It is the orphan case one level
> below Task 9's, recorded at the site, and **left to Task 9** rather than given a code here
> that would collide with `MD0203`.
>
> `make verify` green: 506 fast, 2 slow, 15 guards.

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (`from_digest`, serialisation)
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml`
  (`MD0206`, `MD0207`, `MD0210`, `MD0211`, `MD0212`, `MD0213`, `MD0214`)
- Test: `tests/test_pipeline_file.py` (create)

- [x] **Step 1: write the failing tests**

```python
def test_build_writes_pipeline_yml_and_not_the_three_it_replaces(tmp_path):
    _build(tmp_path)
    assert (tmp_path / "pipeline.yml").exists()
    assert not (tmp_path / "pipeline.ir.json").exists()
    assert not (tmp_path / "mendel.lock.yml").exists()


def test_build_emits_from_the_round_tripped_file(tmp_path, monkeypatch):
    """`ResolvedValue._drop_computed` exists because the IR did not round-trip at all, and —
    in that field's own words — "nothing noticed, because nothing read an IR back until now".
    This makes the round trip load-bearing on every build."""
    _build(tmp_path)
    reparsed = Pipeline.model_validate(yaml.safe_load((tmp_path / "pipeline.yml").read_text()))
    assert emit(reparsed) == (tmp_path / "main.nf").read_text()


def test_editing_pipeline_yml_without_re_emitting_is_refused(tmp_path):
    """Nextflow runs main.nf, not pipeline.yml. Edit the file you were told to edit, forget
    `mendel emit`, and the pipeline that runs is not the pipeline that is documented — with
    every file digest matching, because the bytes on disk are what was written."""
    _build(tmp_path)
    p = tmp_path / "pipeline.yml"
    p.write_text(p.read_text().replace("illumina", "nanopore"))
    code, err = _run(["emit", str(p), "--out", str(tmp_path)])
    assert code != 0 and "MD0213" in err


def test_hand_editing_main_nf_is_refused_and_the_fix_names_the_other_file(tmp_path):
    _build(tmp_path)
    (tmp_path / "main.nf").write_text((tmp_path / "main.nf").read_text() + "\n// touched\n")
    code, err = _run(["emit", str(tmp_path / "pipeline.yml"), "--out", str(tmp_path)])
    assert code != 0 and "MD0214" in err
    assert "pipeline.yml" in err, "the fix must say where to make the change"


def test_emit_refuses_when_modules_are_absent(tmp_path):
    _build(tmp_path)
    shutil.rmtree(tmp_path / "modules")
    code, err = _run(["emit", str(tmp_path / "pipeline.yml"), "--out", str(tmp_path)])
    assert code != 0 and "MD0210" in err


def test_a_newer_version_is_refused(tmp_path):
    _build(tmp_path)
    p = tmp_path / "pipeline.yml"
    p.write_text(p.read_text().replace("version: 1", "version: 2"))
    code, err = _run(["emit", str(p), "--out", str(tmp_path)])
    assert code != 0 and "MD0207" in err
```

- [x] **Step 2: run and watch them fail**

- [x] **Step 3: implement `from_digest`**

Digest the model **with `emitted:` excluded** — otherwise it would contain its own digest.
Same exclusion `ResolvedValue._drop_computed` makes for `review_level`, and for the same
reason: a derived field inside the thing it describes does not round-trip.

- [x] **Step 4: write `pipeline.yml` in `_build`, delete the other two writes**

Replace `cli.py`'s `(args.out / "pipeline.ir.json").write_text(...)` with a `pipeline.yml`
write, and delete the `pipeline.bundle.json` and `mendel.lock.yml` writes from `_publish`.
Emit from the reparsed file, not the in-memory object.

- [x] **Step 5: add the seven codes to `diagnostics.yml`**

| code | `says` |
|---|---|
| `MD0206` | the file `build` wrote does not parse back to the same object |
| `MD0207` | `version:` is newer than this Mendel understands |
| `MD0210` | `modules/` is absent, so the emitted `include` paths point at nothing |
| `MD0211` | `channels[].params` disagrees with what `expression` references |
| `MD0212` | two settings on one step share a name, or two steps share an `id` |
| `MD0213` | `pipeline.yml` changed since the Nextflow was generated from it |
| `MD0214` | `main.nf` or `nextflow.config` was hand-edited since it was generated |

- [x] **Step 6: `make verify`**

- [x] **Step 7: commit**

```bash
git add packages/ tests/test_pipeline_file.py
git commit -m "feat(compiler): pipeline.yml is the artifact, and the run cannot diverge from it"
```

---

## Task 7: the counts test proves a setting reaches a tool

> **Done, 2026-08-09.** One correction: `test_featurecounts_declares_no_parameters` asserted
> `params == []`, which is a stronger claim than its own argument supports — the argument is
> about *strandedness*, which the module already translates from `meta`. It blocked exactly
> what that argument needs, so it now asserts what was ever true: no strandedness param, and
> every param carries a route.
>
> **Watched failing by reverting the route rather than the assertion.** With `params: []` back,
> the run emits `featureCounts \` with an empty `${args}`, and the test fails
> naming the whole command line. `uv run pytest -m slow`: 3 passed, ~40s.

**Files:**
- Modify: `tests/test_counts.py`
- Modify: `registry/contracts/nf-core/subread-featurecounts.yml`

`MD0204` catches a template that ignores `{value}`. **Nothing catches a template whose flag is
wrong**, because the flag goes to the tool and not to the module — the same limit that makes
`-stub-run` blind to a hollow input. Only `--gate test` sees it.

- [x] **Step 1: add one real setting whose effect is visible in output**

`featurecounts` gains a `min_mqs` param routed `via: ext`, `key: args`, template
`-Q {value}`, default `0`. Read `main.nf` first to confirm `-Q` is accepted.

- [x] **Step 2: write the failing assertion**

```python
@pytest.mark.slow
def test_a_resolved_setting_reaches_the_tool(run):
    """The only check that a value Mendel resolved changed what a tool did. Without this the
    routing mechanism is verified only by unit tests of its own machinery."""
    scripts = _command_lines(run, "SUBREAD_FEATURECOUNTS")
    assert scripts, "featureCounts never ran"
    assert "-Q 0" in scripts[0], scripts[0]
```

- [x] **Step 3: run it**

Run: `uv run pytest -m slow -v`
Expected: PASS. If `-Q` is absent, the composition in Task 5 is not reaching the module.

- [x] **Step 4: commit**

```bash
git add tests/test_counts.py registry/contracts/nf-core/subread-featurecounts.yml
git commit -m "test(counts): a resolved setting reaches the tool, on real data"
```

---

## Task 8: an override is a different act from a goal pin

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/tiers.py` (`ValueSource.HUMAN`)
- Modify: `packages/comeni-core/src/comeni_core/ir.py` (`overrides()`, `needs_review()`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `tests/test_audit_regressions.py` (append)

`ValueSource`'s docstring argues that a goal-pinned param is legitimately tier 1 — *"the user
has legitimately removed the ambiguity"*. **That stays.** Editing `pipeline.yml` is a different
act: resolution faced the ambiguity, flagged it tier 4, and a human answered it in the artifact.

- [ ] **Step 1: write the failing tests**

```python
def test_an_override_keeps_the_tier_it_displaced():
    """Collapsing it to tier 1 would erase that the pipeline contains a question someone had
    to answer, and needs_review() would go quiet on a pipeline more in need of review."""
    value = _resolved_with_override("seq_platform", "illumina", displaced=Tier.AMBIGUOUS)
    assert value.tier is Tier.AMBIGUOUS
    assert value.source is ValueSource.HUMAN


def test_a_goal_pin_is_still_tier_one():
    """Regression guard for the split: ValueSource.GOAL keeps its meaning."""
    ir = _resolve(_goal_pinning("seq_platform", "illumina"))
    assert _binding(ir, "seq_platform").tier is Tier.STRUCTURAL


def test_an_answered_setting_leaves_needs_review_and_appears_in_overrides():
    """Otherwise the count never reaches zero and the CLI says REVIEW forever on a question
    already answered. `lockfile.py` makes this argument about a different list: a lockfile
    that cries wolf gets ignored."""
    ir = _ir_with_override("star_align.seq_platform")
    assert "star_align.seq_platform" not in ir.needs_review()
    assert "star_align.seq_platform" in ir.overrides()
```

- [ ] **Step 2: run, watch fail, implement, run again**

- [ ] **Step 3: `make verify`** — this touches `resolve.py`.

- [ ] **Step 4: commit**

```bash
git commit -am "feat(resolver): an override answers an ambiguity without abolishing it"
```

---

## Task 9: replay tells stale from orphaned

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/replay.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MD0203`)
- Test: `packages/mendel-resolver/tests/test_replay.py`

`_chosen()` and `_still_applies()` **survive unchanged**. `_still_applies` returning `False` is
a documented deliberate re-ask: *"replaying would assert a decision between options that no
longer exist — worse than asking again, because it would look decided."* What is wrong is that
it vanishes into a `fresh` count with no statement that an override was discarded.

- [ ] **Step 1: write the failing tests**

```python
def test_a_stale_override_is_reported_and_re_asked():
    """The candidate set moved. Re-asking is right; doing it silently is not."""
    r = ReplayingResolver(records=[_record(candidates=["a", "b"], chosen="a", override="a")])
    r.resolve(_ambiguity(candidates=["c", "d"]))
    assert r.stale == ["star_align.seq_platform"]
    assert r.replayed == []


def test_an_orphaned_override_refuses():
    """resolve() is never called for a step that is gone, so no resolver hook can see it.
    Needs a post-resolution sweep."""
    orphans = orphaned_overrides(previous=_pipeline_with_override("hisat2_align.seq_platform"),
                                 fresh=_pipeline_without("hisat2_align"))
    assert orphans == ["hisat2_align.seq_platform"]


def test_replay_emits_the_recorded_reason_verbatim():
    """`reason` is emitted as the comment above the parameter in main.nf, so prefixing it makes
    an upgraded pipeline differ from the published one by exactly that string — federation
    §4.1 requires byte-identical Nextflow."""
    r = ReplayingResolver(records=[_record(reason="rule matched: doi:10.1093/…")])
    assert r.resolve(_matching_ambiguity()).reason == "rule matched: doi:10.1093/…"
```

- [ ] **Step 2: run, watch fail, implement, run again**

- [ ] **Step 3: commit**

```bash
git commit -am "feat(resolver): a discarded override is reported, and an orphaned one refuses"
```

---

## Task 10: four verbs

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Modify: `packages/comeni-core/src/comeni_core/diagnostics.yml` (`MD0202`)
- Test: `tests/test_upgrade.py`

```bash
mendel build --goal g.yml --registry registry/ --out build/
mendel emit  build/pipeline.yml --out build/                   # no registry, no network
mendel upgrade build/pipeline.yml --registry registry/ --out next/
mendel upgrade build/pipeline.yml --registry registry/ --dry-run   # = verify
mendel publish build/pipeline.yml
```

`verify` is `upgrade --dry-run`, not a separate verb — a digest-only compare answers a strictly
weaker question, and two comparisons of "is this still what it says it is" is root D's finding
waiting to happen.

- [ ] **Step 1: write the failing tests**

```python
def test_emit_needs_no_registry_and_no_network(tmp_path):
    _build(tmp_path)
    code, _ = _run(["emit", str(tmp_path / "pipeline.yml"), "--out", str(tmp_path)])
    assert code == 0


def test_upgrade_refuses_to_write_over_the_file_it_read(tmp_path):
    """Already asserted of a bundle. With one artifact the natural implementation updates it in
    place, destroying the only record of what you had: the replayed overrides, the previous
    digests, the gate evidence."""
    _build(tmp_path)
    code, err = _run(["upgrade", str(tmp_path / "pipeline.yml"),
                      "--registry", "registry", "--out", str(tmp_path)])
    assert code != 0


def test_dry_run_writes_nothing_and_reports_five_categories(tmp_path):
    _build(tmp_path)
    before = _snapshot(tmp_path)
    code, err = _run(["upgrade", str(tmp_path / "pipeline.yml"),
                      "--registry", "registry", "--dry-run"])
    assert code == 0 and _snapshot(tmp_path) == before
    for word in ("drift", "changes", "replayed", "stale", "orphaned"):
        assert word in err.lower()
```

- [ ] **Step 2: run, watch fail, implement, run again**

- [ ] **Step 3: `make verify`** — this touches `cli.py`.

- [ ] **Step 4: commit**

```bash
git commit -am "feat(cli): emit, upgrade --out, and verify as upgrade --dry-run"
```

---

## Task 11: `Pipeline` is door 4's payload

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/egress.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/conformance.py` (`where`, `MD0108`)
- Modify: `tests/test_egress.py`, `tests/test_publish.py`
- Modify: eight docstrings citing `PublishBundle`

**Retiring `PublishBundle` is not one line.** The name appears in eight docstrings across
`marks.py`, `ir.py`, `goal.py`, `registry.py`, `gates.py` and `mendel_resolver/goal.py`, and in
every case it is load-bearing rationale — why `Goal` lives where it does, why `RequiredStates`
is a record, why `comeni-core` owns `Gate`, why a mapping is legal on `Registry`. **Rewrite them
to name `Pipeline`.** A rationale citing a deleted type reads as authoritative and cannot be
checked.

- [ ] **Step 1: write the failing tests**

```python
def test_publication_carries_a_pipeline():
    assert egress.DOORS["publication"] is Pipeline


def test_the_free_text_count_is_unchanged():
    """Six fields, not two. `FREE_TEXT_FIELDS` in tests/test_egress.py names them all, and
    1.9's A16 split took it from four to six by a refactor rather than by a new field crossing
    the boundary — which is exactly what that literal list exists to make someone notice.

    `Pipeline` becoming the payload must not add a seventh. `Why.reason` is `Line`, which is
    `FREE_TEXT` with a single-line validator, so it reaches this set through the same door the
    four existing `reason` fields do — expect the tuple, not a new name.
    """
    assert FREE_TEXT_FIELDS == {
        ("PromptRequest", "prompt"),
        ("GateFailure", "tool_message"),
        ("ResolvedValue", "reason"),
        ("ParamDecision", "reason"),
        ("ProducerDecision", "reason"),
        ("SourceDecision", "reason"),
        ("Why", "reason"),
    }, "a seventh free-text field arrived — is it declared, or did it ride along?"


def test_pipeline_holds_no_registry():
    """`registry.py` carries a mapping and says it is legal because Registry is not
    payload-reachable. Materialisation must copy values, never hold a Registry."""
    names = [str(f.annotation) for f in Pipeline.model_fields.values()]
    assert not any("Registry" in n or "ModuleContract" in n or "Vocabulary" in n for n in names)


def test_via_ext_args_on_a_module_that_ignores_it_is_refused():
    """MD0108. `modulespec.py` already parses reads_ext_args as "task.ext.args" in source, so
    a setting claiming that route for a module that ignores it is a checkable lie."""
    diags = check(_registry_with_args_route_on("nf-core/star/genomegenerate@1.11.0"),
                  Path("vendor/modules"))
    assert any(d.code == "MD0108" for d in diags)
```

- [ ] **Step 2: rename `contract_id` → `where`**

Not `subject`: `marks.py` declares `Subject` and `DecisionRecord.subject` uses it for *the thing
being decided*. A diagnostic's location is a different kind pointing at a different sort of
thing, and reusing one mark for two is what root C exists to stop. `where` carries a document
path — `steps[<id>].settings[<name>]`, `channels[<type_id>]`, `decisions[<key>]`.

- [ ] **Step 3: run, watch fail, implement, run again**

- [ ] **Step 4: `make verify`**

- [ ] **Step 5: commit**

```bash
git commit -am "refactor(core): Pipeline is the publication payload, and PublishBundle retires"
```

---

## Task 12: the documentation, and the `make verify` list

**Files:**
- Create: `docs/reference/pipeline-schema.md`
- Modify: `docs/reference/cli.md` (regenerate; correct `MD0100`'s `pipeline.ir.json` reference)
- Modify: `docs/reference/goal-schema.md` (`goal:` is inert to `emit`)
- Modify: `ARCHITECTURE.md`, `docs/README.md`, `CLAUDE.md`, `CHANGELOG.md`

- [ ] **Step 1: write `docs/reference/pipeline-schema.md`**

Every section of `pipeline.yml`, for a stranger. It is now the file a reader is most likely to
open. Include the comment that `goal:` takes effect on `upgrade`, not on `emit`.

- [ ] **Step 2: regenerate `cli.md` and fix `MD0100`'s row**

Run: `uv run python tools/generate_diagnostics_doc.py`
`MD0100`'s prose says the contract is *"recorded in `pipeline.ir.json` as `unverified`"*. That
file no longer exists; the fact moves to `registry.unverified` in `pipeline.yml`.

- [ ] **Step 3: correct `CLAUDE.md`'s invariant 14**

It says *"exactly two fields across the whole surface may hold free text"*. There are six, and
1.9's A16 split is why — `reason` on `ResolvedValue` and on each of the three decision variants.
The invariant's *argument* is unchanged and still right; only the count is wrong. Say six, name
them, and note that the number is held literally in `tests/test_egress.py` so widening it means
editing a file that says these are all the ways data leaves.

- [ ] **Step 4: add `emit.py` to CLAUDE.md's `make verify` list**

The list names the files whose breakage `make check` cannot see. `tests/test_counts.py` is the
only check that a setting reaches a tool, and rewriting `emit()`'s signature and its `ext.args`
composition is precisely a change `make check` waves through.

- [ ] **Step 5: update `ARCHITECTURE.md`'s settings surface**

The four-route description is superseded. One artifact, three emission sites, `via:` mandatory.

- [ ] **Step 6: `make verify` and `make static`**

- [ ] **Step 7: commit**

```bash
git add docs/ ARCHITECTURE.md CLAUDE.md CHANGELOG.md
git commit -m "docs: pipeline.yml is the artifact a reader opens"
```

---

## Self-review of this plan

**Spec coverage.** §1 → Tasks 4, 6. §2 → Tasks 4, 5. §3 → Tasks 6, 10. §4 → Task 3.
§5 → Tasks 3, 5. §6 → Task 8. §7 → Task 9. §8 → Task 4. §9 → Tasks 1, 11.
§10 → Tasks 1, 2. §11 → no task, and correctly so: it states that a measurement without a
`meta_key` routes nothing *and must not be flagged*, which is a constraint on Task 3's
`MD0200` rather than work of its own. Verification table → distributed. Blast radius → all tasks.

**Three gaps closed on 2026-08-09, before execution.** They are recorded because each was found
by reading the plan against the code rather than by executing it.

- **The annotation walkers are extracted, not rewritten.** Task 4 originally said to write
  `_nested_models` and `_reachable` "in the same shape as" `tests/test_egress.py`'s. That is the
  instruction that produces a second, subtly different walker — and that walker's first version
  could not see inside `RepairRequest.ir`, so a payload serialised a patient path while the guard
  reported green. Both now move to `tests/_walk.py` and both callers import them, with the egress
  guard re-run immediately after the extraction and before anything else.
- **The directive list is written, and `MD0209` ships with it** — Task 3 Steps 5b and 5c, in
  `comeni_core/directives.py` with `NEXTFLOW_VERSION` recorded beside it. The starter set is
  marked as needing verification against the Nextflow docs before commit, which is the same
  discipline as reading a process name out of `main.nf`.
- **`MD0201`'s `fix`/`explanation` and `MD0202`'s report line are literals** in Task 3 Step 6 and
  Task 10. `MD0201`'s especially: its reader is the only person who can tell us the character
  class was drawn wrong, and a message that merely forbids loses that.

**One error the fixing found.** The Global Constraints said *"exactly two fields may hold free
text"*, quoting `CLAUDE.md`'s invariant 14. `tests/test_egress.py`'s `FREE_TEXT_FIELDS` holds
**six**, and its own comment explains why: 1.9's A16 split `DecisionRecord` into three, so four
`reason` entries became six *"by a refactor rather than by a new field crossing the boundary —
which is exactly the sort of change this literal list exists to make someone notice"*. The
constraint and Task 11's test are corrected, and **Task 12 corrects `CLAUDE.md`**.

**Type consistency.** `Via`/`ExtKey` live in `routes.py` (Task 3) and are re-exported from
`pipeline.py` (Task 4) — the circular import is real and this is how it is avoided.
`Diagnostic.where` is `contract_id` until Task 11; Task 1's test says so explicitly.
`emit(pipeline)` from Task 5 is what Task 6 round-trips against.
