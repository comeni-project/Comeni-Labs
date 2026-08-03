"""Module contracts: what a module consumes and produces, in typed terms."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core.vocabulary import Vocabulary


class Alternative(BaseModel):
    """One acceptable shape for a port: a type, and states that must all hold."""

    model_config = ConfigDict(extra="forbid")

    type_id: str
    states: frozenset[str] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class InputPort(BaseModel):
    name: str
    type_id: str = ""
    state_required: frozenset[str] = frozenset()
    state_preferred: frozenset[str] = frozenset()
    """Deprecated spelling of `prefer`, kept so no vendored contract breaks."""
    accepts: list[Alternative] = Field(default_factory=list)
    """Ordered alternatives, ANDed within each. One level of DNF, deliberately.

    Full boolean logic would express more and cost the thing the product sells: today
    "why is SAMTOOLS_SORT here?" answers itself in a sentence, and under a general
    constraint language it becomes a solver trace.
    """
    prefer: frozenset[str] = frozenset()
    """Tiebreak *within* a matched alternative. Never causes insertion or failure.

    Does not promote a later alternative over an earlier one: alternative order is the
    author's statement of preference between kinds of input, the same way decision-table
    rows are ordered and first-match-wins.
    """
    cardinality: str = "1"

    @field_serializer("state_required", "state_preferred", "prefer")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        """Plan 2.5's lockfile pins a contract digest, which hashes exactly these."""
        return sorted(states)

    @model_validator(mode="after")
    def _one_form(self) -> "InputPort":
        if self.type_id and self.accepts:
            raise ValueError(f"port {self.name!r} declares both `type_id` and `accepts`; use one")
        if not self.type_id and not self.accepts:
            raise ValueError(f"port {self.name!r} declares neither `type_id` nor `accepts`")
        if self.state_preferred and not self.prefer:
            object.__setattr__(self, "prefer", self.state_preferred)
        return self

    def alternatives(self) -> list[Alternative]:
        if self.accepts:
            return self.accepts
        return [Alternative(type_id=self.type_id, states=self.state_required)]


class OutputPort(BaseModel):
    name: str
    type_id: str
    state: frozenset[str] = frozenset()

    @field_serializer("state")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class Param(BaseModel):
    name: str
    tier_hint: int | None = None
    default: Any = None


class NfInput(BaseModel):
    """One positional input of the process, and what fills it.

    A contract port is *semantic* — a typed thing the module consumes. A process
    input is *plumbing* — one channel in the call signature. They do not
    correspond, and assuming they did is what made the first generated spine
    uncallable:

    - `subread/featurecounts` takes **one** channel carrying a tuple of bam *and*
      annotation, so two ports collapse into one position;
    - `samtools/sort` takes **three**, of which a reference tuple and an
      `index_format` value model nothing in the type system;
    - `star/align` takes **four** for two ports.

    Declaring the signature here rather than parsing it out of `main.nf` is what
    lets the compiler emit a call for *any* module — a pegi3s image, an in-house
    process — not only for nf-core ones. Exactly one field is meaningful per entry.
    """

    ports: list[str] = Field(default_factory=list)
    """Contract port names filling this channel, in tuple order."""

    literal: Any = None
    """A plain value for a `val` input that carries no data dependency."""

    empty: int = 0
    """Width of an empty tuple standing in for an input the type system does not model.

    0 means this entry is not a placeholder. Otherwise it is the number of elements
    the process declares in that tuple, because Nextflow matches tuple arity: an
    `[[:], []]` handed to `tuple val(meta), path(fasta), path(fai)` fails with "Path
    value cannot be null". `samtools/sort` wants 3; most want 2.
    """


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
    nf_inputs: list[NfInput] = Field(default_factory=list)
    """The process call signature. Empty means one channel per consumed port, in order."""

    provenance: Provenance

    def input_signature(self) -> list[NfInput]:
        """What the process is actually called with.

        Defaulting to one channel per port keeps single-input modules trivial to
        write, which is most of them.
        """
        if self.nf_inputs:
            return self.nf_inputs
        return [NfInput(ports=[port.name]) for port in self.consumes]

    @classmethod
    def load(cls, path: Path, vocab: Vocabulary) -> "ModuleContract":
        contract = cls.model_validate(yaml.safe_load(path.read_text()))
        contract.check_against(vocab)
        return contract

    def check_against(self, vocab: Vocabulary) -> None:
        for port in self.consumes:
            # Every alternative, not only the first: a port whose second branch names an
            # undeclared state is exactly as broken as one whose first does, and it fails
            # later, on the input nobody tested with.
            for alternative in port.alternatives():
                vocab.validate(alternative.type_id, alternative.states)
                vocab.validate(alternative.type_id, port.prefer)
        for port in self.produces:
            vocab.validate(port.type_id, port.state)
