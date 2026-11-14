"""The `rule_proposal` model point (#462): a model proposes rule rows from people's answers.

One call, then once more with its problems, as the forge drafts. The reply is checked where it
arrives: each row is a valid rule row, tests only the facts given, answers only with a legal
answer, and the engine's judge (`mendel_resolver.proposals.judge`) finds nothing. Each call is
an `ai_invocation` under the forge's model setting, because a rule is registry work.

Only the declared payload reaches the model: the target, the existing rows, the facts a row may
test, the legal answers, and each case's study facts, answer and reason. No sample names, keys,
references, file names or pipeline ids.
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from comeni_ai import Client
from comeni_ai.prompts import PromptTemplate
from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.diagnostics import coded
from comeni_core.egress.rules import (
    CaseText,
    FactKind,
    FactValue,
    RuleEffect,
    RuleProposalRequest,
    RuleTarget,
)
from mendel_resolver.proposals import Case, cite_for, judge, table_with
from mendel_resolver.rules import Decision, DecisionRow, DecisionTarget
from pydantic import ValidationError

from mendel_api import db
from mendel_api.invocations import Agent, InvocationPurpose, InvocationState
from mendel_api.models import AiInvocation
from mendel_api.rules.replies import ProposalReply
from mendel_api.services import registry
from mendel_api.settings import model_access

PROMPTS = Path(__file__).parent.parent / "rules" / "prompts"
PROMPT_ID = "rules.propose.v1"
ATTEMPTS = 2
TESTABLE = (MeasurementKind.INTEGER, MeasurementKind.NUMBER, MeasurementKind.BOOLEAN,
            MeasurementKind.ENUM)
"""The kinds a learned row may test. A sample's key or reference names a sample, so it is
never sent, and a rule could not test it for the study anyway."""

NO_MODEL = coded("MI0501", "no model is set to propose rules (Settings → Models → Adapting "
                 "tools)")


def _client() -> Client | None:
    access = model_access(Agent.FORGE.value, InvocationPurpose.ANALYSIS.value)
    return Client(access) if access is not None else None


def model_set() -> bool:
    return model_access(Agent.FORGE.value, InvocationPurpose.ANALYSIS.value) is not None


def fact_kinds(cases: list[Case], existing: Decision | None,
               measurements: MeasurementRegistry) -> list[FactKind]:
    """The facts a row may test: those the cases were given and the existing rows test, when
    declared and of a kind a rule can test; sorted."""
    named = {fact for case in cases for fact in case.facts}
    named |= {fact for row in (existing.rows if existing else []) for fact in row.when}
    found = []
    for fact in sorted(named):
        if fact not in measurements.ids():
            continue
        measurement = measurements.get(fact)
        if measurement.kind not in TESTABLE:
            continue
        found.append(FactKind(id=fact, kind=measurement.kind, values=sorted(measurement.values)))
    return found


def carried() -> set[str]:
    """The facts a case can carry: declared measurements, not facts a rule derives, which a
    kept pipeline does not record and a build computes."""
    stack = registry.stack()
    derived = {d.fact for d in stack.rules.derivations}
    return set(stack.measurements.ids()) - derived


def request(target: DecisionTarget, existing: Decision | None, cases: list[Case],
            facts: list[FactKind], answers: list) -> RuleProposalRequest:
    """The door payload. A case's facts are only those a row may test."""
    allowed = {fact.id for fact in facts}
    return RuleProposalRequest(
        prompt=PROMPT_ID,
        target=RuleTarget(effect=RuleEffect(target.effect.value), of=target.of, name=target.name,
                          when_implementation=sorted(target.when_implementation)),
        # Never a row's `cite`: a learned row's names the kept pipelines it came from.
        existing=[json.dumps(row.model_dump(mode="json", exclude_none=True, exclude={"cite"}),
                             sort_keys=True)
                  for row in (existing.rows if existing else [])],
        facts=facts,
        answers=sorted(answers, key=str),
        cases=sorted((CaseText(facts=[FactValue(measurement=k, value=v)
                                      for k, v in sorted(case.facts.items()) if k in allowed],
                               answer=case.answer, reason=" ".join(case.reason.split()))
                      for case in cases if case.evidence),
                     key=lambda c: c.model_dump_json()))


def _target_text(target: RuleTarget) -> str:
    if target.effect is RuleEffect.IMPLEMENTATION:
        return f"which tool fills the role `{target.of}`"
    tools = ", ".join(target.when_implementation)
    return f"the value of the setting `{target.name}` of {tools} (role `{target.of}`)"


