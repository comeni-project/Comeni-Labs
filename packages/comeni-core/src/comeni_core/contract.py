"""Module contracts: what a module consumes and produces, in typed terms."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from comeni_core.vocabulary import Vocabulary


class InputPort(BaseModel):
    name: str
    type_id: str
    state_required: frozenset[str] = frozenset()
    state_preferred: frozenset[str] = frozenset()
    cardinality: str = "1"


class OutputPort(BaseModel):
    name: str
    type_id: str
    state: frozenset[str] = frozenset()


class Param(BaseModel):
    name: str
    tier_hint: int | None = None
    default: Any = None


class Provenance(BaseModel):
    source: str
    drafted_by: str
    approved_by: str
    approved_at: str


class ModuleContract(BaseModel):
    id: str
    nf_process: str
    nf_include: str
    consumes: list[InputPort] = Field(default_factory=list)
    produces: list[OutputPort] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    priority: int = 0
    container: str | None = None
    """The container URI as the module declares it, tag and all.

    Optional because `nf-core` declares containers in `main.nf` rather than `meta.yml`,
    so a hand-written contract may not have one yet. The clinical data-protection spec
    (§6.1) resolves this reference to a digest at lock time and the `sealed` profile
    refuses to build against one that will not resolve — both in later plans. What Plan 1
    owes them is somewhere to start.
    """
    provenance: Provenance

    @classmethod
    def load(cls, path: Path, vocab: Vocabulary) -> "ModuleContract":
        contract = cls.model_validate(yaml.safe_load(path.read_text()))
        contract.check_against(vocab)
        return contract

    def check_against(self, vocab: Vocabulary) -> None:
        for port in self.consumes:
            vocab.validate(port.type_id, port.state_required)
            vocab.validate(port.type_id, port.state_preferred)
        for port in self.produces:
            vocab.validate(port.type_id, port.state)
