"""`pipeline.yml` — one artifact, every setting, every provenance.

Replaces `pipeline.ir.json`, `mendel.lock.yml` and `PublishBundle` entirely. A researcher
asking "what settings does this pipeline use, and why" read four files and had to know which of
four mechanisms carried each value; one of those mechanisms carried nothing at all.

Everything the emitter reads is **materialised** here, so `emit(pipeline)` takes one argument
and needs no registry. That is what lets a laboratory archive a validated pipeline and
regenerate its Nextflow years later without the registry it was built against — the part that
resolves differently as it changes.

Two rules govern what is in here, and they are converse:

- **Totality.** Every field of every type this replaces has a home, checked mechanically by
  `tests/test_pipeline_totality.py`. Three drafts of this schema dropped five fields between
  them, including the one the `sealed` profile depends on.
- **Productivity.** A field is embedded only if `emit` reads it, or it is provenance no later
  registry lookup recovers. Self-containment widens the publication door, and that widening was
  accepted on condition that nothing rides along.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core.contract import ModuleContract
from comeni_core.decision import DecisionKind, DecisionRecord
from comeni_core.digest import digest_of
from comeni_core.egress import EgressPayload, Emitted
from comeni_core.gates import Gate
from comeni_core.goal import Goal
from comeni_core.layered import Displacement
from comeni_core.lockfile import LockedLayer
from comeni_core.marks import (
    ContainerRef,
    ContractId,
    Digest,
    EdgeRef,
    GroovyExpression,
    LayerName,
    Line,
    NfIdentifier,
    NfPath,
    NfTemplate,
    NodeId,
    ParamValue,
    PortName,
    StateName,
    TestDataRef,
    TypeId,
    substitutable,
)
from comeni_core.routes import TEMPLATED, ExtKey, Join, Via
from comeni_core.tiers import Tier, ValueSource

SCHEMA_VERSION = 2
"""What this Mendel writes and the highest it will read.

The rule was "bumped only by a change that an older Mendel would misread — a section it would
ignore, or a field whose meaning moved", and it was **too narrow in a way that cost a
diagnostic**. Plan 1.13 added `CallArg.join` and did not bump, reasoning that `extra="forbid"`
makes an older Mendel *refuse* a file carrying the new field rather than misread it. That is
true, and it answers the wrong direction: forward compatibility was fine, while every
**archived** pipeline's `emitted.from_digest` moved, because that digest hashes the model dump.
`MD0213` then reported thousands of untouched files as edited by a human.

So the rule is now: **bump whenever the serialised shape changes at all**, because the digest is
part of the shape. `tests/test_pipeline_file.py::test_a_schema_change_bumps_the_version` holds
the current dump's fingerprint and fails when a field is added without one, so the next person
is told rather than trusted to remember.

2 is this bump — it covers `CallArg.join`, shipped in 1.13 without one, and everything Plan 1.14
adds after it."""

__all__ = [
    "SCHEMA_VERSION",
    "CallArg",
    "Channel",
    "MetaEntry",
    "ModuleRef",
    "Pipeline",
    "RegistryProvenance",
    "Setting",
    "Step",
    "StepInput",
    "Why",
]


class Why(BaseModel):
    """Tier, who settled it, which layer, and the citation — in one place.

    This is the legibility the four-file split could not provide: a reader asking why a value
    is what it is gets the answer beside the value rather than by joining a decision record to
    a node by hand.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Tier
    source: ValueSource
    reason: Line
    for_value: ParamValue = None
    """The value this reason was written about. `MD0223`.

    A `Why` is written once at resolution and never re-derived, so nothing noticed when the
    value moved underneath it. `min_mqs` edited 0 → 30 reached featureCounts as `-Q 30` —
    reads below mapping quality 30 discarded, a real analysis change — while the record still
    said `tier: 2 / source: resolver / reason: contract default for min_mqs`, all three
    false, and `publish` certified it at exit 0. Audit A104.

    **`None` means "written before 1.14", not "explains nothing".** An archived pipeline has
    no such field and must still emit, so the check fires only where this is set and
    disagrees — which is also what gives it real negatives. A check that can only pass is not
    a check.

    Under the engine decision (`docs/design/mendel.md` §1) this stops being a legibility
    defect: a human who leaves a stale reason does it occasionally and may notice, and an
    agent tuning settings does it systematically and does not.
    """

    from_layer: LayerName | None = None
    displaced_layer: LayerName | None = None
    """Set when a lower layer offered something this one beat. A5, A15 — dropped by two drafts
    of this schema, which is why the totality test exists."""


