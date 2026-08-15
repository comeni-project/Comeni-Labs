"""The diagnostic registry, loaded from data.

One source, two consumers. `Diagnostic` validates its `code` against this, so an undeclared
code cannot be constructed; and `tools/generate_diagnostics_doc.py` renders
`docs/reference/diagnostics.md` from it, so the public page cannot drift from the codes it
lists.

Both of those were previously conventions. `EXPLANATIONS` was a Python dict beside a
hand-maintained markdown table, and a code could exist in either one alone. The test that would
have caught it — every emittable code has an explanation — can only find codes on paths it
executes; validating at construction makes the state unrepresentable instead.

**Not registry data.** A diagnostic is a fact about this compiler, not about biology: it ships
and versions with the code that raises it, and no laboratory should be able to add one by
approving a data change. `Vocabulary` is per-type and could not hold this anyway. It lives in
`comeni-core` rather than `mendel-compiler` because the forge and the API will emit codes too,
and one registry that every `explain` reads beats one per package.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from comeni_core import yaml_strict
from comeni_core.spell.marks import Line, Text

_REGISTRY_FILE = Path(__file__).with_name("diagnostics.yml")


class UnknownDiagnosticError(KeyError):
    """A code nothing declares.

    Raised rather than returned: emitting an undeclared code is a programming error in this
    repository, not a mistake a user made. `explain` is the one caller that answers rather than
    raises, because there a bad code is exactly a user's typo.
    """


class EmittedBy(StrEnum):
    """Which subsystem raises it. The prefix carries this too, but the prefix is one letter
    pair for a whole product and this is what the generated document groups by."""

    COMPILER = "compiler"
    RESOLVER = "resolver"
    FORGE = "forge"
    API = "api"


class DiagnosticSpec(BaseModel):
    """What a code *is*, as distinct from what one occurrence of it says.

    `summary` and `detail` stay at the check site, because they interpolate the actual
    mismatch — this contract, this declared value against that module's. Identity and standing
    advice are data, and that split is also what keeps templating out of this file: nothing
    here is interpolated.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    emitted_by: EmittedBy
    concern: Line
    says: Line
    """One line. It is rendered into a markdown table row, where a newline breaks the table
    silently rather than loudly."""
    fires_on: list[str]
    refuses: bool
    fix: Text
    explanation: Text


def _load() -> dict[str, DiagnosticSpec]:
    """Read the registry strictly.

    Through `yaml_strict` rather than `yaml.safe_load`, which keeps the **last** of two
    duplicate keys silently (A31). A `diagnostics.yml` declaring `MD0104` twice would load one
    and lose one, and the loss is the sort a reviewer reading the file cannot see. Every loader
    in the pure packages goes through there, so "which files are read strictly" has one answer.
    """
    raw = yaml_strict.load(_REGISTRY_FILE)
    return {code: DiagnosticSpec(code=code, **body) for code, body in sorted(raw.items())}


REGISTRY: dict[str, DiagnosticSpec] = _load()


def spec_for(code: str) -> DiagnosticSpec:
    if code not in REGISTRY:
        raise UnknownDiagnosticError(
            f"{code} is not a declared diagnostic. Declare it in comeni_core/diagnostics.yml. "
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return REGISTRY[code]


def explain(code: str) -> str:
    """Long-form, after `rustc --explain`.

    Answers rather than raising on an unknown code: this is the one entry point a person types
    at a shell, and `MD0104` was `M0104` until 2026-08-07, so the wrong spelling is a thing to
    be helpful about.
    """
    if code not in REGISTRY:
        return (
            f"{code} is not a diagnostic this version emits.\n"
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return f"{code}\n\n{REGISTRY[code].explanation.rstrip()}"
