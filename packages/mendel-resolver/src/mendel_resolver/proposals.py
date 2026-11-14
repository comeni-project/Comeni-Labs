"""Rules proposed from people's answers (#462): the evidence, the engine's judge, the replay.

When people keep giving the same tier-4 answer on the same facts, that answer is a rule nobody
wrote down. A model drafts the row (`mendel_api.services.rules_ai`); these functions hold it to
the evidence. They are pure, and their input is a list of :class:`Case` records, so they do not
know whether the cases came from this installation's kept pipelines or, later, from a server
gathering them from many.

A case holds what was decided, the study's facts, the answer and who gave it, and a reference to
the pipeline and decision. Never a sample name, key, reference or file name.
"""

import hashlib
import json
from collections import defaultdict

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.registry import Registry
from comeni_core.logic.when import matches
from comeni_core.plan.decision import DecisionKind
from comeni_core.spell.marks import ParamValue
from pydantic import BaseModel, ConfigDict

from mendel_resolver.rules.format import Decision, DecisionRow, DecisionTarget, Effect

MIN_CASES = 3
"""How many people's answers to one question it takes before the model is asked for a rule.

The first knob for how much the AI does: lower, and it proposes from thinner evidence."""


class Case(BaseModel):
    """One past decision: what it decided, on which facts, the answer and who gave it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: DecisionTarget
    facts: dict[str, ParamValue]
    """The study-wide facts the pipeline was built on. A per-sample list is left out."""
    answer: ParamValue
    reason: str = ""
    """What the person typed with their answer, where they typed anything."""
    pipeline: str
    decision: str
    """The decision's key in that pipeline's `decisions`."""
    by_person: bool
    tier: int

    @property
    def target_key(self) -> str:
        return self.target.key()

    @property
    def evidence(self) -> bool:
        """A person's answer to a question the rules could not settle. A model's answer, or a
        rule's, is a case the replay compares against, never evidence."""
        return self.by_person and self.tier == 4


def _single_role(contracts: list[str], registry: Registry) -> str | None:
    """The one role every contract fills, or None when they share none or several."""
    try:
        shared = set.intersection(*(set(registry.get(c).roles) for c in contracts))
    except (KeyError, ValueError):
        return None
    return next(iter(shared)) if len(shared) == 1 else None


def _target(record, pipeline: Pipeline, registry: Registry) -> DecisionTarget | None:
    if record.kind == DecisionKind.PRODUCER:
        role = _single_role(list(record.candidates), registry)
        return DecisionTarget(effect=Effect.IMPLEMENTATION, of=role) if role else None
    node, _, param = record.key.partition(".")
    step = next((s for s in pipeline.steps if s.id == node), None)
    if step is None or not param:
        return None
    contract = step.module.contract_id
    role = _single_role([contract], registry)
    if role is None:
        return None
    return DecisionTarget(effect=Effect.PARAM, of=role, name=param,
                          when_implementation=[contract])


def _answer(record) -> ParamValue:
    if getattr(record, "human_override", None) is not None:
        return record.human_override
    if getattr(record, "model_override", None) is not None:
        return record.model_override
    return record.chosen


def cases_of(pipeline: Pipeline, registry: Registry, pipeline_id: str) -> list[Case]:
    """Every tool choice and setting this pipeline decided among two or more candidates, as
    cases, sorted by target, pipeline and decision. Model answers and rule answers are kept:
    the replay compares against them."""
    facts = {m.measurement: m.value for m in pipeline.facts.measurements
             if not isinstance(m.value, list)}
    found = []
    for record in pipeline.decisions:
        if record.kind not in (DecisionKind.PRODUCER, DecisionKind.PARAM):
            continue
        if len(record.candidates) < 2:
            continue
        target = _target(record, pipeline, registry)
        if target is None:
            continue
        found.append(Case(
            target=target, facts=facts, answer=_answer(record),
            reason=getattr(record, "override_reason", "") or "", pipeline=pipeline_id,
            decision=record.key, by_person=getattr(record, "human_override", None) is not None,
            tier=int(record.tier)))
    return sorted(found, key=lambda c: (c.target_key, c.pipeline, c.decision))


def evidence(cases: list[Case]) -> dict[str, list[Case]]:
    """People's answers grouped by what they decide, for each target with at least
    :data:`MIN_CASES` of them; sorted by target key."""
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        if case.evidence:
            grouped[case.target_key].append(case)
    return {key: sorted(found, key=lambda c: (c.pipeline, c.decision))
            for key, found in sorted(grouped.items()) if len(found) >= MIN_CASES}


def evidence_digest(cases: list[Case]) -> str:
    """The digest of these cases, independent of their order: a proposal is asked for again only
    when it moves."""
    rows = sorted(json.dumps(case.model_dump(mode="json"), sort_keys=True) for case in cases)
    return "sha256:" + hashlib.sha256("\n".join(rows).encode()).hexdigest()