class ModuleRef(BaseModel):
    """Which module, pinned. Replaces `LockedContract`, per step rather than in a side file."""

    model_config = ConfigDict(extra="forbid")

    contract_id: ContractId
    digest: Digest
    container: ContainerRef | None = None
    """The container as the contract declared it, tag and all.

    Carried rather than looked up: resolving a tag to an immutable digest needs a registry
    client and therefore the network, which `comeni-core` may not have — and the `sealed`
    profile's digests-required rule depends on this being recorded.
    """


class Setting(BaseModel):
    """One resolved value, and the route that carries it to the tool."""

    model_config = ConfigDict(extra="forbid")

    name: PortName
    value: ParamValue
    via: Via
    key: ExtKey | None = None
    template: NfTemplate | None = None
    why: Why

    @model_validator(mode="after")
    def _a_raw_ext_value_cannot_be_groovy(self) -> "Setting":
        """`MD0221`. A55: a value on the untemplated `ext` route is appended raw, and
        `_ext_scope` turns any fragment mentioning `${` into a Groovy **closure** that
        Nextflow evaluates once per task — on the host, outside any container.

        The templated route has always been checked (`MD0201`); this is the same class on the
        branch that had none. It is at *load* on purpose. `pipeline.yml` is shareable and
        publishable, `settings[].value` is the field its own header tells a human to edit, and
        `key: prefix` takes no template by design (`MD0204`) — so the dangerous shape is also
        the ordinary one, and the refusal has to happen before `emit` reads the file.

        `value: None` is skipped: an unanswered tier-4 setting contributes no fragment at all.
        Invariant 6 says tier 4 is *flagged*, not fatal, and refusing absence here would stop
        the shipped spine from loading.
        """
        if (
            self.via is Via.EXT
            and self.template is None
            and self.value is not None
            and not substitutable(self.value)
        ):
            raise ValueError(
                f"MD0221: {self.name} routes {self.value!r} to `ext.{self.key}` with no "
                "template, so it is written into Nextflow config verbatim. Use letters, "
                "digits and _ . : + - only, or a number, or true/false — "
                "`mendel explain MD0221`."
            )
        return self


class MetaEntry(BaseModel):
    """One key in a channel's `meta` map. A record rather than a mapping, because a typed key
    does not prove a *declared* key."""

    model_config = ConfigDict(extra="forbid")

    key: NfIdentifier
    value: ParamValue
    why: Why
    """Where this fact came from. **Required, no default** — the A48 principle: a record that
    cannot be constructed without answering the question is the fix that lasts.

    A measured fact is a decision the pipeline rests on. `strandedness` becomes featureCounts'
    `-s`, and getting it wrong is the classic way to a matrix of zeroes — this repository uses
    `-s 2` as its worked example of the system working. It reached the tool carrying nothing
    at all, and the measurement's own declared `cite` stopped at the registry. Audit A80.

    `source` separates a profiler that named itself (`MEASURED`) from a number somebody typed
    into a goal file (`GOAL`). Both are legitimate; only one is checkable, and `sealed` is
    meant to refuse a tier-3 decision resting on the second — issue #2. **That distinction
    starts here and is not finished here**: A108 is that the tier-3 *decision* carries no
    premise, and this only makes the premise recordable.
    """


class CallArg(BaseModel):
    """One positional input of the process.

    Mirrors `NfInput`'s three shapes written out, with **no positional shorthand**: root G's
    rule is that a file reads one way, and `call:` is where a second reading produces a
    silently miswired pipeline rather than a parse error.
    """

    model_config = ConfigDict(extra="forbid")

    ports: list[PortName] = Field(default_factory=list)
    literal: ParamValue = None
    empty_width: int | None = None
    join: Join | None = None
    """How `ports` are matched when there is more than one. Mirrors `NfInput.join`.

    Carried on the artifact rather than read back from the contract because `mendel emit`
    runs with **no registry and no network** — it has this file and nothing else, so a fact
    the emitter needs has to be in it. Audit A92.
    """
    why: Why | None = None
    """A positional literal is as much a decision as a flag is. `NfInput.empty` already
    requires a `because`; this carries the whole provenance instead, because "every choice
    carries its provenance" cannot have an exception for the one route that had no artifact."""


