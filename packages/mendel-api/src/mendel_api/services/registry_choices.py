"""What a person can pick from: every type, job and tool, as a picker shows them.

The list and its order come from here, so the browser filters by text and holds no rule of its
own. Everything is read from the declared registry.
"""

from comeni_core.declared.families import family_of
from pydantic import BaseModel

from mendel_api.services import registry

DERIVED = "measurement"
"""A measurement's derived type is a fact about the data, not a file a port can be given."""


class TypeChoice(BaseModel):
    id: str
    name: str | None
    explain: str | None
    family: str
    family_says: str
    made_by: list[str]
    read_by: list[str]


class RoleChoice(BaseModel):
    id: str
    tools: list[str]
    reads: list[str]
    makes: list[str]


class ToolChoice(BaseModel):
    id: str
    roles: list[str]
    reads: list[str]
    makes: list[str]


class Choices(BaseModel):
    types: list[TypeChoice]
    roles: list[RoleChoice]
    tools: list[ToolChoice]


def read() -> Choices:
    stack = registry.stack()
    contracts = stack.registry.all()

    def reads(contract) -> list[str]:
        return sorted({port.type_id for port in contract.consumes})

    def makes(contract) -> list[str]:
        return sorted({port.type_id for port in contract.produces})

    vocabulary, families = stack.vocabulary, stack.families.families
    types = [
        TypeChoice(
            id=type_id,
            name=vocabulary.names.get(type_id),
            explain=vocabulary.explains.get(type_id),
            family=family_of(type_id),
            family_says=families[family_of(type_id)].description,
            made_by=[c.id for c in contracts if type_id in makes(c)],
            read_by=[c.id for c in contracts if type_id in reads(c)],
        )
        for type_id in sorted(vocabulary.types)
        if family_of(type_id) != DERIVED
    ]
    roles = []
    for role in sorted(stack.roles.names):
        doing = [c for c in contracts if role in c.roles]
        roles.append(RoleChoice(
            id=role, tools=[c.id for c in doing],
            reads=sorted({t for c in doing for t in reads(c)}),
            makes=sorted({t for c in doing for t in makes(c)}),
        ))
    tools = [ToolChoice(id=c.id, roles=sorted(c.roles), reads=reads(c), makes=makes(c))
             for c in contracts]
    return Choices(types=types, roles=roles, tools=tools)
