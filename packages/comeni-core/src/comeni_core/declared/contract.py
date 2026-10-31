"""Module contracts: what a module consumes and produces, in typed terms."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    field_serializer,
    model_serializer,
    model_validator,
)

from comeni_core import yaml_strict
from comeni_core.declared.measurement import MeasurementKind
from comeni_core.declared.signature import states_in_type
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.diagnostics import coded
from comeni_core.spell.directives import LEGAL_DIRECTIVES, NEXTFLOW_VERSION
from comeni_core.spell.marks import (
    ContainerRef,
    ContractId,
    NfIdentifier,
    NfPath,
    NfTemplate,
    PortName,
    RoleName,
    TypeId,
)
from comeni_core.spell.routes import TEMPLATED, ExtKey, Join, Via

_NO_EXTRAS = ConfigDict(extra="forbid")
"""Shared strict configuration for every model nested in a contract."""


class Alternative(BaseModel):
    """One acceptable shape for a port: a type, and states that must all hold."""

    model_config = _NO_EXTRAS

    type_id: TypeId
    states: frozenset[str] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def _carried(cls, data: object) -> object:
        return states_in_type(data, "states")

    @field_serializer("states")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class Cardinality(StrEnum):
    """Whether a process invocation consumes one item or the complete channel."""

    ONE = "1"
    """One item per invocation. The process runs once per item on its channel — the default,
    and what every port was before this field was read by anything."""

    MANY = "*"
    """The whole channel in one invocation, emitted with ``.collect()``."""


class InputPort(BaseModel):
    model_config = _NO_EXTRAS

    name: PortName
    type_id: TypeId = ""
    state_required: frozenset[str] = frozenset()
    """States this port cannot function without. A **structural** constraint: their absence
    is unroutable and is refused, rather than routed around."""

    state_required_conventional: frozenset[str] = frozenset()
    """Optional states tried before the structural requirement during routing."""

    state_conventional_because: str = ""
    """Why the conventional states are useful but not structurally required."""

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
    cardinality: Cardinality = Cardinality.ONE
    """How many channel items each process invocation receives."""

    @model_validator(mode="before")
    @classmethod
    def _carried(cls, data: object) -> object:
        return states_in_type(data, "state_required")

    @field_serializer(
        "state_required", "state_required_conventional", "state_preferred", "prefer"
    )
    def _sorted(self, states: frozenset[str]) -> list[str]:
        """Serialize state sets deterministically for stable contract digests."""
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
        """The conventional form first, the structural form as the fallback.

        Expressed as two alternatives rather than as a flag threaded through the router,
        because `accepts` already means exactly this — "a BAM, or failing that a CRAM",
        first-match-wins — and a second mechanism for *try this, then that* would be a second
        place for the two to disagree. The failure list `_satisfy_port` builds is then also
        correct for free.
        """
        if self.accepts:
            return self.accepts
        structural = Alternative(type_id=self.type_id, states=self.state_required)
        if not self.state_required_conventional:
            return [structural]
        return [
            Alternative(
                type_id=self.type_id,
                states=self.state_required | self.state_required_conventional,
            ),
            structural,
        ]


class OutputPort(BaseModel):
    model_config = _NO_EXTRAS

    name: PortName
    """The **emit label**: the compiler reads it as `PROCESS.out.<name>`. Not a name for
    the semantic thing, which is what `type_id` carries — three contracts got that wrong and
    MD0105 found all three."""
    type_id: TypeId
    state: frozenset[str] = frozenset()
    format: frozenset[str] = frozenset()
    """The file formats it writes, as `main.nf` says (`tsv`; `folder` for a directory). Shown
    to people and checked against the module; it takes no part in matching, so tools writing
    the same content in different layouts stay interchangeable."""

    @model_validator(mode="before")
    @classmethod
    def _carried(cls, data: object) -> object:
        return states_in_type(data, "state")

    @field_serializer("state", "format")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)

    @model_serializer(mode="wrap")
    def _no_empty_format(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Left out when unknown, so a contract that says nothing keeps its digest."""
        dumped = handler(self)
        if not dumped.get("format"):
            dumped.pop("format", None)
        return dumped


