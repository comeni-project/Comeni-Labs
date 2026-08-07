"""Module contracts: what a module consumes and produces, in typed terms."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core import yaml_strict
from comeni_core.marks import (
    ContainerRef,
    ContractId,
    NfIdentifier,
    NfPath,
    PortName,
    TypeId,
)
from comeni_core.vocabulary import Vocabulary

_NO_EXTRAS = ConfigDict(extra="forbid")
"""Every model a contract is built from forbids unknown keys.

Pydantic ignores them by default, which cost two different things. `digest_of` hashes
`model_dump_json()`, so a key that never survived parsing never reached the digest and two
materially different files pinned identically — the lockfile promising "built against
exactly this contract" and not keeping it. And a misspelled key loaded clean: `ext_arg:`
for `ext_args:`, `state:` for `states:`, accepted, behaving differently from what it says,
invisible to conformance checking because conformance compares a contract to its *module*
and this is a contract disagreeing with itself.

Audit 2026-08-06, A10. Verified when applied: this rejects nothing in the shipped registry.
"""


class Alternative(BaseModel):
    """One acceptable shape for a port: a type, and states that must all hold."""

    model_config = _NO_EXTRAS

    type_id: TypeId
    states: frozenset[str] = frozenset()

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class InputPort(BaseModel):
    model_config = _NO_EXTRAS

    name: PortName
    type_id: TypeId = ""
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
        """Plan 1.7's lockfile pins a contract digest, which hashes exactly these."""
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
    model_config = _NO_EXTRAS

    name: PortName
    """The **emit label**: the compiler reads it as `PROCESS.out.<name>`. Not a name for
    the semantic thing, which is what `type_id` carries — three contracts got that wrong and
    MD0105 found all three."""
    type_id: TypeId
    state: frozenset[str] = frozenset()

    @field_serializer("state")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class Param(BaseModel):
    model_config = _NO_EXTRAS

    name: NfIdentifier
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

    model_config = _NO_EXTRAS

    ports: list[str] = Field(default_factory=list)
    """Contract port names filling this channel, in tuple order."""

    literal: Any = None
    """A plain value for a `val` input that carries no data dependency."""

    because: str = ""
    """Why `empty` is empty. Required whenever it is set.

    `empty` was doing two different jobs — "the type system does not model this input" and
    "we have not wired this yet" — and nothing told them apart. They look identical in YAML
    and identical in the emitted Groovy, and `-stub-run` cannot tell them apart either,
    because nf-core stubs never read their inputs. Two of them shipped: STAR_GENOMEGENERATE
    was called with no genome and STAR_ALIGN with no annotation, through a green test suite
    and a passing stub gate. Issue #8.

    Making it a sentence someone has to write turns the next one into something a reviewer
    reads rather than something a real run discovers. `tests/test_runnable.py` enforces it.
    """

    empty: int = 0
    """Width of an empty tuple standing in for an input the type system does not model.

    0 means this entry is not a placeholder. Otherwise it is the number of elements
    the process declares in that tuple, because Nextflow matches tuple arity: an
    `[[:], []]` handed to `tuple val(meta), path(fasta), path(fai)` fails with "Path
    value cannot be null". `samtools/sort` wants 3; most want 2.
    """


class Provenance(BaseModel):
    model_config = _NO_EXTRAS

    source: str
    drafted_by: str
    approved_by: str
    approved_at: str


class ModuleContract(BaseModel):
    model_config = _NO_EXTRAS

    id: ContractId
    nf_process: NfIdentifier
    """Emitted into `process <name> {` and `include { <name> }`, where nothing can escape
    it. A34: this was a bare `str`, and a contract could add statements to `main.nf`."""
    nf_include: NfPath
    consumes: list[InputPort] = Field(default_factory=list)
    produces: list[OutputPort] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    priority: int = 0
    container: ContainerRef | None = None
    """The container URI as the module declares it, tag and all.

    Optional because `nf-core` declares containers in `main.nf` rather than `meta.yml`,
    so a hand-written contract may not have one yet. The clinical data-protection spec
    (§6.1) resolves this reference to a digest at lock time and the `sealed` profile
    refuses to build against one that will not resolve — both in later plans. What Plan 1
    owes them is somewhere to start.
    """
    nf_inputs: list[NfInput] = Field(default_factory=list)
    """The process call signature. Empty means one channel per consumed port, in order."""

    ext_args: str = ""
    """Flags this module always needs, regardless of any decision.

    Sits beside `nf_inputs` because both answer the same question — *how is this module
    called?* — rather than *what should be decided?*. `--readFilesCommand zcat` is not a
    judgement anybody makes; it is forced by TrimGalore emitting `.fq.gz`.

    **Carries no tier, deliberately.** A tier is for a decision. Labelling this tier 1
    would be defensible and would dilute what a tier means, which is the one thing this
    project sells.

    Emitted into `process { withName: <nf_process> { ext.args = ... } }`, which is where
    every nf-core module reads its arguments from: `def args = task.ext.args ?: ''`.
    """

    provenance: Provenance

    @model_validator(mode="after")
    def _one_binding_per_param(self) -> "ModuleContract":
        """`IRNode.set_param` appends, so a duplicate here became two bindings there.

        The emitter then sorted `(name, value)` pairs and fell through to comparing two
        `ResolvedValue`s, which are not orderable — a traceback from the middle of the
        compiler rather than the diagnostic `mendel explain` exists to give. Audit
        2026-08-06, A11.

        `Registry.load` already refuses a contract ID declared twice in one layer, because
        resolving it by glob order would be the silent arbitrary pick invariant 8 exists to
        prevent. Same argument, one level down; it was not made here.
        """
        names = [p.name for p in self.params]
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            raise ValueError(f"{self.id} declares {', '.join(repeated)} more than once")
        return self

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
        contract = cls.model_validate(yaml_strict.load(path))
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
