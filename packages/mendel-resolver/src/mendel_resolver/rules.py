"""Tier 3: declared decision tables matched against measured data.

A miss is not an escalation to a model. It is a demotion to tier 4.

The format is grouped: one block per decision, rows underneath. The three strandedness
rules used to be three entries repeating their subject and citation; a reviewer should read
the justification once and then read the branches — and grouping is also what lets them
notice a *missing* branch, which flat rules actively hide.

Every table is validated against the registry, the vocabulary and the measurements at load.
That is the load-bearing part: `subject` used to be an unvalidated free string, and two of
the five rules shipped in `examples/` had never once executed.
"""

import operator
import re
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal

from comeni_core import yaml_strict
from comeni_core.layered import (
    DeclaredKind,
    Displacement,
    Kind,
    Layer,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.marks import ContractId, LayerName, MeasurementId, ParamValue, RoleName
from comeni_core.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.premise import PremiseRecord
from comeni_core.profile import DataProfile
from comeni_core.registry import Registry
from comeni_core.tiers import Tier
from comeni_core.vocabulary import Vocabulary
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mendel_resolver.predicates import matches, tier_of_row

_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

_ORDERED = {MeasurementKind.INTEGER, MeasurementKind.NUMBER}


class RuleValidationError(ValueError):
    """Raised when a rule table cannot fire against the registry it was loaded with."""


def _comparison(expected: ParamValue) -> tuple[str, float] | None:
    """`">= 70"` as (symbol, literal), or None if this is an equality test.

    Written as one function because the load-time validator and the runtime matcher must
    agree on what counts as a comparison. Two copies of this predicate is how a rule
    passes validation and then fails to fire.
    """
    if not isinstance(expected, str):
        return None
    symbol, _, literal = expected.partition(" ")
    if symbol not in _OPS:
        return None
    try:
        return symbol, float(literal)
    except ValueError as exc:
        raise RuleValidationError(
            f"{expected!r} looks like a comparison but {literal!r} is not a number. "
            f"Write it as `\"{symbol} 70\"`, with a space."
        ) from exc


class Effect(StrEnum):
    """What a decision changes. Spec §4.1.

    Three, because a rule about *whether a step exists* and a rule about *which tool fills
    it* are different claims and the shipped format could only spell the first as the second:
    `producer_of: fastq.reads` with `then: null` was the way to say "do not trim". That reads
    as a null pointer rather than as a sentence about a pipeline.
    """

    PRESENCE = "presence"
    PARAM = "param"
    IMPLEMENTATION = "implementation"


class DecisionTarget(BaseModel):
    """What a decision decides — an effect on a **role**, never on a type. Spec §4.1.

    A119 and A123 are one defect from two sides. The old target admitted `{param: X}` and
    `{producer_of: T}`, so a rule about duplicate handling and a rule about which aligner to
    use both keyed on `alignment.bam`, and `Policy.REPLACE` resolved that collision by
    deleting one of them — silently, at exit 0. Keying on `(effect, role[, name])` is what
    makes the two rules different keys rather than the same one.
    """

    model_config = ConfigDict(extra="forbid")

    effect: Effect
    of: RoleName
    name: str | None = None
    """The parameter, for a `param` effect. Meaningless for the other two."""

    when_implementation: list[ContractId] = Field(default_factory=list)
    """Narrow a `param` effect to the implementations that declare it.

    `star_ignore_sjdbgtf` is STAR's alone, so a rule deciding it for the whole `alignment`
    role sets a value that is dead whenever HISAT2 wins — issue #10's deadness, arriving
    through the rule format rather than through a contract. Naming the implementations is the
    author saying which ones the value is *for*, and `MD0308` is what makes them say it.
    """

    def key(self) -> str:
        return f"{self.effect}:{self.of}" + (f":{self.name}" if self.name else "")


class DecisionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    when: dict[str, ParamValue] = Field(default_factory=dict)
    then: ParamValue = None
    because: str | None = None
    cite: str | None = None

    def matches(self, profile: DataProfile) -> bool:
        for measurement_id, expected in self.when.items():
            actual = profile.get(measurement_id)
            if actual is None:
                return False
            comparison = _comparison(expected)
            if comparison is not None:
                symbol, literal = comparison
                if not _OPS[symbol](actual, literal):
                    return False
            elif actual != expected:
                return False
        return True


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decides: DecisionTarget | list[DecisionTarget]
    rows: list[DecisionRow] = Field(default_factory=list)
    because: str | None = None
    cite: str | None = None

    def targets(self) -> list[DecisionTarget]:
        """A decision landing on two tools is **one** choice with one premise and one citation.

        Spec §4.2. `star_ignore_sjdbgtf` depends on how the index was built: supplying splice
        junctions at index time and ignoring them at align time is a single call about where
        the annotation is used, spelled as two flags on two tools.

        Modelling it as two decisions would make the second read the first, and decisions
        reading decisions is what this format refuses — it buys evaluation order, the
        possibility of a cycle, and the loss of `build_premises`' single pass. One block also
        means a reviewer reads the justification once, which is why the format is grouped at
        all.
        """
        return self.decides if isinstance(self.decides, list) else [self.decides]

    def key(self) -> str:
        """One `stack()` key for the whole decision, because it replaces as a whole.

        An overlay replacing a two-target decision has to decide the same two things: half a
        replacement would leave the base's other half in force under a justification the
        overlay never wrote. That the composite key lets a *different* decision land on one of
        those targets is a real gap and is closed after assembly — see
        `_no_target_is_decided_twice`, and the test that reaches it.
        """
        return "+".join(sorted(target.key() for target in self.targets()))


class Fired(BaseModel):
    """A row that matched, and everything a caller needs without consulting the table again.

    A22's shape: `RuleTable` recorded provenance correctly and the one caller that had to
    remember to read it did not. The answer carries its own evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect: Effect
    role: RoleName
    name: str | None = None
    value: ParamValue = None
    tier: Tier = Tier.DATA_PROFILED
    because: str = ""
    cite: str = ""
    axis_because: str = ""
    """The block's justification — the methodology, kept apart from the row's choice.

    One field carried both and printed the axis citation as the row's reason, so the shipped
    registry said HISAT2 was chosen because of the paper describing STAR. A79, A107.
    """

    def key(self) -> str:
        return f"{self.effect}:{self.role}" + (f":{self.name}" if self.name else "")


class Aggregate(BaseModel):
    """Reduce a per-sample measurement to one value. Spec §3.2.

    `over` is `cohort` and nothing else, and it is written out rather than assumed because
    the cohort-versus-sample question is the one the shipped format could not even ask —
    `read_length: ">= 70"` against a cohort of three has no defined meaning, and the format
    gave a rule author no way to say which they meant.
    """

    model_config = ConfigDict(extra="forbid")

    measurement: MeasurementId
    over: Literal["cohort"]
    using: Literal["max", "min", "mean"]


class Derivation(BaseModel):
    """A fact the registry works out, rather than one a tool measured. Spec §3.1.

    A derivation naming a **declared measurement** is a fallback: it may fill a gap and may
    never overwrite. That asymmetry is the whole of it. R15 — *"infer strandedness where
    nothing measured it"* — is unwritable in the shipped format because `when` can only read
    a measurement that is present, so the row validates and can never fire (A122); and a
    version that could fire without the asymmetry would be worse, because it would resolve a
    pipeline against a default while the profile printed beside it named the measured value.

    `kind` is declared rather than inferred from `then`, for the same reason a measurement
    declares one: it says what the fact may hold before any row has produced a value, which
    is what Task 10's type check over `then` will read.
    """

    model_config = ConfigDict(extra="forbid")

    fact: MeasurementId
    kind: MeasurementKind
    rows: list[DecisionRow] = Field(default_factory=list)
    aggregate: Aggregate | None = None
    because: str | None = None
    cite: str | None = None

    @model_validator(mode="after")
    def _can_fire(self) -> "Derivation":
        """Exactly one of `rows` and `aggregate`, and never neither.

        A derivation that can produce nothing is A122's own shape, one layer down: it loads
        clean, contributes nothing, and reads to a reviewer as a fact the registry supplies.
        Refused at load rather than reported at resolution, because by resolution the fact is
        simply absent and nothing can tell an empty derivation from one that was never
        written. Spec §5.

        Both is refused rather than ordered, because an order here would be a rule nobody
        reading the file could see — invariant 8's argument, one layer down again.
        """
        if bool(self.rows) == bool(self.aggregate):
            has = "both `rows` and `aggregate`" if self.rows else "neither `rows` nor `aggregate`"
            raise ValueError(
                f"MD0304: derivation {self.fact!r} declares {has}, and needs exactly one. "
                f"A derivation that can produce nothing still reads as a fact the registry "
                f"supplies; one that could produce two would resolve by a precedence no "
                f"reader of the file can see."
            )
        return self


def _joined(*parts: str | None) -> str:
    """A sentence and its citation, in one line, without `one.; Kim et al.`

    The trailing stop is dropped from every part but the last, because a rule author writes
    prose that ends in a full stop and a citation that does not, and the two meet here rather
    than in the file either of them was written in.
    """
    kept = [part.strip() for part in parts if part and part.strip()]
    return "; ".join(
        part.rstrip(".") if index < len(kept) - 1 else part
        for index, part in enumerate(kept)
    )


class Pin(BaseModel):
    """A rule fired, and everything that follows from it — including where it came from.

    A22: `RuleTable` recorded `layer_of` and `displaced_layer` correctly, and
    `router._choose` never read them, so a rule-pinned reroute produced an IR asserting
    the *base* layer had decided. Recording a fact is not enough if consulting it is
    optional, so the fact travels with the answer rather than beside it. The caller cannot
    take the value without being handed the provenance in the same object.
    """

    model_config = ConfigDict(extra="forbid")

    value: ParamValue
    """The pinned contract id, or the parameter value. `then`, resolved."""
    from_layer: LayerName
    """The layer whose *rule block* decided. Not where the chosen contract was found —
    those differ, and the difference is the whole of A22."""
    displaced_layer: LayerName | None = None
    decision: Decision
    row: DecisionRow
    premise: list[PremiseRecord] = Field(default_factory=list)
    """The facts this row actually read, in `when` order.

    On the `Pin` rather than looked up by the caller, for the reason A22 gives about every
    other field here: a fact the caller must remember to fetch is a fact one of them will
    not. `reason_line` needs it and so does `Why`.
    """

    def because(self) -> str:
        """Why **this row** won — the specific choice, never the axis.

        Was `row.cite or decision.cite or row.because or decision.because`, under a docstring
        that said *"row before block"*. Two bugs in one line, and each was found by a
        different reviewer from a different direction:

        - **The precedence was cite-first, not row-first** (A107). A `cite` shadowed a
          `because`, so the registry's only plain-English explanation of its only tier-3
          decision never reached the artifact. A reader got a DOI where a sentence belonged.
        - **A block `cite` answers a different question** (A79). It justifies the decision
          *axis* — "read length determines which aligner is appropriate", for which Dobin et
          al. is a fair citation — and it was printed as the reason for a *row*. So the
          shipped registry said HISAT2 was chosen because of the paper describing STAR,
          reachable by changing one number in `examples/rnaseq-goal.yml`.

        The second is why this is not a reordering. The field was answering two questions, so
        it becomes two: this one, and `axis_because` below.

        **A citation and a sentence are joined, never chosen between.** Preferring one was the
        A107 half of this bug, and writing `row.because or row.cite` here would have repeated
        it exactly one level down — the sentence would have shadowed the row's own paper
        instead of the reverse. A reader wants the claim and the evidence for it.
        """
        return _joined(self.row.because, self.row.cite)

    def reason_line(self, matched: object = None) -> str:
        """`rule <key>[ where <premises>][: <row justification>]`, with no dangling colon.

        **`matched` is ignored and kept for callers.** It used to be the raw `when` mapping,
        and the shipped artifact read

            reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: …'

        — a Python dict repr embedded in YAML with doubled quotes, reporting the *predicate*
        and never the value. A reader learned the rule tested `>= 70` and never learned that
        `read_length` was 150, or that anything had measured it. The premise is the one thing
        tier 3 asks a reviewer to check, and spec §6.1 says no structured value is a reader's
        only account of itself.

        On `Pin` rather than in `resolve`, because `router` needs it too and importing
        `resolve` from `router` is a cycle — and because every input it formats is already
        here. A row may be justified entirely by its block (a one-row rule often is) and
        `MD0301` allows that, but `rule param:strandedness: ` with nothing after the colon
        reads as a truncation rather than as an absence, which is half of what A78 was.
        """
        head = f"rule {self.decision.key()}"
        if self.premise:
            head = f"{head} where " + "; ".join(record.prose() for record in self.premise)
        because = self.because()
        return f"{head}: {because}" if because else head

    def axis_because(self) -> str:
        """Why this decision is made this way **at all** — the block's justification.

        Kept separate rather than concatenated, because a reader wants to know both and to be
        able to tell which is which: the axis is the methodology, the row is the choice made
        under it. A79, A107.
        """
        return _joined(self.decision.because, self.decision.cite)


_GOAL_FACTS = frozenset({"required_states"})
"""Premises the goal supplies rather than any measurement. Kept beside the rule validator
because this is the list a `when` key is checked against; `premises.py` is where they are
built. Two places, one fact — which is why the name is shared rather than the literal."""


def _key_of(entry: "Derivation | Decision") -> str:
    """One key space for both layers, namespaced. Spec §2.1.

    `stack()` has one key space per kind and `Policy.REPLACE` applies **per key**, so an
    overlay replacing a derivation leaves the decision beside it untouched — which is what
    lets both live in `rules/` without a second `DeclaredKind`.
    """
    if isinstance(entry, Derivation):
        return f"derive:{entry.fact}"
    return entry.key()


class RuleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[Decision] = Field(default_factory=list)
    derivations: list[Derivation] = Field(default_factory=list)
    """The premise layer's half of `rules/`, in key order. Read by `build_premises`."""

    layer_of: dict[str, str] = Field(default_factory=dict)
    """Decision key -> the layer whose block is in force. Audit A15.

    Deliberately *not* a field on `Decision`. A `Decision` is parsed straight out of a
    layer's YAML, so a provenance field there would be a provenance field a layer can
    write for itself — a rule file claiming `from_layer: comeni-registry-examples` while
    sitting in an overlay. Provenance must be recorded by the loader, which knows, rather
    than by the file, which can lie. Same reasoning that keeps `layer_of` off
    `ModuleContract`.
    """

    displaced_layer: dict[str, str] = Field(default_factory=dict)
    """Decision key -> the *lowest* layer whose block this one replaced, if any.

    `by_target[key] = decision` replaced a whole block and recorded nothing, so a tier-3
    parameter decided by a lab's overlay was indistinguishable from one decided by the
    public registry. Invariant 11 says all four kinds of declared data stack; only
    contracts were being watched. Audit A15.

    This is the *per-node* record — what `IRNode.selection.displaced_layer` reads. It is not
    the same thing as `displaced`, below: this one answers "which layer decided this key",
    keyed for lookup during resolution; that one is the full `Displacement` a reader audits.
    """

    displaced: list[Displacement] = Field(default_factory=list)
    """The rules kind's contribution to `PipelineIR.displaced`, one shape for all four kinds.

    `RuleTable` kept only `displaced_layer` — a key→name dict for per-node lookup — so when
    `resolve()` assembled `PipelineIR.displaced` off its arguments, rules had no full
    `Displacement` to contribute and a rule overlay reached the published artifact recording
    nothing (A51). The other three kinds already carried this; now the fourth does too, so
    the loader-level list `resolve()` reads is complete without the caller threading anything.
    """

    @staticmethod
    def kind(
        registry: Registry,
        vocabulary: Vocabulary,
        measurements: MeasurementRegistry,
    ) -> Kind[str, Decision]:
        """How rule blocks are found, keyed and stacked.

        Keyed on the decision's *target*, not the file: a laboratory naming its overlay
        `aligner.yml` where the base says `rnaseq.yml` is still replacing that block, and
        keying on filenames would have let both fire with row order deciding.

        A higher layer replaces the whole block, not row by row — a reviewer should read
        one block and see the entire effective decision.
        """

        fillers_by_role = _fillers_by_role(registry)

        def parse(path: Path) -> list[Derivation | Decision]:
            data = yaml_strict.load(path) or {}
            found: list[Derivation | Decision] = [
                Derivation.model_validate(raw) for raw in data.get("derives", [])
            ]
            # Per file, because `MD0309` is about two decisions **in the same layer**: an
            # overlay replacing a block by key is legal and is the whole of invariant 11.
            seen: dict[str, str] = {}
            for raw in data.get("decisions", []):
                decision = Decision.model_validate(raw)
                _validate(
                    decision,
                    path,
                    registry=registry,
                    fillers_by_role=fillers_by_role,
                    measurements=measurements,
                    seen=seen,
                )
                found.append(decision)
            return found

        return Kind(
            DeclaredKind.RULES,
            parse=parse,
            key=_key_of,
            policy=Policy.REPLACE,
        )

    @classmethod
    def of(
        cls, stacked: "Stacked[str, Derivation | Decision]", layers: Sequence[Layer]
    ) -> "RuleTable":
        name_of = {layer.index: layer.name for layer in layers}
        entries = [stacked.entries[key] for key in sorted(stacked.entries)]
        return cls(
            decisions=[e for e in entries if isinstance(e, Decision)],
            derivations=[e for e in entries if isinstance(e, Derivation)],
            layer_of={key: name_of[at] for key, at in stacked.origin.items()},
            displaced_layer={
                record.key: record.displaced_layer for record in stacked.displaced
            },
            displaced=list(stacked.displaced),
        )

    @classmethod
    def load(
        cls,
        layers: Path | Sequence[Path],
        *,
        registry: Registry,
        vocabulary: Vocabulary,
        measurements: MeasurementRegistry,
    ) -> "RuleTable":
        """Load rule blocks across a layer stack. **Layer roots, not `rules/`.**

        The `names` argument is gone with the rest: a `Layer` carries its own name, so
        there is no longer a fact the caller has to forward on the loader's behalf.
        """
        as_layers = layers_of(layers)
        table = cls.of(
            stack(as_layers, cls.kind(registry, vocabulary, measurements)), as_layers
        )
        # After the stack, not inside `parse` — a decision may read a fact a derivation in
        # another file supplies, and a per-file check would refuse a legitimate rule for the
        # accident of which one `stack()` reached first. Same reason `roles.check` runs after
        # the registry is assembled rather than inside `Registry.kind`'s parse.
        table.check_premise_names(measurements)
        return table

    def check_premise_names(self, measurements: MeasurementRegistry) -> None:
        """Every `when` key across the table names a premise something supplies.

        After assembly, not during parse — see `_check_when`. Called by `layers.load`, which
        is the one place that has finished stacking.
        """
        facts = set(measurements.ids()) | set(_GOAL_FACTS)
        facts |= {derivation.fact for derivation in self.derivations}
        for derivation in self.derivations:
            _check_when(
                derivation.rows,
                f"derivation {derivation.fact!r}",
                measurements=measurements,
                facts=facts,
            )
        self._no_target_is_decided_twice()
        for decision in self.decisions:
            _check_when(
                decision.rows,
                f"decision {decision.key()}",
                measurements=measurements,
                facts=facts,
            )

    def _no_target_is_decided_twice(self) -> None:
        """No two decisions in the assembled table land on the same target.

        The gap a composite stacking key opens. A multi-target decision replaces as a whole,
        so its `stack()` key is the whole set — which means a second decision naming only one
        of those targets is a *different* key, stacks happily beside it, and both fire on that
        target. `MD0309`'s per-file check cannot see it and `stack()`'s per-layer check cannot
        see it either, because to both of them these are two different keys.

        Which is A119 again, arriving through the feature added to express one choice on two
        tools. Recorded here rather than fixed by abandoning the composite key, because half a
        replacement is the worse failure: it would leave a base layer's other target in force
        under a justification the overlay never wrote.
        """
        decided_by: dict[str, str] = {}
        for decision in self.decisions:
            for target in decision.targets():
                if target.key() in decided_by:
                    raise RuleValidationError(
                        f"MD0309: two decisions both land on {target.key()!r} — "
                        f"{decided_by[target.key()]!r} and {decision.key()!r}.\n"
                        f"  Only one of them will fire, and which one is not something a\n"
                        f"  reader of either file can work out. Merge them, or narrow one\n"
                        f"  with `when_implementation:`."
                    )
                decided_by[target.key()] = decision.key()

    def _for(self, key: str, premises: "dict[str, object]") -> Pin | None:
        for decision in self.decisions:
            # `key()` is the composite; a two-target decision answers for either of them.
            if key not in {target.key() for target in decision.targets()}:
                continue
            for row in decision.rows:
                if matches(row.when, premises):
                    return Pin(
                        value=row.then,
                        from_layer=self.layer_of.get(decision.key(), ""),
                        displaced_layer=self.displaced_layer.get(decision.key()),
                        decision=decision,
                        row=row,
                        premise=_premises_read(row, premises),
                    )
        return None

    def effects_for(self, premises: "dict[str, object]") -> list["Fired"]:
        """Every effect the table produces against these premises, in key order.

        One `Fired` per *target*, so a decision landing on two tools produces two effects
        carrying one premise and one citation — which is what makes it one choice rather than
        two that happen to agree.
        """
        fired: list[Fired] = []
        for decision in self.decisions:
            row = next((r for r in decision.rows if matches(r.when, premises)), None)
            if row is None:
                continue
            pin = Pin(
                value=row.then,
                from_layer=self.layer_of.get(decision.key(), ""),
                displaced_layer=self.displaced_layer.get(decision.key()),
                decision=decision,
                row=row,
            )
            for target in decision.targets():
                fired.append(
                    Fired(
                        effect=target.effect,
                        role=target.of,
                        name=target.name,
                        value=row.then,
                        tier=tier_of_row(row.when),
                        because=pin.because(),
                        cite=row.cite or decision.cite or "",
                        axis_because=pin.axis_because(),
                    )
                )
        return sorted(fired, key=lambda f: f.key())

    def value_for(
        self,
        roles: Sequence[str],
        param: str,
        premises: "dict[str, object]",
        *,
        implementation: str | None = None,
    ) -> Pin | None:
        """The decided value for `param` on a node filling any of `roles`.

        Takes the node's roles rather than the parameter alone, which is A123's fix at the
        point of use: `star_ignore_sjdbgtf` decided for role `alignment` reaches STAR and
        does not reach a sorter that happens to declare a parameter of the same name.

        Roles are tried in the order the contract declares them, so a contract filling two
        roles decided differently resolves by its own declaration rather than by dictionary
        order. A contract filling two roles that both decide one parameter is a registry
        defect; it is not refused here because the refusal belongs at load, where the message
        can name both decisions.
        """
        for role in roles:
            pin = self._for(f"{Effect.PARAM}:{role}:{param}", premises)
            if pin is not None and _applies_to(pin, implementation):
                return pin
        return None

    def implementation_for(self, role: str, premises: "dict[str, object]") -> Pin | None:
        return self._for(f"{Effect.IMPLEMENTATION}:{role}", premises)

    def presence_for(self, role: str, premises: "dict[str, object]") -> Pin | None:
        return self._for(f"{Effect.PRESENCE}:{role}", premises)


def _premises_read(row: DecisionRow, premises: "dict[str, object]") -> list[PremiseRecord]:
    """The facts this row consulted, in `when` order and with their values.

    In `when` order rather than sorted, because that is the order the rule author wrote and a
    reader comparing the sentence against the table should meet them the same way.

    A key testing `absent` has no premise to record and contributes nothing: there is no
    value, and *"read_length is None, not measured"* would be a sentence about a fact that
    does not exist. Its absence is already what the row says.
    """
    read: list[PremiseRecord] = []
    for fact in row.when:
        premise = premises.get(fact)
        if premise is None:
            continue
        read.append(
            PremiseRecord(id=premise.id, value=premise.value, origin=premise.origin)
        )
    return read


def _applies_to(pin: Pin, contract_id: str | None) -> bool:
    """Whether a narrowed `param` decision reaches this implementation.

    `when_implementation` is checked here as well as at load, and the two checks answer
    different questions: load asks *could this value ever be dead*, and this asks *is it dead
    right now*. Only the second knows which contract won.
    """
    narrowed = pin.decision.decides.when_implementation
    return not narrowed or contract_id is None or contract_id in narrowed


def _computed_over(then: object, measurement_ids: list[str]) -> str | None:
    """The measurement this `then` reads as arithmetic over, or `None` if it is a value.

    `MD0300`. `DecisionRow.then` is emitted **verbatim** — nothing between the rule table and
    `nextflow.config` evaluates it — so `then: "read_length-1"` reached STAR as the literal
    string `read_length-1`, at tier 3, cited to Dobin et al. 2013, and absent from the review
    list. The only thing that ever refused it was `MD0201`, a shell-injection character class
    that permits `-`, and only on the spaced spelling. Audit A118.

    **A substring test is too loose and would be worse than nothing.** `paired` is a declared
    measurement, so `then: "paired-end"` would be refused by one — a legitimate value, killed
    by a check nobody could disable. What makes a string an expression is a measurement
    sitting next to an operator *and a number*, or two measurements combined. That is what is
    tested here, and `test_a118_a_value_that_merely_contains_a_measurement_name_still_loads`
    is the negative that keeps it honest.
    """
    if not isinstance(then, str):
        return None
    named = [m for m in measurement_ids if re.search(rf"\b{re.escape(m)}\b", then)]
    if not named:
        return None
    for measurement in named:
        bounded = rf"\b{re.escape(measurement)}\b"
        if re.search(rf"{bounded}\s*[-+*/]\s*\d", then) or re.search(
            rf"\d\s*[-+*/]\s*{bounded}", then
        ):
            return measurement
    if len(named) > 1 and re.search(r"[-+*/]", then):
        return named[0]
    return None


def _fillers_by_role(registry: Registry) -> dict[str, list[str]]:
    """Which contracts fill each role, across the whole assembled registry.

    Derived rather than declared, because a role's fillers are a fact about the stack and a
    lab's overlay may add one. Computed once per load and threaded, so the answer cannot
    differ between the check that a role is filled and the check that its fillers declare a
    parameter — the two disagreeing is how `MD0308` would refuse a rule that was fine.
    """
    fillers: dict[str, list[str]] = {}
    for contract in registry.all():
        for role in contract.roles:
            fillers.setdefault(role, []).append(contract.id)
    return {role: sorted(ids) for role, ids in fillers.items()}


def _validate_target(
    target: DecisionTarget,
    path: Path,
    *,
    registry: Registry,
    fillers_by_role: dict[str, list[str]],
    seen: dict[str, str],
) -> None:
    """**Structural checks first, justification last.** Order is load-bearing here.

    An earlier arrangement ran the citation check first, so a rule naming a contract that
    fills no role was reported as *"this row needs a cite"* — a diagnostic pointing at the one
    part of the rule that was correct. A refusal has to name the thing that is wrong.
    """
    fillers = fillers_by_role.get(target.of, [])
    if not fillers:
        raise RuleValidationError(
            f"MD0306: {path}, decision {target.key()}\n"
            f"  No contract in this stack fills role {target.of!r}, so this decision can\n"
            f"  never apply.\n"
            f"  Roles that are filled: {', '.join(sorted(fillers_by_role)) or '(none)'}"
        )

    if target.effect is Effect.PARAM:
        if target.name is None:
            raise RuleValidationError(
                f"MD0307: {path}, decision {target.key()}\n"
                f"  A `param` effect decides a named parameter and this one names none.\n"
                f"  Write `decides: {{effect: param, of: {target.of}, name: <parameter>}}`."
            )
        narrowed = target.when_implementation or fillers
        outside = sorted(set(target.when_implementation) - set(fillers))
        if outside:
            raise RuleValidationError(
                f"MD0306: {path}, decision {target.key()}\n"
                f"  `when_implementation` names {', '.join(outside)}, which do not fill role\n"
                f"  {target.of!r}. Fillers of that role: {', '.join(fillers)}"
            )
        declared_by = {
            contract_id: {p.name for p in registry.get(contract_id).params}
            for contract_id in narrowed
        }
        missing = sorted(c for c, names in declared_by.items() if target.name not in names)
        if missing:
            raise RuleValidationError(
                f"MD0308: {path}, decision {target.key()}\n"
                f"  {target.name!r} is not declared by {', '.join(missing)}, which can fill\n"
                f"  role {target.of!r}. The value would be dead whenever one of those wins.\n"
                f"  Narrow with `when_implementation:`, or decide a parameter they all\n"
                f"  declare."
            )
    elif target.name is not None:
        raise RuleValidationError(
            f"MD0307: {path}, decision {target.key()}\n"
            f"  A `{target.effect}` effect decides the role itself and carries no `name`.\n"
            f"  Drop `name:`, or make this a `param` effect."
        )

    if target.key() in seen:
        raise RuleValidationError(
            f"MD0309: {path}, decision {target.key()}\n"
            f"  Two decisions in the same layer both decide {target.key()!r}: this one and\n"
            f"  {seen[target.key()]}.\n"
            f"  A higher layer replaces a whole block by key, so one of these would silently\n"
            f"  displace the other rather than both applying. Audit A119."
        )
    seen[target.key()] = str(path)


def _validate_rows(
    decision: Decision,
    target: DecisionTarget,
    path: Path,
    *,
    registry: Registry,
    fillers_by_role: dict[str, list[str]],
    measurements: MeasurementRegistry,
) -> None:
    if target.effect is Effect.PARAM:
        for row in decision.rows:
            over = _computed_over(row.then, measurements.ids())
            if over is None:
                continue
            raise RuleValidationError(
                f"MD0300: {path}, decision {target.key()}\n"
                f"  `then: {row.then!r}` reads as an expression over {over!r}, and `then` is\n"
                f"  emitted verbatim — the tool would receive the string {row.then!r}.\n"
                f"  Write one row per range with a literal `then`. If the rule genuinely\n"
                f"  needs arithmetic, that is issue #39 and a format change, not a value."
            )
    elif target.effect is Effect.IMPLEMENTATION:
        fillers = fillers_by_role[target.of]
        for row in decision.rows:
            contract_id = str(row.then)
            if contract_id not in fillers:
                known = (
                    "it is not in this stack"
                    if contract_id not in registry.contracts
                    else f"it fills {', '.join(registry.get(contract_id).roles) or 'no role'}"
                )
                raise RuleValidationError(
                    f"MD0306: {path}, decision {target.key()}\n"
                    f"  {contract_id!r} does not fill role {target.of!r} — {known}.\n"
                    f"  Contracts that do: {', '.join(fillers)}"
                )
    elif target.effect is Effect.PRESENCE:
        for row in decision.rows:
            if row.then not in ("present", "absent"):
                raise RuleValidationError(
                    f"MD0307: {path}, decision {target.key()}\n"
                    f"  `then: {row.then!r}` — a presence effect says `present` or `absent`\n"
                    f"  and nothing else. It is a claim about whether the step exists, which\n"
                    f"  is why it reads as English rather than as `then: null`."
                )

    for index, row in enumerate(decision.rows):
        # Tier 2 is "a documented default exists", so its output is value **plus the
        # document**. A row testing no premise positively earns tier 2 by `tier_of_row`, and
        # a `because` alone states the value and asserts the document. A76 and A128 were both
        # that shape — one in a contract default, one in a rule — and this is the rule stated
        # once rather than the pair fixed twice.
        if tier_of_row(row.when) is Tier.CONVENTION and not (row.cite or decision.cite):
            raise RuleValidationError(
                f"MD0313: {path}, decision {target.key()}, row {index}\n"
                f"  This row tests no premise positively, so it exits at tier 2 — a\n"
                f"  documented default. Tier 2 produces `value + citation` and this row has\n"
                f"  neither a row `cite` nor a block one.\n"
                f"  A `because` states the value; a `cite` is the document tier 2 claims."
            )
        if not (row.because or row.cite or decision.because or decision.cite):
            raise RuleValidationError(
                f"MD0301: {path}, decision {target.key()}, row {index}\n"
                f"  This row justifies nothing — no `because` and no `cite`, on the row or\n"
                f"  on the block. It fires at tier 3, whose review level is *advisory*, which\n"
                f"  means 'the machinery worked, check the premise'. A reader given no\n"
                f"  premise cannot. It also emitted a reason ending in a bare colon.\n"
                f"  Add `because:` saying why this answer, or `cite:` naming the evidence."
            )

def _validate(
    decision: Decision,
    path: Path,
    *,
    registry: Registry,
    fillers_by_role: dict[str, list[str]],
    measurements: MeasurementRegistry,
    seen: dict[str, str],
) -> None:
    # Every target, not only the first. A validator that loops over `decides` incorrectly
    # still passes every single-target test there is, which is why `test_both_targets_of_one
    # _decision_are_validated` exists and why it names that in its docstring.
    for target in decision.targets():
        _validate_target(
            target,
            path,
            registry=registry,
            fillers_by_role=fillers_by_role,
            seen=seen,
        )
        _validate_rows(
            decision,
            target,
            path,
            registry=registry,
            fillers_by_role=fillers_by_role,
            measurements=measurements,
        )


def _check_when(
    rows: Sequence[DecisionRow],
    where: str,
    *,
    measurements: MeasurementRegistry,
    facts: set[str],
) -> None:
    """Every `when` key names a premise something can supply, and reads it sensibly.

    Run **after the stack is assembled** rather than inside `parse`, for the same reason
    `roles.check` runs after the registry is: a derivation and the decision reading it may
    sit in different files, and a check that fires per file would refuse a legitimate rule
    for the accident of which one `stack()` reached first.

    `when` sees more than measurements now — that is A120, and the whole point of the premise
    layer. So the message names all three sources rather than only the one it used to know
    about, which is what made the old diagnostic misleading rather than merely incomplete.
    """
    derived = sorted(facts - set(measurements.ids()) - _GOAL_FACTS)
    for row in rows:
        for fact, expected in row.when.items():
            if fact not in facts:
                raise RuleValidationError(
                    f"MD0310: {where}\n"
                    f"  {fact!r} is not a premise anything supplies, so this row can never\n"
                    f"  fire.\n"
                    f"  Declared measurements: {', '.join(measurements.ids()) or '(none)'}\n"
                    f"  Derived facts: {', '.join(derived) or '(none)'}\n"
                    f"  Goal facts: {', '.join(sorted(_GOAL_FACTS))}"
                )
            if expected in ("absent", "present") or fact not in measurements.ids():
                continue
            measurement = measurements.get(fact)
            if _comparison(expected) is not None and measurement.kind not in _ORDERED:
                raise RuleValidationError(
                    f"MD0310: {where}\n"
                    f"  {fact!r} is an {measurement.kind}, so it can only be compared with\n"
                    f"  equality, `in` or `not` — never {expected!r}."
                )