class StepInput(BaseModel):
    """Where one consumed port comes from. An `IREdge`, keyed under its consumer.

    Lossless, since an edge has exactly one consuming port — and it makes "where does this
    step's GTF come from" answerable without scanning a separate list, which is what root D
    found `diff_ir` was not even comparing.
    """

    model_config = ConfigDict(extra="forbid")

    port: PortName
    source: EdgeRef | None = None
    """`<node>.<port>` when an upstream step produces it.

    Two fields rather than one string with two shapes. The spec drafted this as a single
    `from:` carrying either `trimgalore.reads` or `channel:annotation.gtf`, and that cannot be
    an `EdgeRef` — its validator requires two Groovy identifiers, which `channel:annotation.gtf`
    is not. Encoding a union in a string is also root G's problem: a field that reads two ways.
    """
    channel: TypeId | None = None
    """The entry channel this port reads, when nothing upstream produces it."""
    states: list[StateName] = Field(default_factory=list)
    """Sorted at materialisation. `IREdge.states` is a `frozenset`, and a set has no stable
    order — `digest_of` hashes the JSON, so this must not be one."""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "StepInput":
        if (self.source is None) == (self.channel is None):
            raise ValueError(
                f"MD0215: input {self.port} must name exactly one of `source` or `channel`"
            )
        return self


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    module: ModuleRef
    process: NfIdentifier
    include: NfPath
    why: Why
    ext_args: NfTemplate = ""
    """Flags the module always needs, from its contract — `--readFilesCommand zcat` because
    TrimGalore emits `.fq.gz` and STAR cannot read gzip.

    Not a `Setting`: nothing resolved it and there is no decision behind it, so giving it a
    `why` would invent provenance. Carried rather than looked up because emission must not
    need the registry, and composed *before* the resolved settings so a contract's baseline
    cannot be reordered by a value someone answered.
    """
    inputs: list[StepInput] = Field(default_factory=list)
    call: list[CallArg] = Field(default_factory=list)
    settings: list[Setting] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_duplicate_setting(self) -> "Step":
        """MD0212. A11 arriving in a new type.

        `ModuleContract` already rejects a duplicate `Param` because the second silently
        wins and nothing says so. Here it is worse than ambiguous: `ext.args` composition
        sorts by name and joins, so two settings called `readFilesCommand` are two fragments
        the emitter would concatenate into one flag string without comment.
        """
        names = [setting.name for setting in self.settings]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(
                f"MD0212: step {self.id} declares {', '.join(repeated)} more than once"
            )
        return self

    @model_validator(mode="after")
    def _no_two_writers_for_one_destination(self) -> "Step":
        """MD0208. Two settings that share a *destination* under different names.

        `MD0212` above catches two settings sharing a *name*, which is where a directive or a
        meta key collides — the destination there **is** the name. The one destination two
        differently-named settings can share is an `ext` key, and only a key that does not
        compose: `args`, `args2` and `args3` concatenate their fragments on purpose, so two of
        those is composition, not collision. Every other key — `prefix` — takes one value, and
        `_ext_scope` would join two of them into `'beta' 'alpha'`, a value neither author wrote.
        """
        writers: dict[ExtKey, list[str]] = {}
        for setting in self.settings:
            if setting.via is Via.EXT and setting.key not in TEMPLATED:
                writers.setdefault(setting.key, []).append(setting.name)
        collided = sorted(
            (key, sorted(who)) for key, who in writers.items() if len(who) > 1
        )
        if collided:
            key, who = collided[0]
            raise ValueError(
                f"MD0208: step {self.id} routes {' and '.join(who)} to ext.{key.value}, which "
                f"takes one value — a second writer silently wins. `mendel explain MD0208`."
            )
        return self


