"""The pipeline IR: resolver output, compiler input, and what tests assert on."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)

from comeni_core.declared.layered import Displacement
from comeni_core.goal.premise import PremiseRecord
from comeni_core.goal.profile import DataProfile
from comeni_core.plan.decision import DecisionRecord
from comeni_core.plan.tiers import ReviewLevel, Tier, ValueSource, review_level_for
from comeni_core.spell.marks import (
    ChannelName,
    ContractId,
    LayerName,
    Line,
    NodeId,
    ParamValue,
    PortName,
    SocketKey,
    StateName,
    TypeId,
)


def _still_open(value: "ResolvedValue") -> bool:
    """Does this still need a human, or did one already answer it?

    `review_level` alone said "still needs a human" for a value a human had just supplied,
    because the level is derived from the tier and an override deliberately keeps its tier.
    """
    return (
        value.review_level is ReviewLevel.REQUIRED and value.source is not ValueSource.HUMAN
    )


class ResolvedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """Ignore `review_level` on the way in. It is derived, not stored.

        `computed_field` serialises it on dump, and `extra="forbid"` then refuses it on
        load — so the IR did not round-trip at all: `PipelineIR.model_validate_json(
        ir.model_dump_json())` raised. Nothing noticed, because nothing read an IR back
        until now.

        That matters beyond this file. `mendel upgrade` reads a published artifact off disk
        (Plan 1.7, and a `pipeline.yml` since Plan 1.10) and the repair loop reads back an IR
        it sent (Plan 2); both would have failed on a field this class computes for itself.
        Dropping it is right rather than
        merely convenient — the stored value would be a duplicate of `review_level_for(tier)`
        and could disagree with it.
        """
        if isinstance(data, dict) and "review_level" in data:
            data = {k: v for k, v in data.items() if k != "review_level"}
        return data

    value: ParamValue
    tier: Tier
    source: ValueSource = ValueSource.RESOLVER
    reason: Line
    """Why this value was chosen. Prose, and declared as such — it reaches an egress
    payload through `RepairRequest.ir`, so `tests/guards/test_egress.py` names it explicitly
    rather than letting it ride along unexamined."""

    premise: list[PremiseRecord] = Field(default_factory=list)
    """The facts this decision rested on. Carried through the IR so `Why` can record them.

    On `ResolvedValue` rather than assembled at materialisation, because materialisation
    reads the IR and the premises are gone by then — the resolver is the only place that
    knows which facts a row actually consulted. A108.
    """

    axis_reason: Line = ""
    """Why this decision is made this way at all, where `reason` is why this answer won.

    A tier-3 rule block states a methodology and its rows state choices under it. One field
    carried both, so a block citation was printed as a row's reason and the shipped registry
    said HISAT2 was chosen because of the paper describing STAR. Audit A79, A107.
    """

    from_layer: LayerName | None = None
    """Which registry layer supplied the thing this value came from.

    A contract, for a selection; a rule block, for a parameter. Provenance, recorded
    always and for every node, because a curator reading a published bundle needs to know
    where a pipeline was routed from without having to ask — a flag is the wrong shape
    for a question with an answer on every node.

    A third axis beside `tier` (how well it was settled) and `source` (who settled it),
    for the reason `ValueSource`'s own docstring gives: a tier should not also have to say
    who. `None` in a single-layer build, which is the normal case.
    """

    displaced_layer: LayerName | None = None
    """Set when a *lower* layer offered something this one beat. Audit A5, A15.

    Invariant 11 ends "never let an installed overlay reroute a pipeline silently", and
    two routes did. An overlay contract with a different module key is not a shadow, so
    a shadow, so `displaced` misses it; a priority win is not a tie, so invariant 8
    misses it too.
    An overlay rule block overwrote a lower layer's whole block and recorded nothing at
    all, which is worse — nothing was watching rules.

    **Displacement, not origin.** A layer supplying something new is a lab using the
    system as designed and is not reported. A layer replacing what a lower layer said is
    the silent reroute. Flagging origin would put a notice on every module an overlay
    supplies and bury the one that mattered — the failure the fix was meant to prevent.
    """

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        return review_level_for(self.tier)


class ParamBinding(BaseModel):
    """One resolved parameter. A list rather than a dict on purpose.

    `tests/guards/test_egress.py` forbids mappings in anything reachable from a payload, because
    a typed key does not prove a *declared* key — `{"patient_id": ...}` type-checks
    perfectly against `dict[str, ResolvedValue]`. A list of records carries the same
    information and can be inspected field by field.
    """

    model_config = ConfigDict(extra="forbid")

    name: PortName
    value: ResolvedValue


class IRNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    contract_id: ContractId
    params: list[ParamBinding] = Field(default_factory=list)
    selection: ResolvedValue = Field(
        default_factory=lambda: ResolvedValue(
            value=None, tier=Tier.STRUCTURAL, reason="only one contract can produce this"
        )
    )
    """How this module was chosen, at which tier, and why.

    Spec §6.1 has always said every module choice exits at exactly one tier; until this
    field existed only parameters were tiered, so a module selected because it was the sole
    producer was indistinguishable from one selected by priority.
    """

    presence: ResolvedValue = Field(
        default_factory=lambda: ResolvedValue(
            value=None, tier=Tier.STRUCTURAL, reason="required by the pipeline"
        )
    )
    """**Why this step exists**, as distinct from which contract fills it.

    A113 is the two being one field. A module chosen because it was the only candidate
    reported tier 1 — *"no choice exists, inputs force it"* — when what forced it was the
    contents of the registry. The presence of a sorter genuinely is forced, by featureCounts
    asking for a coordinate-sorted BAM; which sorter was never forced at all. Each half now
    carries the tier it earned, and a reader deciding whether a step can be removed is
    reading the half that answers that.
    """

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        """`params={"strandedness": ...}` still works; it is stored as bindings.

        The list is what the egress guard requires, but a mapping is the natural way to
        write one, so the ergonomic form survives the representation change.
        """
        if isinstance(data, dict) and isinstance(data.get("params"), dict):
            data = dict(data)
            data["params"] = [{"name": k, "value": v} for k, v in data["params"].items()]
        return data

    def param(self, name: str) -> ResolvedValue | None:
        return next((b.value for b in self.params if b.name == name), None)

    def set_param(self, name: str, value: ResolvedValue) -> None:
        self.params.append(ParamBinding(name=name, value=value))


class IREdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_node: NodeId
    from_port: PortName
    to_node: NodeId
    to_port: PortName
    type_id: TypeId
    states: frozenset[StateName] = frozenset()

    @field_serializer("states")
    def _sorted_states(self, states: frozenset[str]) -> list[StateName]:
        return sorted(states)


class IRChannel(BaseModel):
    """One channel and the sockets it feeds. The resolved form of a `DraftChannel`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ChannelName
    type_id: TypeId

    scope: ResolvedValue | None = None
    """The scope somebody chose for this channel, **or `None` for the type's default.**

    `None` is not `SAMPLE`: it is *nobody said*, which is a different fact. Taking a type's
    default is not a decision, and an artifact recording one for it would owe `mendel explain`
    an answer to a question that was never open — §12.2's rule, arriving from the other side.

    ═══ A `ResolvedValue`, AND THE EGRESS GUARD IS WHY ═══════════════════════════════════════

    The first version carried a `Scope` and a bare `Line`. `tests/guards/test_egress.py` refused
    both: a plain `str` on a payload is how a closed vocabulary stops being closed, and the `Line`
    would have been the **fifteenth** free-text field on invariant 14's surface — a new author at a
    new moment, which is the argument `ParamDecision.override_reason` had to make to become the
    tenth.

    It does not have to be made. A scope override *is* a resolved value: something settled, at a
    tier, by somebody, for a reason, against an axis. `ResolvedValue` is that shape, and its
    `reason` and `axis_reason` are already fields 3 and 12. Nothing widens.

    Tier 4 always, because whether two GTF ports are fed by one file or by two is not derivable
    from the drawing — both are legal pipelines and they analyse different experiments, so a
    person decided and invariant 6 flags a person's decision however confident they were.
    """

    ports: list[SocketKey] = Field(default_factory=list)
    """`<node>.<port>`. Sorted at construction — a set has no stable order and this reaches a
    digest, which is the same reason `IREdge.states` carries a serialiser."""


