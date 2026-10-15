"""The loaded layers, adapted to what the build plan reads (`mendel_authoring.ports.Declared`)."""

from dataclasses import dataclass

from mendel_resolver.layers import Layers


@dataclass(frozen=True)
class LayersDeclared:
    layers: Layers

    def outputs(self, contract_id: str) -> list[str]:
        return [output.type_id for output in self.layers.registry.get(contract_id).produces]

    def tool(self, tool_id: str) -> str | None:
        found = self.layers.tools.tools.get(tool_id)
        return found.description if found else None

    def family(self, family_id: str) -> str | None:
        found = self.layers.families.families.get(family_id)
        return found.description if found else None


def of(layers: Layers) -> LayersDeclared:
    return LayersDeclared(layers)