class ParamDomain(BaseModel):
    """The enum, boolean, integer, or numeric values a parameter accepts."""

    model_config = _NO_EXTRAS

    kind: MeasurementKind
    values: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None

    def refuse(self, name: str, value: object) -> str | None:
        """Why `value` is not a legal setting for `name`, or `None` if it is.

        Returns rather than raises: the caller is a rule validator that wants to add the file
        and the decision key to the message, and an exception here would either lose that
        context or have to be caught and re-raised — which is the shape `measurements.get`
        already has to be wrapped for.
        """
        if self.kind is MeasurementKind.ENUM:
            if value in self.values:
                return None
            return (
                f"{name} accepts {', '.join(self.values)}, and {value!r} is none of them"
            )
        if self.kind is MeasurementKind.BOOLEAN:
            return None if isinstance(value, bool) else f"{name} accepts a boolean"
        if isinstance(value, bool) or not isinstance(value, int | float):
            noun = "an integer" if self.kind is MeasurementKind.INTEGER else "a number"
            return f"{name} accepts {noun}"
        if self.kind is MeasurementKind.INTEGER and not isinstance(value, int):
            return f"{name} accepts an integer"
        if self.minimum is not None and value < self.minimum:
            return f"{name} has minimum {self.minimum:g}, and {value!r} is below it"
        if self.maximum is not None and value > self.maximum:
            return f"{name} has maximum {self.maximum:g}, and {value!r} is above it"
        return None


class Param(BaseModel):
    """A resolvable setting and the emission route that carries it to the tool."""

    model_config = _NO_EXTRAS

    name: NfIdentifier
    tier_hint: int | None = None

    domain: ParamDomain | None = None
    """Legal values for this parameter; ``None`` leaves rule validation to its fallback."""

    default: Any = None
    because: str = ""
    """Why the declared default is appropriate; empty means no reason was declared."""
    via: Via
    """Which emission site carries this. No default: a setting with no route is the defect."""
    key: ExtKey | None = None
    """Required by `via: ext`, forbidden elsewhere. `when` is not a member — see `ExtKey`."""
    template: NfTemplate | None = None
    """How the value composes into an argument string. Required for `args`/`args2`/`args3`,
    forbidden on routes that take one typed value."""

    @model_validator(mode="after")
    def _route_is_complete(self) -> "Param":
        """The route must actually be able to carry a value.

        Four ways it cannot, and each is a code rather than a silent no-op: no key on `ext`, a
        key off `ext`, a template that discards the value or sits where nothing composes, and a
        directive name Nextflow would ignore.
        """
        if self.via is Via.EXT and self.key is None:
            raise ValueError(coded("MD0205", f"{self.name} declares via: ext without a key"))
        if self.via is not Via.EXT and self.key is not None:
            raise ValueError(
                coded(
                    "MD0205",
                    f"{self.name} declares key: {self.key} on via: {self.via}, which has "
                    "no keyspace")
            )
        if self.via is Via.DIRECTIVE and self.name not in LEGAL_DIRECTIVES:
            raise ValueError(
                coded(
                    "MD0209",
                    f"{self.name} is not a process directive Nextflow {NEXTFLOW_VERSION} "
                    "accepts. An unknown directive inside a `withName` block is silently ignored, "
                "so this would be a setting that does nothing.")
            )

        composes = self.via is Via.EXT and self.key in TEMPLATED
        if composes and (self.template is None or "{value}" not in self.template):
            raise ValueError(
                coded("MD0204", f"{self.name} routes to ext.{self.key} but its template does not "
                "mention {value}, so the resolved value would be discarded while real flags "
                "were emitted")
            )
        if not composes and self.template is not None:
            raise ValueError(
                coded(
                    "MD0204",
                    f"{self.name} routes to {self.via}, which takes one typed value rather "
                    "than an argument string, so a template has nothing to compose into")
            )
        return self


