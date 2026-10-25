# packages/comeni-core/src/comeni_core/declared/tools.py
"""Load descriptive metadata for tools represented in registry layers.

Each declaration supplies a stable tool ID, display name, description, and optional homepage
and citation. Higher layers replace lower-layer metadata with the same ID.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from comeni_core import yaml_strict
from comeni_core.declared.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack


class Tool(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=128)
    """The module key's first two segments, `nf-core/samtools`: the same key `mendel docs`
    groups a page by, so a tool, its folder and its page are one name."""
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=600)
    homepage: str | None = None
    cite: str | None = None


def _parse_tool(path: Path) -> list[Tool]:
    """Parse one tool declaration, ignoring its loader-facing kind marker."""
    data = yaml_strict.load(path) or {}
    data.pop("declares", None)
    return [Tool.model_validate(data)]


class ToolCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tools: dict[str, Tool]

    @staticmethod
    def kind() -> Kind[str, Tool]:
        """Keyed on the tool id; a higher layer replaces a lower one's description."""
        return Kind(
            DeclaredKind.TOOLS, parse=_parse_tool, key=lambda tool: tool.id, policy=Policy.REPLACE
        )

    @classmethod
    def of(cls, stacked: Stacked[str, Tool]) -> "ToolCatalogue":
        return cls(tools=dict(stacked.entries))

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "ToolCatalogue":
        """Load tool metadata from one or more layer roots."""
        return cls.of(stack(layers_of(layers), cls.kind()))