# ---------------- the engine's judge ----------------

LEARNED = "learned from people's answers"


class _Fact(BaseModel):
    """A recorded fact as a rule reads it: only its value matters here."""

    model_config = ConfigDict(frozen=True)

    value: ParamValue


def _premises(case: Case) -> dict[str, _Fact]:
    return {name: _Fact(value=value) for name, value in case.facts.items()}


def cite_for(cases: list[Case]) -> str:
    """The citation a learned row carries, set by the engine and never by the model."""
    pipelines = ", ".join(sorted({case.pipeline for case in cases}))
    decisions = ", ".join(sorted({case.decision for case in cases}))
    return f"kept pipelines {pipelines}, decision {decisions}"


def _narrowed(row: DecisionRow, existing: Decision, cases: list[Case]) -> DecisionRow:
    """The row, saying `absent` for each fact the existing rows test that none of the answers it
    reaches had. That is why the question was asked, and the loader reads a row after them that
    does not say so as one that never fires (MD0323)."""
    reached = [case for case in cases if case.evidence and matches(row.when, _premises(case))]
    tested = sorted({fact for old in existing.rows for fact in old.when} - set(row.when))
    missing = [fact for fact in tested if reached and not any(fact in c.facts for c in reached)]
    if not missing:
        return row
    return row.model_copy(update={"when": {**row.when, **dict.fromkeys(missing, "absent")}})


def table_with(target: DecisionTarget, existing: Decision | None, rows: list[DecisionRow],
               cite: str, *, cases: list[Case] | None = None) -> Decision:
    """The table a proposal would put in force: the existing rows first, then the new ones.

    Appended, because the question was asked only where every existing row missed (`hit:
    first`), so the new rows only ever fire there. Given the cases, each new row is narrowed to
    the facts those rows found missing."""
    cited = [row.model_copy(update={"cite": cite}) for row in rows]
    if existing is None:
        return Decision(decides=target, rows=cited, because=LEARNED)
    cited = [_narrowed(row, existing, cases or []) for row in cited]
    return existing.model_copy(update={"rows": [*existing.rows, *cited]})


def _first(table: Decision, case: Case) -> tuple[int, ParamValue] | None:
    """The index of the first row of `table` that fires on this case's facts, and its value."""
    premises = _premises(case)
    for index, row in enumerate(table.rows):
        gives, value = row.value(premises)
        if gives and matches(row.when, premises):
            return index, value
    return None


def judge(table: Decision, new: list[DecisionRow], cases: list[Case]) -> list[str]:
    """What is wrong with putting `table` in force, given the answers its `new` rows were drafted
    from. Empty when it is sound.

    - **Contradiction:** a person's answer the table would overturn.
    - **Unsupported:** a new row no answer reaches; the model may not invent support.
    - **Shadowed:** a new row an earlier row always beats.
    """
    answers = [case for case in cases if case.evidence]
    start = len(table.rows) - len(new)
    problems = []
    fired: dict[int, list[Case]] = {}
    for case in answers:
        try:
            first = _first(table, case)
        except ValueError as exc:
            return [str(exc)]
        if first is None:
            continue
        index, value = first
        fired.setdefault(index, []).append(case)
        if value != case.answer:
            problems.append(f"{case.pipeline} {case.decision}: a person chose {case.answer}; "
                            f"the table would choose {value}")
    for n, row in enumerate(table.rows[start:], start=1):
        reached = [case for case in answers if matches(row.when, _premises(case))]
        if not reached:
            problems.append(f"row {n} matches none of the answers it was drafted from")
        elif not fired.get(start + n - 1):
            problems.append(f"row {n} never fires: an earlier row settles every case it matches")
    return problems


# ---------------- the replay ----------------


class Replayed(BaseModel):
    """One past decision the proposed rows would have settled, and whether the same way."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline: str
    decision: str
    recorded: ParamValue
    would: ParamValue
    agrees: bool
    by_person: bool


def replay(table: Decision, new: list[DecisionRow], cases: list[Case]) -> list[Replayed]:
    """Evaluate the proposed table against every recorded case of its target, of any tier or
    author, and list those a new row would settle: answers it would change first.

    Evaluated against the recorded facts, never rebuilt: no build or artifact is touched. For a
    model's or a rule's answer a change is information, not a refusal."""
    start = len(table.rows) - len(new)
    found = []
    for case in cases:
        first = _first(table, case)
        if first is None or first[0] < start:
            continue
        found.append(Replayed(pipeline=case.pipeline, decision=case.decision,
                              recorded=case.answer, would=first[1],
                              agrees=first[1] == case.answer, by_person=case.by_person))
    return sorted(found, key=lambda r: (r.agrees, r.pipeline, r.decision))