class Channel(BaseModel):
    """What the laboratory supplies, and the measured facts that ride with it."""

    model_config = ConfigDict(extra="forbid")

    type_id: TypeId
    params: list[PortName] = Field(default_factory=list)
    """Which `params.<name>` the expression references. Plural: one expression may reference
    several, and the shipped registry being 1:1 today is not a schema guarantee.

    Stored *and* derivable, deliberately. Taking a regex over arbitrary Groovy out of the
    emitter is much of what materialisation buys, so the duplication is accepted and then
    checked — `MD0211` refuses a hand-edited file where the two have diverged.
    """
    expression: GroovyExpression
    """The one unbounded-Groovy field in the file, by design. A type declares how it arrives;
    the compiler has no built-in idea what a FASTQ is."""
    meta: list[MetaEntry] = Field(default_factory=list)
    test_data: list[TestDataRef] = Field(default_factory=list)
    """A small public example of this type, for the `test` profile. Pinned to a commit in the
    vocabulary, never a branch — a dataset that moves is one you cannot compare a result against
    next year. Always a list here even when the vocabulary declares one string, because a schema
    that is sometimes a string and sometimes a list reads two ways."""

    @model_validator(mode="after")
    def _params_match_the_expression(self) -> "Channel":
        """MD0211, and it is the price of storing what is also derivable.

        The duplication is deliberate — taking a scan over arbitrary Groovy out of the
        emitter is much of what materialisation buys — so the two must be checked against
        each other on **every** load, not only where they were written together.
        """
        referenced = _param_refs(self.expression)
        if sorted(self.params) != referenced:
            raise ValueError(
                f"MD0211: channel {self.type_id} declares params {sorted(self.params)} but "
                f"its expression references {referenced}. `params:` names what `expression:` "
                f"reads; edit whichever of the two is wrong."
            )
        return self


class RegistryProvenance(BaseModel):
    """Which registry built this. **Provenance, not a dependency of `emit`.**"""

    model_config = ConfigDict(extra="forbid")

    layers: list[LockedLayer] = Field(default_factory=list)
    displaced: list[Displacement] = Field(default_factory=list)
    """What an overlay replaced, across every kind of declared data. Wider than the
    `shadowed` it replaced, which covered contracts alone."""
    unverified: list[ContractId] = Field(default_factory=list)


