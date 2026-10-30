"""A tool's test: what it runs on, and what must come out (forge MVP 4).

**Inputs are paths inside nf-core's `test-datasets`, never URLs**, so nothing a model writes can
name a host for Nextflow to fetch from. `TestDraft` is what a person or the AI writes; the engine
adds the contract, the name and the commit the data is pinned to.
"""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy
from comeni_core.spell.marks import ContractId, PortName

DataPath = Annotated[str, StringConstraints(
    pattern=r"^[A-Za-z0-9_][A-Za-z0-9._-]*(/[A-Za-z0-9_][A-Za-z0-9._-]*)*$", max_length=300,
)]
"""A file under the `test-datasets` data root: no scheme, no leading `/`, no `..`."""

Pattern = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.*?/\[\]-]+$", max_length=120)]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Expected(_Frozen):
    """One output that must exist: a file published by `port` whose path matches `pattern`."""

    port: PortName
    pattern: Pattern


class SetupStep(_Frozen):
    """A registry tool run first, when an input cannot come ready-made (design answer 7)."""

    tool: ContractId
    inputs: dict[PortName, list[DataPath]] = {}
    feeds: dict[PortName, PortName]
    """This step's output port → the tested tool's input port."""


class TestDraft(_Frozen):
    __test__ = False  # pytest: a name, not a test class

    inputs: dict[PortName, list[DataPath]]
    setup: list[SetupStep] = []
    params: dict[str, str | int | float | bool] = {}
    expect: list[Expected] = Field(min_length=1)
    unchecked: dict[PortName, str] = {}
    """A produced port no pattern can pin, and why (a name made from the sample, say)."""


class ToolTest(TestDraft):
    contract: ContractId
    name: str = Field(min_length=1, max_length=120)
    data_commit: str = Field(min_length=1, max_length=64)
    """The `test-datasets` commit: a dataset that moves is one a result cannot be compared to."""


def _parse_test(path: Path) -> list[ToolTest]:
    data = yaml_strict.load(path) or {}
    data.pop("declares", None)
    return [ToolTest.model_validate(data)]


def test_kind() -> Kind[tuple[str, str], ToolTest]:
    """Keyed on contract and name; a higher layer's test of that name replaces a lower one's."""
    return Kind(DeclaredKind.TESTS, parse=_parse_test, key=lambda t: (t.contract, t.name),
                policy=Policy.REPLACE)


test_kind.__test__ = False