def _values(payload: RuleProposalRequest, problems: list[str]) -> dict[str, str]:
    def kind(fact: FactKind) -> str:
        return f"{fact.kind.value}" + (f": {', '.join(map(str, fact.values))}"
                                       if fact.values else "")

    def case(c: CaseText) -> str:
        facts = ", ".join(f"{f.measurement} = {json.dumps(f.value)}" for f in c.facts)
        return (f"- facts: {facts or '(none known)'} → answer: {json.dumps(c.answer)}"
                + (f"; reason: {c.reason}" if c.reason else ""))

    return {
        "target": _target_text(payload.target),
        "existing": "\n".join(f"{n}. {row}" for n, row in enumerate(payload.existing, 1))
        or "(none: this is a new table)",
        "facts": "\n".join(f"- {f.id} ({kind(f)})" for f in payload.facts) or "(none)",
        "answers": "\n".join(f"- {json.dumps(a)}" for a in payload.answers),
        "cases": "\n".join(case(c) for c in payload.cases),
        "problems": ("\n=== your last reply was refused ===\n"
                     + "\n".join(f"- {p}" for p in problems)) if problems else "",
    }


def _record(digest: str, client: Client, started: datetime, evidence: str, *, ok: bool) -> str:
    invocation_id = secrets.token_hex(16)
    finished = datetime.now(UTC)
    usage = getattr(client, "last_usage", None)
    prompt = getattr(client, "last_prompt", None)
    with db.session_scope() as session:
        session.add(AiInvocation(
            id=invocation_id, agent=Agent.FORGE.value,
            purpose=InvocationPurpose.ANALYSIS.value,
            model=usage.model if usage else client.access.model,
            provider="local" if client.access.base_url else "",
            prompt_id=PROMPT_ID, prompt_version=PROMPT_ID.rsplit(".", 1)[-1],
            prompt_digest=hashlib.sha256(prompt.encode()).hexdigest() if prompt else digest,
            input_digests={"registry": registry.digest(), "evidence": evidence},
            temperature=client.access.temperature,
            state=(InvocationState.SUCCEEDED if ok else InvocationState.REFUSED).value,
            failure_code="" if ok else "MA0004",
            started_at=started, finished_at=finished,
            duration_ms=int((finished - started).total_seconds() * 1000),
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            cached_tokens=usage.cached_tokens if usage else None,
            response=getattr(client, "last_response", None),
        ))
    return invocation_id


def _rows(reply: ProposalReply, facts: list[FactKind],
          answers: list) -> tuple[list[DecisionRow], list[str]]:
    """The reply's rows as rule rows, and what is wrong with them before the judge."""
    allowed = {fact.id for fact in facts}
    rows, problems = [], []
    for n, proposed in enumerate(reply.rows, start=1):
        try:
            row = DecisionRow.model_validate(proposed.model_dump())
        except ValidationError as error:
            problems.append(f"row {n} is not a rule row: {error.errors()[0]['msg']}")
            continue
        problems += [f"row {n} tests {fact}, which is not one of the facts given"
                     for fact in sorted(set(row.when) - allowed)]
        if row.then not in answers:
            problems.append(f"row {n}: {row.then} is not one of the legal answers")
        rows.append(row)
    return rows, problems


def propose(target: DecisionTarget, existing: Decision | None, cases: list[Case],
            facts: list[FactKind], answers: list, client: Client | None = None,
            *, evidence: str = "") -> tuple[list[DecisionRow], str, str | None, list[str]]:
    """Ask for rows, checked where they arrive: the rows (cited and narrowed by the engine), the
    model's `why`, the last invocation's id, and the problems a refused reply left. `([], why,
    id, [])` is the model saying the answers hold no rule."""
    client = client or _client()
    if client is None:
        return [], "", None, [NO_MODEL]
    payload = request(target, existing, cases, facts, answers)
    template = PromptTemplate.load(PROMPTS, PROMPT_ID)
    cite = cite_for([case for case in cases if case.evidence])
    problems: list[str] = []
    invocation = None
    for _ in range(ATTEMPTS):
        rendered = template.render(_values(payload, problems))
        started = datetime.now(UTC)
        reply = client.respond(rendered.text, ProposalReply)
        invocation = _record(rendered.digest, client, started, evidence, ok=reply is not None)
        if reply is None:
            problems = [getattr(client, "last_refusal", None) or "the reply did not fit its shape"]
            continue
        if not reply.rows:
            return [], reply.why, invocation, []
        rows, problems = _rows(reply, facts, answers)
        if not problems:
            table = table_with(target, existing, rows, cite, cases=cases,
                               carried=carried())
            new = table.rows[len(table.rows) - len(rows):]
            problems = judge(table, new, cases)
            if not problems:
                return new, reply.why, invocation, []
    return [], "", invocation, problems
