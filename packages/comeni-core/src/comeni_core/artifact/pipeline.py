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

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from comeni_core.artifact.digest import digest_of
from comeni_core.artifact.egress import EgressPayload, Emitted
from comeni_core.artifact.gates import Gate
from comeni_core.artifact.load import _param_refs
from comeni_core.artifact.lockfile import LockedLayer
from comeni_core.declared.layered import Displacement
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal
from comeni_core.goal.premise import PremiseRecord
from comeni_core.plan.decision import DecisionKind, DecisionRecord
from comeni_core.plan.tiers import (
    ReviewLevel,
    Tier,
    ValueSource,
    review_level_for,
)
from comeni_core.spell.marks import (
    ChannelName,
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
from comeni_core.spell.routes import TEMPLATED, ExtKey, Join, Via

SCHEMA_VERSION = 6
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

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """Ignore `review_level` on the way in — it is derived, not stored.

        `computed_field` serialises it and `extra="forbid"` would then refuse it on load, so
        a `pipeline.yml` this Mendel wrote could not be read back by `emit` or `upgrade`.
        `ResolvedValue._drop_computed` exists for exactly this and says so; the second copy
        is here rather than shared because the two models are in different modules and a
        mixin for six lines would hide the reason.
        """
        if isinstance(data, dict) and "review_level" in data:
            data = {k: v for k, v in data.items() if k != "review_level"}
        return data

    tier: Tier
    source: ValueSource

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        """What this tier obliges a reader to do, beside the tier itself. Spec §6.2.

        `tier: 3` is a number whose meaning lives in a table in another document, and the
        artifact is the thing a stranger opens. Carrying the answer is what stops
        `CLAUDE.md` having to be open beside it.

        Derived rather than stored: a stored copy is a second source of truth for one fact,
        and `Why` already learned that lesson once — `for_value` exists because a reason
        could outlive the value it explained (A104). Named `review_level` rather than
        `review` to match `ResolvedValue.review_level`, which has computed the same thing
        since Plan 1; two names for one concept is how the two come to disagree.
        """
        return review_level_for(self.tier)

    reason: Line

    premise: list[PremiseRecord] = Field(default_factory=list)
    """The facts this decision rested on, and where each came from.

    Tier 3 is defined as producing `value + rule + measurement` and produced the first two:
    the artifact said which rule fired and never what it fired *on*. `CLAUDE.md` calls tier 3
    advisory and glosses it *"the machinery worked, check the premise"* — and there was no
    premise in the file to check. A measured build and an asserted one had a byte-identical
    `steps:` block. Audit A108, A127.

    This is also what `ProfilePolicy` reads to make `sealed` refuse a tier-3 decision resting
    on an assertion (issue #2), which is why the origin travels *with* the value rather than
    being recoverable by joining against the profile: a join is a step a caller can skip.

    Empty for a document written before version 3. Requiring it of one would assert the
    premise is *missing* rather than *never recorded* — Plan 1.14 Task 0's lesson, which cost
    a plan the first time it was learned.
    """

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

    axis_reason: Line = ""
    """Why this decision is made this way **at all**, where `reason` is why this answer won.

    A tier-3 rule block carries a methodology — "read length determines which aligner is
    appropriate", cited to Dobin et al. 2013 — and each row carries a choice made under it.
    One field was serving both, so the block's citation was printed as the row's reason and
    the shipped registry stated that HISAT2 was chosen because of the paper describing STAR.
    Audit A79 and A107, the same defect found from opposite ends.

    Empty for a decision with no axis to state — a contract default has no methodology behind
    it beyond itself, and inventing one would be the circularity A76 is about.
    """

    from_layer: LayerName | None = None
    displaced_layer: LayerName | None = None
    """Set when a lower layer offered something this one beat. A5, A15 — dropped by two drafts
    of this schema, which is why the totality test exists."""


def _no_flags_why() -> Why:
    """The `why` for a module that declares no `ext_args` at all.

    A step with no flags still answers the question — "why does this module take no baseline
    arguments" — and the answer is that its contract declares none. Saying so is cheaper than
    a reader wondering whether the field went missing.
    """
    return Why(
        tier=Tier.STRUCTURAL,
        source=ValueSource.RESOLVER,
        reason="this contract declares no flags its module always needs",
        for_value="",
    )


class ModuleRef(BaseModel):
    """Which module, pinned. Replaces `LockedContract`, per step rather than in a side file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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

    model_config = ConfigDict(extra="forbid", frozen=True)

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
                coded("MD0221", f"{self.name} routes {self.value!r} to `ext.{self.key}` with no "
                "template, so it is written into Nextflow config verbatim. Use letters, "
                "digits and _ . : + - only, or a number, or true/false — "
                "`mendel explain MD0221`.")
            )
        return self


class MetaEntry(BaseModel):
    """One key in a channel's `meta` map. A record rather than a mapping, because a typed key
    does not prove a *declared* key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

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


class ExtArgs(BaseModel):
    """Flags a module always needs, and why it needs them.

    Was a bare `NfTemplate`, on a recorded argument that has not survived contact: *"nothing
    resolved it and there is no decision behind it, so giving it a `why` would invent
    provenance."* That conflates **tier** with **reason**. A tier is about how something was
    settled; a reason is about why it is what it is, and a tier-1 fact has one — `NfInput.empty`
    already carries a tier-1 `Why` for a structurally identical thing. Audit A82.

    The argument was also *load-bearing on a premise it did not state*. STAR's
    `--readFilesCommand zcat` was justified by "TrimGalore emits `.fq.gz`", and one goal edit
    removes TrimGalore while the flag survives, its stated justification naming a module that
    is not in the pipeline. Stating the premise about the *reads* rather than about a
    neighbour is what makes it stay true when the graph moves.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template: NfTemplate = ""
    why: Why

    @classmethod
    def none(cls) -> "ExtArgs":
        """No baseline flags, said out loud.

        `why` stays required rather than defaulting, so nothing can construct flags without a
        reason. This is the one case where the reason is knowable in advance, and naming it
        means "this module needs no baseline arguments" is an answer in the artifact rather
        than an empty string a reader has to interpret.
        """
        return cls(why=_no_flags_why())

    @model_validator(mode="before")
    @classmethod
    def _accept_a_bare_template(cls, data: object) -> object:
        """`ext_args: "--readFilesCommand zcat"` still parses.

        Same split as `Constraints._accept_mapping`: the ergonomic form somebody writes and
        the safe representation the artifact keeps are different decisions. A contract that
        states only the flags materialises with a reason saying so — greppable, and honest
        about being a gap rather than silently looking like an answer.
        """
        if isinstance(data, str):
            return {
                "template": data,
                "why": {
                    "tier": Tier.STRUCTURAL,
                    "source": ValueSource.RESOLVER,
                    "reason": "declared by the contract with no stated reason",
                    "for_value": data,
                },
            }
        return data


class CallArg(BaseModel):
    """One positional input of the process.

    Mirrors `NfInput`'s three shapes written out, with **no positional shorthand**: root G's
    rule is that a file reads one way, and `call:` is where a second reading produces a
    silently miswired pipeline rather than a parse error.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ports: list[PortName] = Field(default_factory=list)
    literal: ParamValue = None
    empty_width: int | None = None
    from_setting: PortName | None = None
    """The name of the `settings[]` entry whose value fills this position. `via: positional`.

    Carried on the artifact rather than resolved at emit, for the reason everything else here
    is: `mendel emit` runs with no registry and cannot ask a contract which parameter belongs
    in slot 3. Audit A91.
    """
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

    model_config = ConfigDict(extra="forbid", frozen=True)

    port: PortName
    source: EdgeRef | None = None
    """`<node>.<port>` when an upstream step produces it.

    Two fields rather than one string with two shapes. The spec drafted this as a single
    `from:` carrying either `trimgalore.reads` or `channel:annotation.gtf`, and that cannot be
    an `EdgeRef` — its validator requires two Groovy identifiers, which `channel:annotation.gtf`
    is not. Encoding a union in a string is also root G's problem: a field that reads two ways.
    """
    channel: ChannelName | None = None
    """The entry channel this port reads, when nothing upstream produces it.

    **A `ChannelName` since Plan 5B; it was a `TypeId`.** That is the change that makes two
    same-type inputs *addressable*: a port naming its source by type cannot distinguish the
    liver annotation from the reference one, so `pipeline.yml` could not express what the
    canvas was already drawing. `MD0227` refuses a name no channel declares.
    """
    gather: bool = False
    """Whether this port consumes the **whole channel in one invocation** — `.collect()`.

    From the contract's `cardinality: "*"`, and materialised here so emission needs no registry.
    `False` is one item per invocation, which is what every port was.

    **MULTIQC is why it exists.** It consumes `qc.report` from every sample, and without this
    the emitted workflow says `MULTIQC(ch_qc_report)` — one invocation per sample, producing N
    reports where the point of the tool is to produce one.

    A `bool` rather than the contract's `Cardinality`, because the artifact records what was
    *decided* rather than the vocabulary the decision was expressed in — the same reason
    `Step.presence` is a tier and not a rule. A third cardinality would arrive here as a
    different field, which is the right amount of friction.
    """

    states: list[StateName] = Field(default_factory=list)
    """Sorted at materialisation. `IREdge.states` is a `frozenset`, and a set has no stable
    order — `digest_of` hashes the JSON, so this must not be one."""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "StepInput":
        if (self.source is None) == (self.channel is None):
            raise ValueError(
                coded("MD0215", f"input {self.port} must name exactly one of `source` or `channel`")
            )
        return self


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NodeId
    module: ModuleRef
    process: NfIdentifier
    include: NfPath
    why: Why
    """Why **this contract** fills the step. See `exists` for why the step is here at all."""

    presence: Why | None = None
    """Why the step exists, as distinct from which contract fills it. A113.

    Named for the effect that decides it — `effect: presence` in a rule — so the field a
    reader finds in the artifact and the word they would write in a rule are the same word.

    Two questions that were one field, and the tier is what made the conflation visible: a
    module chosen because it was the only candidate reported tier 1 — *"no choice exists,
    inputs force it"* — when what forced it was the contents of the registry. The presence of
    a sorter genuinely is forced, by featureCounts asking for a coordinate-sorted BAM; which
    sorter was never forced at all.

    A reader deciding whether a step can be removed is reading this one, and until now the
    artifact answered a different question in the same place.

    `None` for a document written before Plan 1.15 — an archived pipeline cannot answer, and
    requiring it would assert the reason is *missing* rather than *never recorded*. That is
    Plan 1.14 Task 0's lesson, applied on arrival rather than after a fixture caught it.
    """
    ext_args: ExtArgs = Field(default_factory=lambda: ExtArgs(why=_no_flags_why()))
    """Flags the module always needs, from its contract, **and why it needs them**.

    Still not a `Setting` — nothing resolved it and no decision was made — but that is an
    argument about its *tier*, not about whether it has a reason. It carried none at all
    until A82, which is how STAR's `--readFilesCommand zcat` reached `nextflow.config`
    justified by a sentence about a module one goal edit removes.

    Carried rather than looked up because emission must not need the registry, and composed
    *before* the resolved settings so a contract's baseline cannot be reordered by a value
    someone answered.
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
                coded("MD0212", f"step {self.id} declares {', '.join(repeated)} more than once")
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
                coded(
                    "MD0208",
                    f"step {self.id} routes {' and '.join(who)} to ext.{key.value}, which "
                    f"takes one value — a second writer silently wins. `mendel explain MD0208`.")
            )
        return self


class Scope(StrEnum):
    """How many times a channel delivers, relative to the run.

    ═══ WHY THIS DECIDES WHETHER A PIPELINE IS CORRECT ═══════════════════════════════════════

    A Nextflow process with several **queue** inputs runs as many times as the **shortest** one.
    Every entry channel was a queue, so a reference genome — one item — capped a whole run: with
    twenty-four samples `STAR_ALIGN` ran **once** and twenty-three were silently dropped. No
    error, no warning, a green gate and a counts matrix for one sample.

    Nobody saw it because the stub profile globs **one** sample pair, so N = 1 and the shortest
    channel is every channel. The bug is invisible to the only end-to-end test that runs a tool.

    ═══ EXACTLY TWO MEMBERS, AND THE THIRD IS REFUSED IN WRITING ═════════════════════════════

    **There is no `GROUP` scope.** Every case for one — per-batch adapters, per-lane references —
    is expressible as a `SAMPLE` channel with a column that groups, and a scope for it would put
    a *join strategy* into the vocabulary, where the pipeline that has to perform the join cannot
    see it. A type would be asserting how two channels combine, which is not a fact about the
    type.

    If a real case appears it arrives as a new member with an argument written here, the way
    `wiener_core.series.Kind` gained exactly two and refused a third.
    """

    RUN = "run"
    """One for the whole run: a reference genome, an annotation, an index.

    Emitted as a **value channel**, which Nextflow may consume any number of times. That is the
    fix — a queue of one item is consumed once and then the process stops."""

    SAMPLE = "sample"
    """One per sample. Emitted as a queue, which is what makes the process run per sample."""


class Channel(BaseModel):
    """What the laboratory supplies, and the measured facts that ride with it.

    **A channel has a name and a param since Plan 5B**, and the reason is spec §0's one
    sentence: *a channel's identity and its cardinality were properties of the TYPE, not of the
    pipeline.* `entry_channel: "…params.gtf…"` in a type file fused three pipeline decisions
    into one string, and the first of them is why the spine's three `annotation.gtf` consumers
    were one hole nobody could address.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ChannelName
    """This pipeline's own id for the channel — `gtf`, `gtf_2`, `reads`.

    **Derived, never typed.** *"Yes it's a label, does not change the actual keys"* — a person's
    words reach `DraftLabel` and stop there. The derivation is the type id's last segment, with
    `_2`, `_3` on collision: `qc.report` and `multiqc.report` both end in `report`, which
    `_channel_name`'s docstring already recorded costing two ports the same channel silently.
    A derived value that can collide needs a check rather than a convention, so `MD0226`
    refuses a pipeline whose channel names are not unique.
    """
    param: NfIdentifier
    """The hole this reads: `params.<param>`.

    **Separate from `name`, and `fastq.reads` is why.** Every other shipped type reads
    `params.<last segment>`; that one reads `params.input` and always has. Collapsing the two
    fields would rename it inside a phase that is supposed to change no behaviour, and would
    dissolve the ambiguity spec §12.1 says phase 5 must solve.
    """
    scope: Scope = Scope.SAMPLE
    """Whether this channel delivers once for the run or once per sample.

    **Defaulting to `SAMPLE` is deliberate and is the conservative choice.** A sample-scoped
    channel emits as a queue, which is what every channel was before this field existed — so a
    type that says nothing behaves exactly as it did, and the change is opt-in per type rather
    than a silent reinterpretation of every registry in the world.
    """

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
                coded("MD0211", f"channel {self.type_id} declares params {sorted(self.params)} but "
                f"its expression references {referenced}. `params:` names what `expression:` "
                f"reads; edit whichever of the two is wrong.")
            )
        return self