class Pipeline(EgressPayload):
    """The pipeline. Read this; edit this; `mendel emit` rebuilds the Nextflow from it.

    **Door 4's payload**, since Plan 1.10 Task 11 — publication, the door with no undo.
    `PublishBundle` carried goal + IR + decisions + lockfile, which is this same information
    one layer less assembled, so the artifact a person reads before publishing and the thing
    that crosses the boundary are now one document rather than two that can disagree.

    Being an `EgressPayload` means `frozen=True` as well as `extra="forbid"`: what was
    reviewed is what is sent. `gate` and `emitted` are therefore stamped with `model_copy`
    rather than assigned, which is the right shape for them anyway — both are evidence about
    a finished pipeline, and evidence should not be edited in place.
    """

    @model_validator(mode="before")
    @classmethod
    def _backfill_provenance_a_v1_file_never_had(cls, data: object) -> object:
        """An archived pipeline has no `channels[].meta[].why`, and must still load.

        Plan 1.14 makes that field required — the A48 principle, so nothing can construct a
        fact without saying where it came from. **Requiring it of a document written before it
        existed would be a different claim**: that the provenance is missing, rather than that
        it was never recorded. So a `version: 1` document is backfilled with a `why` that says
        exactly that, and says it in the file rather than in a release note.

        Deliberately here and not on `MetaEntry`, because the *version* is what licenses the
        backfill and only this model knows it. A `MetaEntry` validator would fill the gap for
        a version-2 document too, which would make the requirement decorative — the failure
        mode `Constraints._accept_mapping` avoids by keeping the ergonomic form and the safe
        representation separate decisions.
        """
        if not isinstance(data, dict) or data.get("version", SCHEMA_VERSION) >= 2:
            return data
        legacy = {
            "tier": Tier.STRUCTURAL,
            "source": ValueSource.GOAL,
            "reason": (
                "provenance was not recorded: this pipeline predates schema 2, which is when "
                "measured facts began carrying where they came from"
            ),
        }
        data = dict(data)
        data["channels"] = [
            {**channel, "meta": [{**entry, "why": entry.get("why") or legacy}
                                 for entry in channel.get("meta") or []]}
            for channel in data.get("channels") or []
        ]
        return data

    version: int = SCHEMA_VERSION
    """What this file is written as. Defaults to what this Mendel writes rather than to a
    literal, because a literal is a second place the version lives and the two drifted the
    moment `SCHEMA_VERSION` moved without it."""

    goal: Goal
    """What was asked for. **Inert to `emit`** — it is input to *resolution*, and the facts
    emission needs are already materialised into `channels[].meta`.

    **Required, no default (A48).** Plan 1.10 Task 6 made `goal` keyword-only with no default on
    `Pipeline.of()` for exactly this reason, but the model field kept `default_factory=Goal` — and
    the model is what a hand-edited file loads through. A `pipeline.yml` with the `goal:` block
    deleted then loaded as an empty `Goal`, and `upgrade` re-resolved *that*, writing `steps: []`
    at exit 0. Dropping a section is the likeliest edit mistake there is; it is now a load error.
    Editing it takes effect on
    `mendel upgrade`, and the emitted file says so in a comment."""
    registry: RegistryProvenance = Field(default_factory=RegistryProvenance)
    steps: list[Step] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    emitted: Emitted | None = None
    """Digests of what was written. `None` means no evidence, exactly as `gate: None` does."""
    gate: Gate | None = None
    """The strongest gate this pipeline actually passed. The verdict comes from the artifact."""

    @model_validator(mode="after")
    def _readable_and_unambiguous(self) -> "Pipeline":
        """MD0207 and MD0212, on **every** load — this is what `any load` means.

        MD0207 refuses a file from a newer Mendel rather than reading the parts it happens to
        recognise. Forward compatibility is a promise this format has not made, and an older
        build silently ignoring a section a newer one added is how a pipeline gets emitted
        without the thing that section carried.
        """
        if self.version > SCHEMA_VERSION:
            raise ValueError(
                f"MD0207: this pipeline.yml declares version {self.version}, and this Mendel "
                f"understands version {SCHEMA_VERSION}. Upgrade Mendel; do not edit the "
                f"version down, which would only move the failure somewhere less obvious."
            )
        ids = [step.id for step in self.steps]
        repeated = sorted({name for name in ids if ids.count(name) > 1})
        if repeated:
            raise ValueError(
                f"MD0212: two steps share the id {', '.join(repeated)}. A step id is what "
                f"`inputs[].source` points at, so a duplicate makes the wiring ambiguous."
            )
        measured = {entry.key for channel in self.channels for entry in channel.meta}
        for step in self.steps:
            shadow = sorted(
                s.name
                for s in step.settings
                if s.via is Via.META and s.name in measured
            )
            if shadow:
                raise ValueError(
                    f"MD0208: step {step.id} routes {', '.join(shadow)} to meta, but a "
                    f"measurement already writes {shadow[0]} into the meta map — the setting "
                    f"would silently overwrite a measured fact. `mendel explain MD0208`."
                )
        keys = [record.key for record in self.decisions]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            raise ValueError(
                f"MD0219: two decision records share the key {repeated[0]}. A key names one "
                f"decision; a duplicate is a corrupt file, and `ReplayResolver` would keep one "
                f"and drop the other's answer in silence. `mendel explain MD0219`."
            )
        values = self._param_setting_values()
        for record in self.decisions:
            if getattr(record, "kind", None) is not DecisionKind.PARAM:
                continue
            override = record.human_override
            value = values.get(record.key)
            if override is not None and value is not None and override != value:
                raise ValueError(
                    f"MD0218: {record.key} is answered {value!r} in settings and {override!r} "
                    f"in its decision's human_override — one file, two answers, and emit and "
                    f"upgrade would read different ones. settings[].value is the writable one; "
                    f"remove the human_override or set it equal. `mendel explain MD0218`."
                )

        # MD0220. `why.source: human` is a claim that a person answered an ambiguity resolution
        # had faced and flagged — and it is what clears that item from `needs_review()`. Written
        # into `settings[].why` with no decision recording the answer, it is a review cleared by
        # assertion: exactly the honesty invariant 6 exists to keep. So a `human` source must be
        # backed by a `PARAM` decision for the same key carrying a non-null `human_override`. The
        # genuine edit sets both (settings[].value and the override), so the honest case passes;
        # what this refuses is the port used to relabel a resolver's guess as a person's answer.
        overrides = {
            record.key: record.human_override
            for record in self.decisions
            if getattr(record, "kind", None) is DecisionKind.PARAM
        }
        for step in self.steps:
            for setting in step.settings:
                if setting.why.source is not ValueSource.HUMAN:
                    continue
                key = f"{step.id}.{setting.name}"
                if overrides.get(key) is None:
                    raise ValueError(
                        f"MD0220: {key} says source: human, but no decision records a person "
                        f"answering it — its human_override is null or absent. `source: human` "
                        f"clears the review, so it must be backed by the answer it claims. Set "
                        f"the decision's human_override to the value, or restore the source that "
                        f"resolution gave it. `mendel explain MD0220`."
                    )
        return self

    def _param_setting_values(self) -> dict[str, ParamValue]:
        """`{step.id}.{setting.name}` → value, the key a `ParamDecision` carries."""
        return {
            f"{step.id}.{setting.name}": setting.value
            for step in self.steps
            for setting in step.settings
        }

    def replayable_decisions(self) -> list[DecisionRecord]:
        """Decisions with a parameter's human answer taken from `settings[].value`.

        `settings[].value` is the writable home of a tier-4 answer — the field `emit` reads and
        the file tells a person to edit. A `ParamDecision`'s `human_override` is synced from it
        here so `upgrade` replays the same answer `emit` already uses; before this, editing the
        value and not the override made the two verbs produce different pipelines (A46).

        Only where the value differs from the resolver's own `chosen`: an equal value is the
        resolver's (or a model's) choice, not a human edit, and must keep its review flag rather
        than be relabelled `HUMAN`. A stored, contradicting override is refused at load (MD0218),
        so the value and any existing override agree by the time this runs.
        """
        values = self._param_setting_values()
        replayable = []
        for record in self.decisions:
            value = values.get(record.key)
            if (
                getattr(record, "kind", None) is DecisionKind.PARAM
                and record.human_override is None
                and value is not None
                and value != record.chosen
            ):
                replayable.append(record.model_copy(update={"human_override": value}))
            else:
                replayable.append(record)
        return replayable

    def content_digest(self) -> str:
        """The digest `emitted.from_digest` records, over everything **but** `emitted`.

        A derived field inside the thing it describes does not round-trip, which is the same
        reason `ResolvedValue._drop_computed` exists for `review_level`. Excluding it here is
        load-bearing rather than tidy: include it and the digest can never be recomputed.
        """
        return digest_of(self.model_copy(update={"emitted": None}))

    @classmethod
    def of(cls, ir, registry, vocab, measurements=None, layers=(), *, goal) -> "Pipeline":
        """The **only** validating constructor.

        `goal` is **keyword-only and required**, with no default. The first version defaulted
        it to `Goal(profile=ir.profile)`, which type-checked, round-tripped, passed the
        totality test — that test asks whether a field has a *home*, and it did — and wrote
        `have: []`, `want: []` into every pipeline file. A default is how a field comes to be
        present and empty, and this file's whole claim is that it records what was asked for.

        Enforced by `tests/test_construction.py`, the way `MeasurementRegistry.profile()`
        already is — that guard exists because deleting one call let `profile: {sample_name:
        ...}` build cleanly. Same reasoning: materialisation must not be bypassable by a caller
        assembling a `Pipeline` by hand with the contract-derived fields left empty.

        Takes a registry as an *argument* and keeps none of it. `registry.py` carries a mapping
        and says it is legal because `Registry` is not payload-reachable; holding one here would
        silently end that.
        """
        from comeni_core.lockfile import Lockfile

        lock = Lockfile.of(ir, registry, layers)
        pinned = {entry.id: entry for entry in lock.contracts}

        steps = []
        for node in ir.nodes:
            contract = registry.get(node.contract_id)
            entry = pinned[node.contract_id]
            steps.append(
                Step(
                    id=node.id,
                    module=ModuleRef(
                        contract_id=node.contract_id,
                        digest=entry.digest,
                        container=entry.container,
                    ),
                    process=contract.nf_process,
                    include=contract.nf_include,
                    why=_why(node.selection),
                    ext_args=contract.ext_args,
                    inputs=_inputs(ir, node, contract),
                    call=_call(contract),
                    settings=_settings(node, contract),
                )
            )

        return cls(
            # The *resolved* profile, not the one the goal file declared: `resolve()` routes
            # every profile through `MeasurementRegistry.profile()`, the one validating
            # constructor, and what survived that is what the pipeline was built against.
            goal=goal.model_copy(update={"profile": ir.profile}),
            registry=RegistryProvenance(
                layers=list(lock.layers),
                displaced=list(ir.displaced),
                unverified=list(ir.unverified),
            ),
            steps=steps,
            channels=_channels(ir, registry, vocab, measurements),
            decisions=list(ir.decisions),
        )


