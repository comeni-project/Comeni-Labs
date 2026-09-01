"""Module contracts: what a module consumes and produces, in typed terms."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    model_validator,
)

from comeni_core import yaml_strict
from comeni_core.declared.measurement import MeasurementKind
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


class Cardinality(StrEnum):
    """How many items this port consumes per invocation.

    **A closed vocabulary, where it was a bare `str` defaulting to `"1"`.** That is A10's rule —
    a value that is ignored is a value that can be mistyped in silence — and it mattered here
    more than usual, because the field had exactly one reader and it compared against the
    literal `"1"`: anything else, including `"one"` and `"2"`, meant *many* by falling through.

    Two members, and a third is not obviously wrong — `"2"` for a paired thing is imaginable.
    It is refused until somebody has one, because a number here would have to mean *the process
    is invoked once per N items*, and nothing in Nextflow's channel algebra does that without a
    `buffer` whose size is a pipeline's decision rather than a contract's.
    """

    ONE = "1"
    """One item per invocation. The process runs once per item on its channel — the default,
    and what every port was before this field was read by anything."""

    MANY = "*"
    """The whole channel, in one invocation. Emitted as `.collect()`.

    **MULTIQC is why this exists.** It consumes `qc.report` from every sample, and without it the
    emitted workflow says `MULTIQC(ch_qc_report)` — one invocation per sample, producing N
    reports where the entire point of the tool is to produce one. It is not in the spine, so
    nothing is broken today; the contract is in the registry and would be wrong the moment a
    goal routed to it.
    """


class InputPort(BaseModel):
    model_config = _NO_EXTRAS

    name: PortName
    type_id: TypeId = ""
    state_required: frozenset[str] = frozenset()
    """States this port cannot function without. A **structural** constraint: their absence
    is unroutable and is refused, rather than routed around."""

    state_required_conventional: frozenset[str] = frozenset()
    """States this port is conventionally given but does not require.

    `star/align` declared `state_required: [trimmed]`, and STAR soft-clips adapters —
    nf-core/rnaseq's `--skip_trimming` exists precisely because trimming is optional. So the
    contract encoded a tier-2 convention as a tier-1 constraint, and a rule deciding that
    trimming should be absent produced an **unroutable pipeline** rather than a shorter one.
    Same disease as "the only contract that produces this" (A113), one layer down.

    It still drives insertion: the router asks for the conventional states first and falls
    back to the structural ones only when nothing can supply them. Dropping them outright
    would delete trimming from every pipeline, which is a far larger change than the one this
    field is for.
    """

    state_conventional_because: str = ""
    """Why those states are a convention and not a requirement.

    Named for the field it explains rather than for the field beside it. A
    `state_required_because` would read as justifying `state_required`, which is the one it
    is not about — and the distinction between the two is the entire content of §8.2.
    """

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
    """How many items this port takes per invocation — see `Cardinality`.

    **It reaches the emitter since Plan 5B phase 4.3.** It had exactly one reader,
    `validate.py`, which counts *wires* — a different question entirely: how many edges may
    target this port, not how many items it consumes. A port can take one wire carrying a
    channel of five hundred reports, which is precisely MULTIQC's case.
    """

    @field_serializer(
        "state_required", "state_required_conventional", "state_preferred", "prefer"
    )
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

    @field_serializer("state")
    def _sorted(self, states: frozenset[str]) -> list[str]:
        return sorted(states)


class ParamDomain(BaseModel):
    """What values a parameter accepts. Spec §7.1's second half.

    Mirrors `Measurement`'s declaration — `kind`, `values`, `minimum`, `maximum` — because it
    is the same question asked about the other end of a rule: a `when` reads a measurement's
    domain and a `then` writes a param's. Sharing `MeasurementKind` rather than declaring a
    parallel enum keeps that symmetry a fact rather than a resemblance.

    Deliberately **not** `extensible`. A measurement is extensible when the world can produce
    a value nobody enumerated — `organism`, `purpose` — and a parameter's legal values are a
    property of a tool's command line, which is fixed by the tool. A param whose values
    genuinely cannot be enumerated declares no domain at all.
    """

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
    """A setting the resolver decides, and the route that carries the answer to the tool.

    Every field but `via` predates Plan 1.10. `via` is mandatory because without it a resolved
    value went to a `params.<node>_<name>` line in `main.nf` that no module reads — the resolver
    ran, flagged tier 4, printed `REVIEW`, and the pipeline behaved identically whatever the
    answer was. Issue #10. Requiring a route makes that unrepresentable rather than detectable.
    """

    model_config = _NO_EXTRAS

    name: NfIdentifier
    tier_hint: int | None = None

    domain: ParamDomain | None = None
    """What values this parameter accepts. `None` means undeclared, which is legal and is what
    most contracts say today.

    Without it, `MD0300` had to guess whether a `then` was arithmetic by looking for a
    measurement name sitting beside an operator — a heuristic that admits anything spelled
    unexpectedly and refuses `paired-end`, a legitimate value killed by a check nobody could
    disable. With it the question is a type check. Audit A118; spec §7.1.

    The heuristic is **kept** as the fallback rather than retired, because most contracts
    declare no domain and removing it would trade a heuristic for nothing.
    """

    default: Any = None
    because: str = ""
    """Why this default is this value — the *document* tier 2 claims exists.

    Tier 2 is defined as "a documented default exists", and there was nowhere to put the
    document. A laboratory raising featureCounts' `-Q` from 0 to 30 — discarding every read
    below mapping quality 30, a real change to which reads are counted — produced a
    **byte-identical** `why:` block, because the justification lived in a YAML comment the
    loader drops. Audit A76.

    Empty is legal and materialises as *"no reason was declared"* rather than as the old
    circular text: `contract default for min_mqs` names the field it is explaining, which
    says who settled it and not why.
    """
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
    """Baseline flags a module always needs, and the premise that makes them right.

    `because` is a **premise**, not a fact about a neighbouring module, and the difference is
    the whole of A82. STAR's `--readFilesCommand zcat` was justified by *"TrimGalore emits
    `.fq.gz`"*; one goal edit removes TrimGalore and the flag survives, its stated reason
    naming a module that is not in the pipeline. A premise about the *reads* stays true when
    the graph moves — and where it can be false, saying so is the point.
    """

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
    """The name of a `params` entry that fills this slot — the `via: positional` route.

    Declared **here rather than as an index on `Param`**, correcting the plan, which proposed
    `Param.slot: int`. A position stored in two places is two places that can disagree, and
    `MD0102` already counts `nf_inputs` entries against the module's inputs — so keeping the
    slot on this side means a routed parameter still occupies its position and the arity check
    goes on working untouched.

    Replaces a `literal` for a value somebody should be able to decide: `star_ignore_sjdbgtf`
    was a hardcoded `false` in the call, outside the tier ladder and in no review queue, while
    the only route the design allowed put the answered value in `meta` where STAR never looks.
    Audit A91.
    """

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

    join: Join | None = None
    """How this entry's ports are matched when there is more than one.

    Required whenever `ports` holds two or more, and there is deliberately no default.
    `emit` used to combine unconditionally — a Cartesian product — which is right for the
    one multi-port entry the shipped registry has and silently wrong for any second
    per-sample port. Audit A92.
    """

    @model_validator(mode="after")
    def _join_declared_when_it_matters(self) -> "NfInput":
        """Two ports in one channel have to say how they meet.

        There is no safe default to fall back on: guessing `broadcast` cross-products two
        per-sample channels and Nextflow calls it success, which is how two samples became
        four analyses with half of them mixing samples. Guessing `by_sample` would drop the
        shipped spine's annotation, which has no per-sample key to join on. Only the contract
        knows. Audit A92.
        """
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
    """Emitted into `process <name> {` and `include { <name> }`, where nothing can escape
    it. A34: this was a bare `str`, and a contract could add statements to `main.nf`."""
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
    """Why this contract ranks where it does — the same missing document as `Param.because`.

    A tier-2 module selection reads *"registry priority 10, over …"*, which states the
    mechanism and not the reason. `priority` is a bare integer, and the justification for the
    shipped one lives in a YAML comment the loader discards: exactly A76's shape, one field
    over. Audit A128.

    Reaches the artifact as the selection's `axis_reason` — *why is priority the thing
    deciding here* — leaving `reason` to say which contract won and by what margin.
    """

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

    ext_args: "str | ContractExtArgs" = ""
    """Flags this module always needs, regardless of any decision — and why.

    Two forms. A bare string is the old spelling and still parses; the record form adds
    `because:`, which is what reaches `pipeline.yml` as the step's reason. A contract using
    the bare form materialises with *"declared by the contract with no stated reason"*, which
    is honest about being a gap instead of looking like an answer. Audit A82.

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
        data = yaml_strict.load(path)
        # `declares: contract` is how a file says what it is now that the directory does not
        # (comeni-registry#1). Popped rather than declared as a field: it is the loader's
        # business, not the contract's, and `extra="forbid"` means it has to go somewhere.
        #
        # **`declares:`, not `kind:`** — a measurement already has a `kind:`, and it means
        # the kind of its *value* (`integer`, `enum`). Two meanings for one key in the same
        # file is how a loader comes to strip a field it did not write.
        if isinstance(data, dict):
            data.pop("declares", None)
        try:
            contract = cls.model_validate(data)
        except ValidationError as exc:
            # A missing `via` is a real refusal — MD0200, the value reaches no tool — but
            # Pydantic reports it as a bare `Field required` on `params.N.via`, and the CLI
            # wraps any `ValidationError` as "this goal is not valid": the one file the operator
            # did not write, blamed for a contract author's omission (A41). Re-raise the
            # missing-`via` case with its code and the contract named; leave every other
            # `ValidationError` untouched so `nf_process`/`nf_include` and the model-level route
            # checks keep raising exactly what their tests assert.
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
