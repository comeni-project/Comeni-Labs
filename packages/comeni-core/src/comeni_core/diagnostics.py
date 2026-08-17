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

    CORE = "core"
    """`comeni-core` — the types, the declared-data loaders, and `pipeline.yml` itself.

    **Missing until 2026-08-16, and its absence is why twenty-three entries named the wrong
    package.** `comeni_core.artifact.pipeline` holds the artifact's validators, so `MD0207`,
    `MD0212`, `MD0225` and the rest raise here while being *about* a file the compiler writes;
    `declared/` holds the loaders, so `MD0001`–`MD0009` raise here too. With no truthful option
    the label drifted to whichever subsystem the code felt like it belonged to.

    A vocabulary that cannot express the truth is a vocabulary that teaches people to lie to it,
    and it did — including in the six codes added the same week this was fixed.
    """
    COMPILER = "compiler"
    RESOLVER = "resolver"
    FORGE = "forge"
    AI = "ai"
    """`mendel-ai` — reaching a model, and what comes back.

    Arrived with forge Phase 2, the first time anything in this repository could call a model.
    Its codes are about **access** (nothing configured, credentials refused, no answer in time)
    and **output** (an answer that will not fit the shape it was asked for). Neither is about a
    pipeline, which is why they are their own concern rather than an extension of routing."""
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


def coded(code: str, message: str) -> str:
    """A message with its diagnostic code on the front, checked against the registry.

    **This is the one place a code becomes text.** Before it, seventy-eight emissions were
    string literals — `f"MD0001: {where} is not valid YAML"` — with nothing tying the code to
    `diagnostics.yml`. A typo shipped, a `raise` outliving its registry entry shipped, and both
    printed to a user while failing `mendel explain` and never appearing in the generated page.
    Every code in source happened to be declared, which is correctness by vigilance.

    **A string builder rather than an exception factory.** Twelve exception types carry codes —
    `ValueError` at sixty-five, `RuleValidationError` at nineteen — so a factory returning an
    exception would have to take the type as an argument, which reads worse than the `raise` it
    replaces. And several emissions are not raises at all: the CLI prints `mendel: MD0210: …`
    and `MD0202` is a report line. One function serves every site, changes no exception class,
    and leaves `raise` visible where control flow is decided.

    **Checked at call time, which is the error path.** That is weaker than import time and it is
    deliberately not the whole answer: `tests/test_diagnostics_ownership.py` scans the literals
    and runs whether or not anything fails. What this buys is that a bad code cannot reach a
    user — the emission raises here instead, naming the code and the known set.
    """
    if code not in REGISTRY:
        raise UnknownDiagnosticError(
            f"{code} is not a declared diagnostic. Declare it in "
            f"comeni_core/diagnostics.yml, or fix the code.\n"
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return f"{code}: {message}"


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