def _meta_entry(key: str, measurement, value, profile) -> MetaEntry:
    """One `meta` key, with where its value came from. A80.

    The provenance is the profile's, not this function's invention: `Measured.source` already
    separates a profiling run that named itself from a number somebody typed into a goal file,
    and `Measured.by` already names the contract that produced it. Both stopped at the goal.

    Tier 1 throughout, and that is not a cop-out. A measurement is not a *decision* — nothing
    chose it, the data either says this or it does not — so "no choice exists" is the honest
    tier. What varies is `source`, and that is the field a reader and `sealed` both need.
    """
    entry = next(
        (m for m in profile.measurements if m.measurement == measurement.id), None
    )
    source = entry.source if entry is not None else ValueSource.GOAL
    by = entry.by if entry is not None else None

    if source is ValueSource.MEASURED:
        reason = f"measured by {by}" if by else "measured"
    else:
        reason = "asserted in the goal; no profiling run established it"
    if measurement.cite:
        reason = f"{reason}; {measurement.cite}"
    if measurement.description:
        reason = f"{reason} — {measurement.description}"

    return MetaEntry(
        key=key,
        value=value,
        why=Why(
            tier=Tier.STRUCTURAL,
            source=source,
            reason=reason,
            for_value=value,
        ),
    )


def _why(value) -> Why:
    """A `ResolvedValue` seen as provenance. Field for field, no interpretation.

    `for_value` is the one field that is not simply copied, and it needs no interpretation
    either: the reason was written about the value it arrived with, so recording that value
    beside it is a statement of fact at the moment it is true. Everything after this point can
    only make it false, which is exactly what `MD0223` is for. A104.
    """
    return Why(
        tier=value.tier,
        source=value.source,
        reason=value.reason,
        for_value=value.value,
        from_layer=value.from_layer,
        displaced_layer=value.displaced_layer,
    )


