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
from pathlib import Path

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
from comeni_core.marks import LayerName, ParamValue
from comeni_core.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.profile import DataProfile
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from pydantic import BaseModel, ConfigDict, Field

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


class DecisionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    param: str | None = None
    producer_of: str | None = None

    def key(self) -> str:
        return f"param:{self.param}" if self.param else f"producer_of:{self.producer_of}"


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

    decides: DecisionTarget
    rows: list[DecisionRow] = Field(default_factory=list)
    because: str | None = None
    cite: str | None = None


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
        """`rule <key>[ matched <when>][: <row justification>]`, with no dangling colon.

        On `Pin` rather than in `resolve`, because `router` needs it too and importing
        `resolve` from `router` is a cycle — and because every input it formats is already
        here. A row may be justified entirely by its block (a one-row rule often is) and
        `MD0301` allows that, but `rule param:strandedness: ` with nothing after the colon
        reads as a truncation rather than as an absence, which is half of what A78 was.
        """
        head = f"rule {self.decision.decides.key()}"
        if matched is not None:
            head = f"{head} matched {matched}"
        because = self.because()
        return f"{head}: {because}" if because else head

    def axis_because(self) -> str:
        """Why this decision is made this way **at all** — the block's justification.

        Kept separate rather than concatenated, because a reader wants to know both and to be
        able to tell which is which: the axis is the methodology, the row is the choice made
        under it. A79, A107.
        """
        return _joined(self.decision.because, self.decision.cite)


class RuleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[Decision] = Field(default_factory=list)

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

        def parse(path: Path) -> list[Decision]:
            data = yaml_strict.load(path) or {}
            found = []
            for raw in data.get("decisions", []):
                decision = Decision.model_validate(raw)
                _validate(decision, path, registry, vocabulary, measurements)
                found.append(decision)
            return found

        return Kind(
            DeclaredKind.RULES,
            parse=parse,
            key=lambda decision: decision.decides.key(),
            policy=Policy.REPLACE,
        )

    @classmethod
    def of(cls, stacked: Stacked[str, Decision], layers: Sequence[Layer]) -> "RuleTable":
        name_of = {layer.index: layer.name for layer in layers}
        return cls(
            decisions=[stacked.entries[key] for key in sorted(stacked.entries)],
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
        return cls.of(
            stack(as_layers, cls.kind(registry, vocabulary, measurements)), as_layers
        )

    def _for(self, key: str, profile: DataProfile) -> Pin | None:
        for decision in self.decisions:
            if decision.decides.key() != key:
                continue
            for row in decision.rows:
                if row.matches(profile):
                    return Pin(
                        value=row.then,
                        from_layer=self.layer_of.get(key, ""),
                        displaced_layer=self.displaced_layer.get(key),
                        decision=decision,
                        row=row,
                    )
        return None

    def value_for(self, param: str, profile: DataProfile) -> Pin | None:
        return self._for(f"param:{param}", profile)

    def producer_for(self, type_id: str, profile: DataProfile) -> Pin | None:
        return self._for(f"producer_of:{type_id}", profile)


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


def _validate(
    decision: Decision,
    path: Path,
    registry: Registry,
    vocabulary: Vocabulary,
    measurements: MeasurementRegistry,
) -> None:
    target = decision.decides
    if bool(target.param) == bool(target.producer_of):
        raise RuleValidationError(f"{path}: a decision decides exactly one of param, producer_of")

    if target.param:
        declared = sorted({p.name for c in registry.all() for p in c.params})
        if target.param not in declared:
            raise RuleValidationError(
                f"{path}, decision {target.key()}\n"
                f"  No contract in the registry declares a parameter named {target.param!r}.\n"
                f"  Parameters that do exist: {', '.join(declared) or '(none)'}"
            )
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
    else:
        if target.producer_of not in vocabulary.types:
            raise RuleValidationError(
                f"{path}: {target.producer_of!r} is not a declared type.\n"
                f"  Types that do exist: {', '.join(sorted(vocabulary.types))}"
            )
        for row in decision.rows:
            contract_id = str(row.then)
            if contract_id not in registry.contracts:
                raise RuleValidationError(
                    f"{path}: {contract_id!r} is not in the registry, so this row can never "
                    f"be applied. A rule table is only valid against a registry that can "
                    f"satisfy it."
                )
            produced = {p.type_id for p in registry.get(contract_id).produces}
            if target.producer_of not in produced:
                raise RuleValidationError(
                    f"{path}: {contract_id!r} does not produce {target.producer_of!r}"
                )

    for index, row in enumerate(decision.rows):
        if not (row.because or row.cite or decision.because or decision.cite):
            raise RuleValidationError(
                f"MD0301: {path}, decision {target.key()}, row {index}\n"
                f"  This row justifies nothing — no `because` and no `cite`, on the row or\n"
                f"  on the block. It fires at tier 3, whose review level is *advisory*, which\n"
                f"  means 'the machinery worked, check the premise'. A reader given no\n"
                f"  premise cannot. It also emitted a reason ending in a bare colon.\n"
                f"  Add `because:` saying why this answer, or `cite:` naming the evidence."
            )

    for row in decision.rows:
        for measurement_id, expected in row.when.items():
            try:
                # Raises naming what *is* declared, which is the half of the message an
                # author actually needs. Re-raised as a rule error so a bad table is one
                # kind of failure to the caller rather than two.
                measurement = measurements.get(measurement_id)
            except KeyError as exc:
                raise RuleValidationError(
                    f"{path}, decision {target.key()}\n  {exc.args[0]}"
                ) from exc
            if _comparison(expected) is not None and measurement.kind not in _ORDERED:
                raise RuleValidationError(
                    f"{path}: {measurement_id!r} is an {measurement.kind}, so it can only be "
                    f"compared with equality, not {expected!r}"
                )