class RegistryProvenance(BaseModel):
    """Which registry built this. **Provenance, not a dependency of `emit`.**"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layers: list[LockedLayer] = Field(default_factory=list)
    displaced: list[Displacement] = Field(default_factory=list)
    """What an overlay replaced, across every kind of declared data. Wider than the
    `shadowed` it replaced, which covered contracts alone."""
    unverified: list[ContractId] = Field(default_factory=list)



class AiPoint(StrEnum):
    """The three declared runtime AI points. Invariant 3 says there are exactly these.

    Adding a fourth is not a schema change to wave through — it is a change to invariant 3,
    and `tests/test_ai_provenance.py` asserts this list so somebody has to say so out loud.
    """

    PROMPT = "prompt"
    """Prompt → goal extraction. The user corrects the result before anything runs."""
    TIER_4 = "tier-4"
    """Resolution of an ambiguity the ladder could not settle. Always flagged (invariant 6)."""
    REPAIR = "repair"
    """Compiler repair, bounded to three attempts. Patches the IR, never the `.nf` text."""


class AiProvenance(BaseModel):
    """What could have been consulted for this build, and what was. A130.

    **`available` is the field that makes "no model" mean something.** `used` is derivable from
    the decisions; `available` is a fact about how the build was *configured* — which AI points
    had an adapter — and it is the one a reader cannot get any other way. Both empty is a
    positive statement: nothing was wired to a model, so nothing could have been consulted.

    Without it, the only evidence was `source: resolver` on every value, which is the
    resolver's claim about itself. Round three recorded that `Resolution.source` can be set
    untruthfully by any resolver, including a future model adapter, and put it on the same
    standing as `confidence` and `reason`.

    **`None` is not `[]`.** `None` means the file predates the question — a `version: 3`
    artifact, written when nothing asked. `[]` means somebody looked and there was nothing
    wired. Reading the first as the second would invent a statement nobody made, and `MD0225`
    would then enforce it. That is `MD0223`'s lesson (`for_value`) one field over, and it is
    why this is a nullable list rather than a list with an empty default.

    **The limit, stated here rather than implied.** This proves the negative and not the
    positive. A build with an adapter configured *will* say so; a model-backed build whose
    adapter writes `source: resolver` on every value is indistinguishable from a deterministic
    one. A130 closes in the direction that can be checked, and the other direction needs the
    adapter to be honest — which no field can make it. A field that implied more than that
    would be worse than no field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    available: list[AiPoint] | None = None
    """Which of the three declared points had an adapter. `[]` = none were wired."""
    used: list[AiPoint] | None = None
    """Which actually answered. A subset of `available`, and empty whenever that is."""


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
    def _migrate(cls, data: object) -> object:
        """Every version branch, applied in ascending order. **One validator, on purpose.**

        Pydantic runs several `mode="before"` model validators bottom-up, so two of them are
        ordered by where they sit in the class body — which is invisible, and got this wrong on
        the first attempt: the 5 → 6 branch stamped `version: 6` and the 1 → 2 branch, which
        guards on `version < 2`, then declined to run. A version-1 document stopped loading, and
        the error named a missing `why` three types away from the cause.

        A list read top to bottom cannot have that bug. Add a branch by appending to it.
        """
        if not isinstance(data, dict):
            return data
        for migration in (cls._v1_to_v2, cls._v5_to_v6):
            data = migration(data)
        return data

    @classmethod
    def _v1_to_v2(cls, data: dict) -> dict:
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
        if data.get("version", SCHEMA_VERSION) >= 2:
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

    @classmethod
    def _v5_to_v6(cls, data: dict) -> dict:
        """Schema 5 → 6. A channel gains a `name` and a `param`; a port names one.

        ═══ IT IS A SPELLING, NOT A DECISION, AND THAT IS THE WHOLE ARGUMENT ══════════════════

        A version-5 file has **one channel per type** — `goal_of` deduplicated by `type_id` and
        `StepInput.channel` *was* a `TypeId`. So `annotation.gtf` → `gtf` restates what the file
        already said; nothing is chosen, and the mapping is total and unambiguous.

        Spec §12.2 asks the migration to write a `Why` saying it decided, so that `upgrade`
        **replays** rather than re-derives. That is exactly right for **scope**, which phase 4
        adds: a v5 file has no scope on any channel, taking the type's default is a genuinely
        new decision, and a decision appearing in a pipeline nobody re-decided is what replay
        exists to prevent.

        **A name is not that.** Recording a `DecisionRecord` for a rename would put a decision
        nobody made into the artifact — §12.2's own failure mode, arriving from the other side —
        and `mendel explain` would owe an answer for a question that was never open. What the
        property needs instead is that the migration and a fresh derivation *cannot* disagree,
        and they cannot because they are the same two functions: `materialise._stem` and
        `materialise._unique`, in the same `sorted(type_id)` order over the same channel list.

        `test_a_migrated_v5_pipeline_upgrades_to_the_same_nextflow` is that claim as a test,
        and it is the phase's real check. Phase 4 owes the `Why`.

        **`param` comes out of the expression, not out of the name.** A v5 `entry_channel` is a
        literal — `Channel.fromPath(params.gtf, …)` — and `params:` beside it already lists what
        it references, put there by `MD0211` and checked on every load. So the param a migrated
        channel reads is the one the file itself records, which is how `fastq.reads` keeps
        `params.input` across the migration rather than being renamed by a derivation.
        """
        if data.get("version", SCHEMA_VERSION) >= 6:
            return data

        from comeni_core.artifact import materialise

        data = dict(data)
        # **Two counters, exactly as `_channels` uses two.** One shared set gave
        # `annotation.gtf` the param `gtf_2`: the name took `gtf` and the param, the same word
        # for the same channel, found it taken. A name and a param are different namespaces and
        # only a cross-channel collision is one.
        #
        # It was written with one set here *after* the same bug had been found and fixed in
        # `_channels` — the two are the same arithmetic in two places, which is why
        # `test_the_migration_names_channels_the_way_a_fresh_build_does` compares them against
        # each other rather than each against a literal.
        names: dict[str, None] = {}
        params: dict[str, None] = {}
        named: dict[str, str] = {}
        channels = []
        # Sorted by type id, which is the order `_channels` assigns in — so a migrated file and
        # a rebuilt one number a collision the same way round.
        for channel in sorted(
            data.get("channels") or [], key=lambda c: c.get("type_id", "")
        ):
            type_id = channel.get("type_id", "")
            name = materialise._unique(materialise._stem(type_id), names)
            # One param per v5 channel in every file this can be handed; the fallback keeps a
            # hand-written fixture with no `params:` loadable rather than raising an IndexError
            # from inside a migration, where a stack trace explains nothing.
            declared = list(channel.get("params") or [])
            param = materialise._unique(
                declared[0] if declared else materialise._stem(type_id), params
            )
            named[type_id] = name
            channels.append({**channel, "name": name, "param": param})
        data["channels"] = channels

        data["steps"] = [
            {
                **step,
                "inputs": [
                    item
                    if item.get("channel") is None
                    # `.get(…, …)` rather than `[…]`: a port naming a type no channel declares
                    # is a broken v5 file, and `MD0227` is a better place to say so than a
                    # `KeyError` raised while migrating it.
                    else {**item, "channel": named.get(item["channel"], item["channel"])}
                    for item in step.get("inputs") or []
                ],
            }
            for step in data.get("steps") or []
        ]
        data["version"] = SCHEMA_VERSION
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
    ai: AiProvenance = Field(default_factory=AiProvenance)
    """Which of the three declared AI points were reachable for this build, and which
    answered. A130. Defaults to *stating nothing*, which is what a file predating the
    question means; `Pipeline.of` records `[]`/`[]`, which is a measurement."""
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
                coded(
                    "MD0207",
                    f"this pipeline.yml declares version {self.version}, and this Mendel "
                    f"understands version {SCHEMA_VERSION}. Upgrade Mendel; do not edit the "
                f"version down, which would only move the failure somewhere less obvious.")
            )
        ids = [step.id for step in self.steps]
        repeated = sorted({name for name in ids if ids.count(name) > 1})
        if repeated:
            raise ValueError(
                coded("MD0212", f"two steps share the id {', '.join(repeated)}. A step id is what "
                f"`inputs[].source` points at, so a duplicate makes the wiring ambiguous.")
            )
        # A130. `== []` and not falsy: `None` means the file predates the question and makes
        # no claim, so it cannot contradict one. Only an explicit "nothing was wired" can.
        if self.ai.available == []:
            claimed = sorted(
                f"{step.id}.{setting.name}"
                for step in self.steps
                for setting in step.settings
                if setting.why.source is ValueSource.MODEL
            )
            if claimed:
                raise ValueError(
                    coded(
                        "MD0225",
                        f"{', '.join(claimed)} record that a model settled them, and this "
                        "build records that no AI point was available. One of the two is false. "
                    "`ai.available: []` means nothing was wired to a model, so nothing could "
                    "have been consulted.")
                )
        # ═══ MD0226 AND MD0227 — Plan 5B §2.2 ═══════════════════════════════════════════════
        #
        # **A derived value that can collide needs a check, not a convention.** A channel's
        # name is derived from its type id's last segment, which is not injective: `qc.report`
        # and `multiqc.report` both end in `report`, and `_channel_name`'s own docstring
        # recorded that collision costing two ports the same channel *silently*.
        # `materialise._unique` suffixes them; this refuses the file if two ever come out equal
        # anyway, so the derivation cannot regress into the bug it replaced.
        names = [channel.name for channel in self.channels]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(
                coded(
                    "MD0226",
                    f"two channels share the name {', '.join(repeated)}. A channel name is what "
                    f"`inputs[].channel` points at and what becomes `ch_{repeated[0]}` in the "
                    f"workflow, so a duplicate feeds two ports from one channel and drops the "
                    f"other. `mendel explain MD0226`.",
                )
            )
        declared = set(names)
        dangling = sorted(
            {
                f"{step.id}.{item.port} -> {item.channel}"
                for step in self.steps
                for item in step.inputs
                if item.channel is not None and item.channel not in declared
            }
        )
        if dangling:
            raise ValueError(
                coded(
                    "MD0227",
                    f"{dangling[0]} names a channel this pipeline does not declare. "
                    f"{len(dangling)} port(s) in total. A port reads a channel by NAME since "
                    f"schema 6 — by type before it — so a file hand-edited from an older one "
                    f"names `annotation.gtf` where it now means `gtf`. `mendel explain MD0227`.",
                )
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
                    coded("MD0208", f"step {step.id} routes {', '.join(shadow)} to meta, but a "
                    f"measurement already writes {shadow[0]} into the meta map — the setting "
                    f"would silently overwrite a measured fact. `mendel explain MD0208`.")
                )
        keys = [record.key for record in self.decisions]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            raise ValueError(
                coded(
                    "MD0219",
                    f"two decision records share the key {repeated[0]}. A key names one "
                    f"decision; a duplicate is a corrupt file, and `ReplayResolver` would keep one "
                f"and drop the other's answer in silence. `mendel explain MD0219`.")
            )
        values = self._param_setting_values()
        for record in self.decisions:
            if getattr(record, "kind", None) is not DecisionKind.PARAM:
                continue
            override = record.human_override
            value = values.get(record.key)
            if override is not None and value is not None and override != value:
                raise ValueError(
                    coded(
                        "MD0218",
                        f"{record.key} is answered {value!r} in settings and {override!r} "
                        f"in its decision's human_override — one file, two answers, and emit and "
                    f"upgrade would read different ones. settings[].value is the writable one; "
                    f"remove the human_override or set it equal. `mendel explain MD0218`.")
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
                        coded(
                            "MD0220",
                            f"{key} says source: human, but no decision records a person "
                            f"answering it — its human_override is null or absent. `source: human` "
                        f"clears the review, so it must be backed by the answer it claims.\n"
                        f"  Edit `settings[].value` and leave `source` alone: `upgrade` "
                        f"promotes the answer and sets `source: human` itself. Or restore the "
                        f"source that resolution gave it. `mendel explain MD0220`.")
                    )
        return self

    def _param_setting_values(self) -> dict[str, ParamValue]:
        """`{step.id}.{setting.name}` → value, the key a `ParamDecision` carries."""
        return {
            f"{step.id}.{setting.name}": setting.value
            for step in self.steps
            for setting in step.settings
        }

    def _param_setting_reasons(self) -> dict[str, str]:
        """The same keys → the reason written beside each value.

        A hand-edited reason travels the route a hand-edited value already does. Anything
        else and the answer survives `upgrade` while the sentence explaining it does not,
        which is A77 exactly.
        """
        return {
            f"{step.id}.{setting.name}": setting.why.reason
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
        reasons = self._param_setting_reasons()
        replayable = []
        for record in self.decisions:
            value = values.get(record.key)
            if (
                getattr(record, "kind", None) is DecisionKind.PARAM
                and record.human_override is not None
                and reasons.get(record.key, "") not in ("", record.reason)
            ):
                # Already overridden, and the reason beside the value has since been edited.
                # The promotion branch below only fires the *first* time a value is answered,
                # so without this a reason written after the answer — the ordinary order,
                # since `upgrade` is what reveals the machine text worth replacing — would
                # never reach the record. A77.
                replayable.append(
                    record.model_copy(
                        update={"override_reason": reasons[record.key]}
                    )
                )
            elif (
                getattr(record, "kind", None) is DecisionKind.PARAM
                and record.human_override is None
                and value is not None
                and value != record.chosen
            ):
                # The reason travels with the answer. A person who edits the value and the
                # sentence beside it has written both; carrying only the first is how
                # `upgrade` came to replace *"our sequencer is an Illumina NovaSeq X; lab SOP
                # BIOINF-014"* with "selected the first of 1 candidates without judgement".
                # Only when it differs from the resolver's own text, which is not a reason a
                # person wrote. A77.
                written = reasons.get(record.key, "")
                replayable.append(
                    record.model_copy(
                        update={
                            "human_override": value,
                            "override_reason": (
                                written if written != record.reason else ""
                            ),
                        }
                    )
                )
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
        """The **only** validating constructor. The body lives in `materialise.of`.

        Kept here rather than exposed as a bare function because
        `tests/test_construction.py` asserts nothing else builds a `Pipeline`, and that guard
        names this spelling. The argument for why `goal` is keyword-only and required moved
        with the body.
        """
        # Imported inside the call, not at the top: `materialise` imports `Pipeline` to
        # build one, so a module-level import here is a cycle. This is the only such import
        # in the package and it is here rather than the other way round because the models
        # are what everything else depends on.
        from comeni_core.artifact import materialise

        return materialise.of(
            ir, registry, vocab, measurements=measurements, layers=layers, goal=goal
        )