def _settings(node, contract: ModuleContract) -> list[Setting]:
    """Resolved values, each carrying the route its contract declared for it.

    Sorted by name. With one setting the order is unobservable, which is exactly why a test
    with one setting cannot see a sort bug — and `ext.args` composition depends on this being
    deterministic for byte-identical emission.

    **A binding whose contract declares no such param refuses**, and used to be dropped in
    silence — the orphan case one level below `MD0203`, and found by a guard that passed for
    the wrong reason: an A27 test smuggled prose through a `samtools/sort` binding, and that
    contract declares `params: []`, so nothing was being tested.

    Resolution cannot produce one, since it sets parameters *from* `contract.params`. So this
    takes a deserialised or hand-built IR — and there, refusing is right: a value with no
    route is a value the emitted Nextflow will not contain, described in a file whose whole
    claim is that it records every value.
    """
    routes = {param.name: param for param in contract.params}
    orphaned = sorted({b.name for b in node.params} - set(routes))
    if orphaned:
        raise ValueError(
            f"MD0216: {node.id} carries resolved value(s) for {', '.join(orphaned)}, which "
            f"{contract.id} does not declare as a parameter, so nothing would carry them to "
            f"the tool. `mendel explain MD0216`."
        )
    return [
        Setting(
            name=binding.name,
            value=binding.value.value,
            via=routes[binding.name].via,
            key=routes[binding.name].key,
            template=routes[binding.name].template,
            why=_why(binding.value),
        )
        for binding in sorted(node.params, key=lambda b: b.name)
    ]