class PipelineIR(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[IRNode] = Field(default_factory=list)
    edges: list[IREdge] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)

    channels: list[IRChannel] = Field(default_factory=list)
    """Which sockets the drawing grouped into each channel.

    **Empty means one channel per type**, which is what every build meant before Plan 5B phase
    3 and is still what a goal-driven `resolve()` produces. `materialise.channels_of` fills it
    from the drawing's `DraftChannel` list, because whether two GTF ports are one channel or two
    is a decision only a person can make.

    On the IR rather than on the `Goal` because it is **wiring**, not shape. A goal says *I have
    two annotations*; this says which of them a given port reads, and invariant 15's whole
    argument is that a goal describes a shape and nothing else.

    **A list of records rather than a `dict[socket, name]`**, which is what it was for one
    commit. `tests/guards/test_egress.py` refused it in two voices — *`dict` is not a declared
    container* and *these fields are mappings; use a list of declared records instead* — and it
    was right twice: a mapping's keys are unvalidated by construction, which is the hole the
    egress boundary spent three audits closing. It also reads better beside `DraftChannel` and
    `ChannelView`, which are the same fact at the other two layers.
    """

    profile: DataProfile = Field(default_factory=DataProfile)
    """What was measured about the data this pipeline was built for.

    On the IR rather than passed to the emitter separately, because it is part of what the
    pipeline was built *from* — the same reason Plan 1.7 puts `registry_layers` here. The
    emitter needs it to populate the `meta` map, and a reviewer reading `pipeline.ir.json`
    needs it to know which measurement a tier-3 decision rested on.
    """

    registry_layers: list[LayerName] = Field(default_factory=list)
    """Which layers built this, in stacking order. A list because order is meaning:
    later layers win, and a set would lose that."""

    displaced: list[Displacement] = Field(default_factory=list)
    """What an overlay replaced, across every kind of declared data.

    Carried on the artifact rather than only printed at build time. A published pipeline
    whose registry quietly rerouted it would be unauditable by the person who downloaded
    it, which is the failure invariant 11 exists to prevent.

    Was `shadowed: list[ShadowRecord]`, which covered contracts alone — so an overlay
    measurement that flipped the strandedness a module is told (A23) or an overlay
    vocabulary that replaced the entry channel (A24) reached the artifact as nothing at
    all. They have no `IRNode` to hang off; this is where they go."""

    unverified: list[ContractId] = Field(default_factory=list)
    """Contracts whose module source was not present, so nothing checked them.

    Carried on the artifact rather than only printed, because it reaches a publish bundle:
    a curator may refuse to curate an unverified contract. A claim about a module, with no
    module to check it against, is a claim without evidence.
    """

    def needs_review(self) -> list[str]:
        """Everything a human must look at before this pipeline runs.

        Covers decisions as well as parameters. A routing tie emits a DecisionRecord
        at tier 4 — invariant 8 demotes it, invariant 6 says tier 4 is always flagged
        — but for a while this method scanned only node params, so the CLI reported
        "0 requiring review" while an aligner had been chosen alphabetically. A record
        nobody is shown is not a flag.
        """
        flagged = [
            f"{node.id}.{binding.name}"
            for node in self.nodes
            for binding in node.params
            if _still_open(binding.value)
        ]
        # A module choice carries a tier too, since `selection` landed. A tied producer
        # also emits a DecisionRecord, so this would mostly be a duplicate — except the
        # record is keyed on the ambiguity and this is keyed on the node, and a reviewer
        # reading "which modules need looking at" should not have to join the two.
        flagged += [
            f"{node.id} (module)" for node in self.nodes if _still_open(node.selection)
        ]
        answered = {key for key, _ in self._overrides()}
        flagged += [
            decision.key
            for decision in self.decisions
            if review_level_for(decision.tier) is ReviewLevel.REQUIRED
            and decision.key not in flagged
            and decision.key not in answered
        ]
        return flagged

    def overrides(self) -> list[str]:
        """Tier-4 questions a **human** answered. What `needs_review()` stops listing.

        A separate list, for the reason `overlay_reroutes()` is one: "what must I decide"
        and "what did somebody already decide" are different questions, and folding the
        second into the first teaches a reviewer to skim both.

        Without this the count never reaches zero and the CLI says REVIEW for ever on a
        question already settled — `lockfile.py` makes the same argument about a different
        list, and it is the sharper one: **a list that cries wolf gets ignored**, so the
        genuinely unanswered tier-4 beside it goes unread too.

        The tier does *not* clear. An override is tier 4 that stayed tier 4, which is what
        distinguishes it from a goal pin: see `ValueSource.HUMAN`. Invariant 6 says tier 4 is
        always flagged; it does not say the flag can never be answered.
        """
        return [f"{key} = {value!r}" for key, value in self._overrides()]

    def _overrides(self) -> list[tuple[str, object]]:
        """Every human-answered value, keyed the way `needs_review()` keys it.

        One computation, two callers, because the two disagreeing is exactly how a value
        could be excused from review and never appear anywhere else.
        """
        found = [
            (f"{node.id}.{binding.name}", binding.value.value)
            for node in self.nodes
            for binding in node.params
            if binding.value.source is ValueSource.HUMAN
        ]
        found += [
            (f"{node.id} (module)", node.contract_id)
            for node in self.nodes
            if node.selection.source is ValueSource.HUMAN
        ]
        # A decision key is `<node>.<subject>`, and a producer's subject is
        # `producer:<type_id>` — so the record's key never equals the `(module)` string
        # above. Both are listed: the record is what `upgrade` replays and the node is what
        # a reviewer reads, and joining them by hand is what `needs_review()` exists to
        # avoid. Deduplicated on the key, which is what makes the param case one entry.
        seen = {key for key, _ in found}
        found += [
            (decision.key, decision.human_override)
            for decision in self.decisions
            if getattr(decision, "human_override", None) is not None
            and decision.key not in seen
        ]
        return found

    def overlay_reroutes(self) -> list[str]:
        """Where an installed overlay changed what the layers below it would have done.

        Invariant 11 ends "never let an installed overlay reroute a pipeline silently",
        and two routes did it silently: an overlay contract with a different module key is
        not a shadow, and an overlay rule block replaced a lower block without a record.
        Audit A5 and A15.

        **A separate list from `needs_review()`, deliberately.** That method answers "what
        must a human decide before this runs" and lists `REQUIRED` only, under a test named
        for the guarantee. This answers a different question — "what did my overlay
        change" — and the two do not belong in one list: an overlay winning on priority is
        a documented default, correctly tier 2 and correctly review `none`. What was
        missing was visibility, not severity.

        Derived rather than stored, so it cannot drift from the fields it reads, and empty
        for the single-layer build that is the normal case.
        """
        lines = [
            f"{node.id} (module) = {node.contract_id}: from "
            f"{node.selection.from_layer!r}, displacing {node.selection.displaced_layer!r}"
            for node in self.nodes
            if node.selection.displaced_layer is not None
        ]
        lines += [
            f"{node.id}.{binding.name} = {binding.value.value!r}: from "
            f"{binding.value.from_layer!r}, displacing {binding.value.displaced_layer!r}"
            for node in self.nodes
            for binding in node.params
            if binding.value.displaced_layer is not None
        ]
        return lines