class ContractExtArgs(BaseModel):
    """Baseline argument text a module always needs and its stated premise."""

    model_config = _NO_EXTRAS

    template: str = ""
    because: str = ""


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

    param: str = ""
    """The ``params`` entry that fills this positional process input."""

    because: str = ""
    """Why an intentionally empty placeholder is valid for this process input."""

    empty: int = 0
    """Width of an empty tuple standing in for an input the type system does not model.

    0 means this entry is not a placeholder. Otherwise it is the number of elements
    the process declares in that tuple, because Nextflow matches tuple arity: an
    `[[:], []]` handed to `tuple val(meta), path(fasta), path(fai)` fails with "Path
    value cannot be null". `samtools/sort` wants 3; most want 2.
    """

    join: Join | None = None
    """How multiple ports are matched; required because no join policy is universally safe."""

    @model_validator(mode="after")
    def _join_declared_when_it_matters(self) -> "NfInput":
        """Require an explicit join policy when one input combines multiple ports."""
        if len(self.ports) > 1 and self.join is None:
            raise ValueError(
                f"an nf_inputs entry with two or more ports ({', '.join(self.ports)}) must "
                f"declare `join:` — `broadcast` if the later ports are one thing every sample "
                f"is paired against, `by_sample` if they are per-sample and must match. There "
                f"is no default: guessing wrong produces a green run with wrong results."
            )
        return self


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
    """Validated identifier used in generated process and include statements."""
    nf_include: NfPath
    consumes: list[InputPort] = Field(default_factory=list)
    produces: list[OutputPort] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)

    roles: list[RoleName] = Field(default_factory=list)
    """The jobs this contract can do. What a tier-3 rule targets, and the only thing it may.

    Empty is legal, so the field could be added without rewriting every layer in the world
    on the same day — but the shipped registry is held to a stricter standard by
    `test_every_contract_declares_a_role`, because a contract filling no role is invisible
    to every rule and that is a silent way to be unreachable rather than a loud one.
    """

    priority: int = 0
    priority_because: str = ""
    """Why priority is an appropriate selection axis for this contract."""

    container: ContainerRef | None = None
    """Optional container reference declared for the module."""
    nf_inputs: list[NfInput] = Field(default_factory=list)
    """The process call signature. Empty means one channel per consumed port, in order."""

    ext_args: "str | ContractExtArgs" = ""
    """Baseline argument text, optionally paired with the premise that requires it."""

    provenance: Provenance

    @model_validator(mode="after")
    def _one_binding_per_param(self) -> "ModuleContract":
        """Reject duplicate parameter names before they become ambiguous bindings."""
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
        data = yaml_strict.load(path)
        # The declaration marker belongs to the loader, not the strict contract model.
        #
        # **`declares:`, not `kind:`** — a measurement already has a `kind:`, and it means
        # the kind of its *value* (`integer`, `enum`). Two meanings for one key in the same
        # file is how a loader comes to strip a field it did not write.
        if isinstance(data, dict):
            data.pop("declares", None)
        try:
            contract = cls.model_validate(data)
        except ValidationError as exc:
            # Give a missing route its domain diagnostic and contract context. Preserve every
            # other Pydantic validation error unchanged.
            missing_via = cls._missing_via(exc, data)
            if missing_via is not None:
                raise missing_via from exc
            raise
        contract.check_against(vocab)
        return contract

    @staticmethod
    def _missing_via(exc: ValidationError, data: Any) -> ValueError | None:
        """MD0200 for a `Param` with no `via:`, naming the contract and the parameter."""
        params = data.get("params", []) if isinstance(data, dict) else []
        cid = data.get("id", "<unknown>") if isinstance(data, dict) else "<unknown>"
        for error in exc.errors():
            loc = error["loc"]
            if error["type"] == "missing" and "via" in loc and "params" in loc:
                idx = loc[loc.index("params") + 1]
                name = "<unnamed>"
                if isinstance(idx, int) and idx < len(params) and isinstance(params[idx], dict):
                    name = params[idx].get("name", "<unnamed>")
                return ValueError(
                    coded(
                        "MD0200",
                        f"contract {cid} parameter {name!r} declares no via:, so nothing "
                        f"would carry its value. Add via: naming where it lands — ext with a key, "
                    f"meta, or directive. `mendel explain MD0200`.")
                )
        return None

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
