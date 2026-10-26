"""Load, validate, format, and explain the repository-wide diagnostic registry.

``diagnostics.yml`` is the source for emitted-code validation and generated reference
documentation. Diagnostics belong to the code that emits them rather than to laboratory registry
data, so all packages share this versioned registry through ``comeni-core``.
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
    """Subsystem ownership used to group generated diagnostic documentation."""

    CORE = "core"
    """Core models, declared-data loaders, and pipeline artifact validation."""
    COMPILER = "compiler"
    RESOLVER = "resolver"
    FORGE = "forge"
    AI = "ai"
    """Model access and validation of model output."""
    API = "api"
    AUTHORING = "authoring"
    """Authoring protocol and session-state transitions."""
    WIENER = "wiener"
    """Pure run admission, management, and state transitions."""
    WIENER_API = "wiener-api"
    """Wiener persistence and service boundaries."""
    VENDOR = "vendor"
    """Maintainer-time source fetching and registry-layer checks."""


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
    """Read and validate the registry, refusing duplicate YAML keys."""
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
    """Prefix a message with a declared code, rejecting unknown emission sites."""
    if code not in REGISTRY:
        raise UnknownDiagnosticError(
            f"{code} is not a declared diagnostic. Declare it in "
            f"comeni_core/diagnostics.yml, or fix the code.\n"
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return f"{code}: {message}"


def explain(code: str) -> str:
    """Return long-form help, or a helpful known-code list for an unknown code."""
    if code not in REGISTRY:
        return (
            f"{code} is not a diagnostic this version emits.\n"
            f"Known: {', '.join(sorted(REGISTRY))}"
        )
    return f"{code}\n\n{REGISTRY[code].explanation.rstrip()}"