def _call(contract: ModuleContract) -> list[CallArg]:
    """The process's positional inputs, materialised from `nf_inputs`.

    A positional literal is a tier-1 decision that appeared in no artifact at all before this —
    `STAR_ALIGN(reads, index, gtf, false)` and nothing recorded that `false` or why.
    """
    return [
        CallArg(
            ports=list(spec.ports),
            literal=spec.literal,
            empty_width=spec.empty or None,
            join=spec.join,
            why=(
                Why(
                    tier=Tier.STRUCTURAL,
                    source=ValueSource.RESOLVER,
                    reason=spec.because,
                    for_value=spec.literal,
                )
                if spec.because
                else None
            ),
        )
        for spec in contract.input_signature()
    ]


def _inputs(ir, node, contract) -> list[StepInput]:
    """Every consumed port and where it comes from, keyed under the consumer.

    Entry ports are listed too. Without them a `Step` would not know which channel a port
    reads, and emission would have to ask the registry for `consumes[].type_id` — which is
    exactly the dependency materialisation removes.
    """
    fed = {
        edge.to_port: edge for edge in ir.edges if edge.to_node == node.id
    }
    inputs = []
    for port in contract.consumes:
        edge = fed.get(port.name)
        if edge is not None:
            inputs.append(
                StepInput(
                    port=port.name,
                    source=f"{edge.from_node}.{edge.from_port}",
                    states=sorted(edge.states),
                )
            )
        else:
            inputs.append(StepInput(port=port.name, channel=port.type_id))
    return inputs


def _channels(ir, registry, vocab, measurements) -> list[Channel]:
    """Every type consumed but not produced inside the pipeline, and how it arrives.

    The `meta` entries are the measured facts a module reads — `single_end`, `strandedness` —
    materialised here so emission needs no measurement registry. Sorted, because a set or a
    dict order reaching a digest is how a lockfile becomes spuriously dirty.
    """
    fed = {(edge.to_node, edge.to_port) for edge in ir.edges}
    needed: dict[str, None] = {}
    for node in ir.nodes:
        for port in registry.get(node.contract_id).consumes:
            if (node.id, port.name) not in fed:
                needed[port.type_id] = None

    channels = []
    for type_id in sorted(needed):
        sourced = measurements.meta_sources_for(type_id, ir.profile) if measurements else {}
        expression = vocab.entry_channels.get(type_id) or _default_entry(type_id)
        declared = vocab.test_data.get(type_id)
        channels.append(
            Channel(
                type_id=type_id,
                params=_param_refs(expression),
                expression=expression,
                meta=[
                    _meta_entry(key, *sourced[key], ir.profile) for key in sorted(sourced)
                ],
                test_data=[declared] if isinstance(declared, str) else list(declared or []),
            )
        )
    return channels


_IDENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "_"
)


def _param_refs(expression: str) -> list[str]:
    """Every `params.<name>` an entry-channel expression references, sorted and deduplicated.

    Scanned by hand rather than with `re`, which is not on `comeni-core`'s purity allowlist —
    `_is_identifier` refused to widen it for a character class and this is the same trade.
    `mendel_compiler.emit.entry_params` does the same job with a regex because that package
    already allows one; the two must agree, which is what `MD0211` checks.

    Plural because one expression may reference several: `fastq.reads` names `params.input`
    three times today, and the shipped registry being 1:1 is not a schema guarantee.
    """
    found: set[str] = set()
    marker = "params."
    start = expression.find(marker)
    while start != -1:
        cursor = start + len(marker)
        end = cursor
        while end < len(expression) and expression[end] in _IDENT_CHARS:
            end += 1
        if end > cursor:
            found.add(expression[cursor:end])
        start = expression.find(marker, end)
    return sorted(found)


def _default_entry(type_id: str) -> str:
    """How a type arrives when its vocabulary declares no `entry_channel`.

    Materialised here rather than left to the emitter, because emission must not need the
    vocabulary. Deleting this while narrowing `emit`'s signature emitted `ch_genome_index_star =`
    with nothing after it — valid-looking Groovy that dies at parse, caught by reading the
    golden diff rather than by regenerating it and moving on.
    """
    param = type_id.rsplit(".", 1)[-1]
    return f"Channel.fromPath(params.{param}, checkIfExists: true).map {{ f -> [ [:], f ] }}"
