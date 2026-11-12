"""Module contracts: what a module consumes and produces, in typed terms."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

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
from comeni_core.plan.tiers import Grain
from comeni_core.spell.directives import LEGAL_DIRECTIVES, NEXTFLOW_VERSION
from comeni_core.spell.marks import (
    ContainerRef,
    ContractId,
    MeasurementId,
    NfIdentifier,
    NfPath,
    NfTemplate,
    PortName,
    RoleName,
    TypeId,
    substitutable,
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
    grain: Grain | None = None
    """What one invocation of the process reads (#466): one item per `study` or per `sample`.
    `None` is the type's own grain."""
    many: bool = False
    """One invocation takes every item of a finer grain at once, gathered with `.collect()`:
    MultiQC reads every sample's report in one run. Declared with `grain: study`, since a sample
    has nothing finer to gather until units and parts arrive (per-sample design, Goal A)."""
    by: MeasurementId | None = Field(default=None, exclude_if=lambda by: by is None)
    """With `many`, gather per value of this key rather than over the study (#466): a
    co-assembler reads every sample of one group in one call. The key comes from each
    samplesheet row."""
    required: bool = True
    """Whether the process can run without this input (#460). An optional input is left out
    unless switched on, and its `nf_inputs` entry says what to pass instead (`absent`)."""

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
    def _gathers_something(self) -> "InputPort":
        if self.by is not None and not self.many:
            raise ValueError(coded(
                "MD0343", f"port {self.name!r} groups by {self.by} and does not gather "
                "(`many: true`) — `mendel explain MD0343`."))
        # A study gathers its samples; a sample gathers its rows, such as lanes (#466); a group,
        # the samples sharing a key.
        if self.many and self.by is None and self.grain not in (Grain.STUDY, Grain.SAMPLE):
            raise ValueError(coded(
                "MD0331", f"port {self.name!r} gathers (`many: true`) at grain "
                f"{self.grain.value if self.grain else 'of its type'}, which has nothing finer to "
                "gather. Declare `grain: study` beside it to read every sample at once."))
        return self

    @model_validator(mode="after")
    def _one_form(self) -> "InputPort":
        if self.type_id and self.accepts:
            raise ValueError(f"port {self.name!r} declares both `type_id` and `accepts`; use one")
        if not self.type_id and not self.accepts:
            raise ValueError(f"port {self.name!r} declares neither `type_id` nor `accepts`")
        if self.state_preferred and not self.prefer:
            object.__setattr__(self, "prefer", self.state_preferred)
        return self

    @model_serializer(mode="wrap")
    def _no_default_required(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Left out when required, and grain and many when unset, so a contract that says
        nothing keeps its digest."""
        data = handler(self)
        if self.required:
            data.pop("required", None)
        if self.grain is None:
            data.pop("grain", None)
        if not self.many:
            data.pop("many", None)
        return data

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
    produced_when: dict[str, Any] | None = None
    """When the process writes this output (#460): `None` is always, otherwise a `when` over
    `given.<input>` and `param.<name>` facts. QUAST's misassemblies exist only with a reference."""

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
        if self.produced_when is None:
            dumped.pop("produced_when", None)
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
        # The default becomes the step's setting, which refuses this at MD0221 on every build
        # (issue 477). A module that falls back on its own (`task.ext.prefix ?: meta.id`) needs
        # no default: an unset value contributes no fragment.
        if (self.via is Via.EXT and self.template is None and self.default is not None
                and not substitutable(self.default)):
            raise ValueError(
                coded("MD0221", f"{self.name}'s default {self.default!r} routes to "
                      f"`ext.{self.key}` with no template, so every pipeline using it would be "
                      "refused. Leave the default out when the module falls back on its own, "
                      "or use letters, digits and _ . : + - only — `mendel explain MD0221`.")
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

    join: Join | Annotated[dict[str, Join], Field(title="Per port")] | None = None
    """How multiple ports are matched; required because no join policy is universally safe.

    One `Join` applies to every port after the first. A map gives each later port its own, for
    a tuple that pairs a per-sample index with its BAM and shares one intervals file across the
    run (gatk4/haplotypecaller, #464)."""

    absent: int = 0
    """Width of the empty tuple passed when this entry's ports are all left out (#460). The arity
    rule is `empty`'s. Required when every port is optional, refused otherwise: an entry with a
    required port is never left out whole (#464)."""

    @field_serializer("join")
    def _sorted_join(self, join: "Join | dict[str, Join] | None") -> Any:
        """A join map in port order, so its digest does not depend on how it was written."""
        if isinstance(join, dict):
            return {port: join[port] for port in self.ports if port in join}
        return join

    @model_serializer(mode="wrap")
    def _no_default_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Left out when 0, so a contract that says nothing keeps its digest."""
        data = handler(self)
        if not self.absent:
            data.pop("absent", None)
        return data

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
        if isinstance(self.join, dict):
            later = self.ports[1:]
            missing = [p for p in later if p not in self.join]
            extra = sorted(p for p in self.join if p not in later)
            if missing or extra:
                raise ValueError(
                    f"the join map of nf_inputs {self.ports} must name each port after the "
                    f"first exactly once: missing {missing}, not after the first {extra}")
        return self

    def join_for(self, port: str) -> Join:
        """How `port`, a port after the first, meets the ones before it."""
        if port not in self.ports[1:]:
            raise ValueError(f"{port!r} is not a port after the first of nf_inputs {self.ports}")
        if isinstance(self.join, dict):
            return self.join[port]
        if self.join is None:
            raise ValueError(f"nf_inputs {self.ports} declares no join")
        return self.join


class ConstraintRow(BaseModel):
    """What a tool allows (#460): when `when` holds, these ports or params must or must not be
    given. A fact about the tool, never a choice; choosing is a rule's (#461)."""

    model_config = _NO_EXTRAS

    when: dict[str, Any] = Field(default_factory=dict)
    """A condition over `given.<port>` and `param.<name>` facts, in rules' `when` syntax."""
    requires: list[str] = Field(default_factory=list)
    forbids: list[str] = Field(default_factory=list)
    because: str = Field(min_length=1)
    cite: str = ""

    @model_validator(mode="after")
    def _says_something(self) -> "ConstraintRow":
        if not self.requires and not self.forbids:
            raise ValueError("a constraint row requires or forbids something")
        return self


class GroupKind(StrEnum):
    """Boutiques' groups: shorthand that expands into constraint rows."""

    ONE_OF = "one_of"
    """Exactly one member is given."""
    ANY_OF = "any_of"
    """At least one member is given."""
    ALL_OR_NONE = "all_or_none"
    """All members are given, or none."""


class Group(BaseModel):
    model_config = _NO_EXTRAS

    kind: GroupKind
    members: list[str] = Field(min_length=2)
    when: dict[str, Any] = Field(default_factory=dict)
    because: str = Field(min_length=1)


def _when_keys(when: dict[str, Any], ports: dict[str, set[str]], params: set[str]) -> list[str]:
    """The keys of a contract's `when` that name nothing in it. A condition reads
    `given.<port>`, `param.<name>`, `type.<port>`, the type connected to a port (#464), and
    `fact.<measurement>`, a fact each sample has (#466); `ports` maps each port to the types it
    accepts."""
    wrong = []
    for key, value in when.items():
        space, _, name = key.partition(".")
        if space == "given" and name in ports and value not in ("present", "absent"):
            wrong.append(f"{key}: {value!r} (an input is `present` or `absent`)")
        elif space == "type" and name in ports:
            named = _types_named(value)
            accepted = ports[name]
            if named is None or not named or not named <= accepted:
                wrong.append(f"{key}: {value!r} (`{name}` accepts {', '.join(sorted(accepted))})")
        elif space == "fact" and name.isidentifier():
            # A per-sample fact (#466): which measurement it names is checked at load, where
            # the measurements are known (MD0336).
            continue
        elif not ((space == "given" and name in ports) or (space == "param" and name in params)):
            wrong.append(key)
    return wrong


def _types_named(value: Any) -> set[str] | None:
    """The type ids a `type.<port>` condition names: one id, `{in: [...]}` or `{not: id}`."""
    if isinstance(value, str) and value not in ("present", "absent") and " " not in value:
        return {value}
    if isinstance(value, dict) and len(value) == 1:
        if isinstance(value.get("in"), list) and all(isinstance(v, str) for v in value["in"]):
            return set(value["in"])
        if isinstance(value.get("not"), str):
            return {value["not"]}
    return None


def accepted_types(port: "InputPort") -> set[str]:
    """The types routing can connect to `port`: its alternatives' types."""
    return {alternative.type_id for alternative in port.alternatives()}


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

    constraints: list[ConstraintRow] = Field(default_factory=list)
    """What this tool allows between its inputs and params (#460)."""
    groups: list[Group] = Field(default_factory=list)

    provenance: Provenance

    @model_serializer(mode="wrap")
    def _no_default_constraints(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Left out when empty, so a contract that says nothing keeps its digest."""
        data = handler(self)
        for field in ("constraints", "groups"):
            if not data.get(field):
                data.pop(field, None)
        return data

    @model_validator(mode="after")
    def _constraints_name_real_things(self) -> "ModuleContract":
        """MD0602 for a name the contract does not declare; MD0601 for an input slot that
        cannot be emitted when its optional ports are left out."""
        accepts = {p.name: accepted_types(p) for p in self.consumes}
        ports = set(accepts)
        params = {p.name for p in self.params}
        clauses = [("a constraint row", r.when, [*r.requires, *r.forbids])
                   for r in self.constraints]
        clauses += [(f"a {g.kind} group", g.when, g.members) for g in self.groups]
        clauses += [(f"output {o.name!r}", o.produced_when or {}, []) for o in self.produces]
        for where, when, names in clauses:
            unknown = _when_keys(when, accepts, params)
            unknown += [n for n in names if n not in ports | params]
            if unknown:
                raise ValueError(coded(
                    "MD0602", f"{self.id}: {where} names {', '.join(unknown)}, which is not an "
                    "input or param of this contract, or a type it does not accept. Conditions "
                    "test `given.<input>`, `param.<name>` or `type.<input>`; a measurement "
                    "waits for per-sample facts (#466)"))
        self._optional_slots_can_be_emitted(ports)
        return self

    def _optional_slots_can_be_emitted(self, ports: set[str]) -> None:
        required = {p.name: p.required for p in self.consumes}
        if not self.nf_inputs and not all(required.values()):
            raise ValueError(coded(
                "MD0601", f"{self.id} has optional inputs but no nf_inputs: declare each "
                "optional input's slot with `absent`, the empty tuple's width"))
        # A slot may mix required and optional ports, and hold optional ports independent of
        # each other (#464): the compiler passes `[]` in each left-out port's position. Only a
        # slot whose ports can all be left out needs `absent`, the width of the empty tuple.
        for entry in self.nf_inputs:
            optional = [p for p in entry.ports if not required.get(p, True)]
            if len(optional) < len(entry.ports) and entry.absent:
                raise ValueError(coded(
                    "MD0601", f"{self.id}: nf_inputs {entry.ports} declares absent, but it has "
                    "a required input, so it is never left out whole"))
            if not optional:
                continue
            if len(optional) == len(entry.ports) and not entry.absent:
                raise ValueError(coded(
                    "MD0601", f"{self.id}: nf_inputs {entry.ports} can be left out entirely "
                    "and has no `absent` width"))
            # When the first port is left out, the first one that is on takes its place, and
            # the later ports' joins are relative to it: sound only if they all join alike.
            if (entry.ports[0] in optional and isinstance(entry.join, dict)
                    and len(set(entry.join.values())) > 1):
                raise ValueError(coded(
                    "MD0601", f"{self.id}: nf_inputs {entry.ports} starts with an optional "
                    "input, so its later inputs must all join the same way"))

    def optional_ports(self) -> list[str]:
        """The inputs the process can run without, in declaration order."""
        return [p.name for p in self.consumes if not p.required]

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
            cls._states_beside_the_type(path, data)
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
        # Late import: constraints evaluates contracts, so it imports this module.
        from comeni_core.declared.constraints import check_constraints

        findings = check_constraints(contract)
        if findings:
            raise ValueError(f"{path}: " + "\n".join(findings))
        return contract

    @staticmethod
    def _states_beside_the_type(path: Path, data: Any) -> None:
        """MD0110: a contract file has one way to write states, in the type."""
        ports = [*data.get("produces", []), *data.get("consumes", [])]
        ports += [a for port in data.get("consumes", []) for a in port.get("accepts", [])]
        for port in ports:
            field = next((f for f in ("state", "state_required", "states") if f in port), None)
            if field is not None:
                raise ValueError(coded(
                    "MD0110", f"{path}: port {port.get('name', port.get('type_id'))!r} writes "
                    f"`{field}`; states belong in the type, as `type::state`"))

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
