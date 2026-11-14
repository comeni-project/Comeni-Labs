"""Rules proposed from people's answers (#462): the source, the store, the check and the sink.

The middle is pure (`mendel_resolver.proposals`: cases, the judge, the replay) and the model
point is `rules_ai`. The two ends here are adapters, so a server gathering cases from many
installations could replace either:

- **the source** reads this installation's kept pipelines;
- **the sink** writes an approved table to this installation's own registry layer, stacked above
  the release, where every later build reads it.

A proposal is stored, never recomputed: the model is asked again for a target only when the
digest of its evidence moves, so a rejected proposal stays rejected until people answer
differently.
"""

import logging
import os
import secrets
import shutil
import tempfile
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa
import yaml
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import ParamValue
from comeni_flow.interpret import Refused
from mendel_compiler import pipeline_file
from mendel_resolver import layers
from mendel_resolver.proposals import LEARNED as LEARNED_BECAUSE
from mendel_resolver.proposals import (
    Case,
    Replayed,
    cases_of,
    evidence,
    evidence_digest,
    judge,
    replay,
)
from mendel_resolver.rules import Decision, DecisionRow, DecisionTarget, Effect
from pydantic import BaseModel, JsonValue

from mendel_api import db, jobs
from mendel_api.models import AiInvocation, PipelineDraft, RuleProposal
from mendel_api.services import registry, rules_ai
from mendel_api.settings import active_registry, own_layer, settings

log = logging.getLogger(__name__)

JOB = "propose_rules"
JOB_ID = "propose-rules"
LEARNED = "rules/learned"


# ── the source: this installation's kept pipelines ──────────────────────────────────────────


def _kept_rows() -> tuple[tuple[str, str], ...]:
    with db.session_scope() as session:
        found = session.execute(sa.select(PipelineDraft.id, PipelineDraft.kept_digest)
                                .where(PipelineDraft.kept_at.is_not(None))).all()
    return tuple(sorted((draft_id, digest or "") for draft_id, digest in found))


@lru_cache(maxsize=2)
def _cases_for(kept: tuple[tuple[str, str], ...], root: Path, layers_digest: str) -> list[Case]:
    """One pass over the kept `pipeline.yml` files, cached on which pipelines are kept, in which
    state, and on the registry their targets are read against."""
    stack = registry.stack()
    found: list[Case] = []
    for draft_id, _ in kept:
        path = root / draft_id / "pipeline.yml"
        try:
            pipeline = pipeline_file.load(path)
        except (OSError, ValueError) as error:
            log.warning("kept pipeline %s is unreadable, so it is not evidence: %s",
                        draft_id, type(error).__name__)
            continue
        found.extend(cases_of(pipeline, stack.registry, draft_id))
    return sorted(found, key=lambda c: (c.target_key, c.pipeline, c.decision))


def cases() -> list[Case]:
    """Every case in this installation's kept pipelines, of any tier or author."""
    return _cases_for(_kept_rows(), Path(settings.draft_root), registry.digest())


kept = _cases_for
"""The cache, under the name the tests clear."""


# ── what a target is, in force and in words ──────────────────────────────────────────────────


def slug(target_key: str) -> str:
    """The learned file's name. Only `:` is replaced: roles and setting names hold no `-`, so
    two targets never share a file."""
    return target_key.replace(":", "-")


def in_force(target_key: str) -> Decision | None:
    """The table in force for this target, from every layer the installation builds with."""
    return next((d for d in registry.stack().rules.decisions
                 if target_key in {t.key() for t in d.targets()}), None)


def answers_for(target: DecisionTarget, found: list[Case]) -> list[ParamValue]:
    """The legal answers: every tool filling the role, or the setting's declared domain; the
    answers people gave where the domain is open."""
    stack = registry.stack()
    if target.effect is Effect.IMPLEMENTATION:
        return sorted(c.id for c in stack.registry.all() if target.of in c.roles)
    for contract_id in target.when_implementation:
        spec = next((p for p in stack.registry.get(contract_id).params
                     if p.name == target.name), None)
        if spec is not None and spec.domain is not None:
            if spec.domain.values:
                return sorted(spec.domain.values)
            if spec.domain.kind.value == "boolean":
                return [False, True]
    return sorted({case.answer for case in found}, key=str)


def words(target: DecisionTarget) -> str:
    if target.effect is Effect.IMPLEMENTATION:
        return f"Which tool fills {target.of.replace('_', ' ')}"
    tools = ", ".join(target.when_implementation)
    return f"The {target.name} setting of {tools}"


# ── asking ───────────────────────────────────────────────────────────────────────────────────


def _latest(session, target_key: str) -> RuleProposal | None:
    return session.scalars(sa.select(RuleProposal).where(RuleProposal.target_key == target_key)
                           .order_by(RuleProposal.created_at.desc())).first()


def run(client=None) -> int:
    """Ask the model about each target whose evidence moved since it was last asked; return how
    many were asked. A model that is not configured asks nothing."""
    every = cases()
    measurements = registry.stack().measurements
    asked = 0
    for key, found in evidence(every).items():
        digest = evidence_digest(found)
        with db.session_scope() as session:
            latest = _latest(session, key)
            if latest is not None and latest.evidence_digest == digest:
                continue
        target = found[0].target
        existing = in_force(key)
        of_target = [case for case in every if case.target_key == key]
        rows, why, invocation, problems = rules_ai.propose(
            target, existing, of_target, rules_ai.fact_kinds(of_target, existing, measurements),
            answers_for(target, found), client, evidence=digest)
        if invocation is None:
            return asked
        asked += 1
        status = "proposed" if rows else ("refused" if problems else "no_rule")
        with db.session_scope() as session:
            session.execute(sa.update(RuleProposal)
                            .where(RuleProposal.target_key == key,
                                   RuleProposal.status == "proposed")
                            .values(status="superseded"))
            session.add(RuleProposal(
                id=secrets.token_hex(16), target_key=key,
                target=target.model_dump(mode="json"),
                rows=[row.model_dump(mode="json", exclude_none=True) for row in rows],
                why=why, evidence_digest=digest, invocation=invocation, status=status,
                problems=problems, created_at=datetime.now(UTC)))
    return asked


async def start() -> None:
    """Queue a run on the AI worker; refused when no model is set to propose rules."""
    if not rules_ai.model_set():
        raise Refused(rules_ai.NO_MODEL)
    await jobs.enqueue(JOB, job_id=JOB_ID, queue=jobs.AI_QUEUE)


async def propose_rules(ctx: dict) -> int:
    """The AI worker's job."""
    import asyncio

    return await asyncio.to_thread(run)


# ── the check ────────────────────────────────────────────────────────────────────────────────


def _file(table: Decision, header: list[str]) -> str:
    body = yaml.safe_dump({"declares": "rule", "version": 1,
                           "decisions": [table.model_dump(mode="json", exclude_none=True)]},
                          sort_keys=False, allow_unicode=True)
    return "".join(f"# {line}\n" for line in header) + body


def _table(row: RuleProposal) -> Decision:
    """The table this proposal puts in force: the one in force now, then its rows (stored cited
    and narrowed by the engine). Read only for an open proposal."""
    stored = [DecisionRow.model_validate(r) for r in row.rows]
    existing = in_force(row.target_key)
    if existing is None:
        return Decision(decides=DecisionTarget.model_validate(row.target), rows=stored,
                        because=LEARNED_BECAUSE)
    return existing.model_copy(update={"rows": [*existing.rows, *stored]})


def check(row: RuleProposal) -> list[str]:
    """Whether the table this proposal would put in force, **as it would be now**, is sound: the
    engine's judge against today's answers, then the registry, by writing it into a copy of the
    installation's layer and loading it on the release. The table in force may have changed since
    the model was asked (a release switch, a hand edit), so it is judged again here."""
    table = _table(row)
    stored = table.rows[len(table.rows) - len(row.rows):]
    judged = judge(table, stored, [c for c in cases() if c.target_key == row.target_key])
    if judged:
        return judged
    with tempfile.TemporaryDirectory() as scratch:
        candidate = Path(scratch) / "layer"
        own = own_layer()
        if (own / "registry.yml").is_file():
            shutil.copytree(own, candidate)
        else:
            candidate.mkdir()
            (candidate / "registry.yml").write_text(
                f"name: {registry.OWN_LAYER_NAME}\nrequires_format: 2\n")
        path = candidate / LEARNED / f"{slug(row.target_key)}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_file(table, []))
        try:
            layers.load([active_registry(), candidate])
        except (ValueError, KeyError) as error:
            return [str(error)]
    return []


_checks: dict[tuple, list[str]] = {}


def _checked(row: RuleProposal) -> list[str]:
    """`check`, remembered while the kept pipelines and the registry stay as they are: the page
    reads every open proposal on each load. Approving always checks again."""
    key = (row.id, _kept_rows(), registry.digest())
    if key not in _checks:
        if len(_checks) > 64:
            _checks.clear()
        _checks[key] = check(row)
    return _checks[key]


# ── the view ─────────────────────────────────────────────────────────────────────────────────


class EvidenceView(BaseModel):
    pipeline: str
    decision: str
    facts: dict[str, ParamValue]
    """The study facts the person answered on."""
    answer: ParamValue
    reason: str


class ProposalView(BaseModel):
    id: str
    target_key: str
    target: str
    rows: list[dict[str, JsonValue]]
    why: str
    model: str
    invocation: str | None
    evidence: list[EvidenceView]
    check: list[str]
    replay: list[Replayed]
    stale: bool
    created_at: datetime


class RefusedView(BaseModel):
    id: str
    target_key: str
    target: str
    status: str
    why: str
    problems: list[str]


class InUseView(BaseModel):
    slug: str
    target_key: str
    target: str
    rows: list[dict[str, JsonValue]]
    learned: list[bool]
    """Per row: learned from people's answers, or a row of the release the file copies."""
    approved_by: str | None
    approved_at: datetime | None
    proposal: str | None


class ProposalsView(BaseModel):
    proposals: list[ProposalView]
    refused: list[RefusedView]
    in_use: list[InUseView]
    running: bool = False
    model: bool


def _model_of(session, invocation: str | None) -> str:
    found = session.get(AiInvocation, invocation) if invocation else None
    return found.model if found is not None else ""


def read() -> ProposalsView:
    every = cases()
    grouped = evidence(every)
    with db.session_scope() as session:
        rows = session.scalars(sa.select(RuleProposal)
                               .order_by(RuleProposal.created_at.desc())).all()
        latest: dict[str, RuleProposal] = {}
        for row in rows:
            latest.setdefault(row.target_key, row)
        approved = {slug(r.target_key): r for r in rows if r.status == "approved"}
        open_ = []
        for row in rows:
            if row.status != "proposed":
                continue
            target = DecisionTarget.model_validate(row.target)
            found = grouped.get(row.target_key, [])
            table = _table(row)
            new = table.rows[len(table.rows) - len(row.rows):]
            open_.append(ProposalView(
                id=row.id, target_key=row.target_key, target=words(target), rows=row.rows,
                why=row.why, model=_model_of(session, row.invocation),
                invocation=row.invocation,
                evidence=[EvidenceView(pipeline=c.pipeline, decision=c.decision, facts=c.facts,
                                       answer=c.answer, reason=c.reason) for c in found],
                check=_checked(row),
                replay=replay(table, new, [c for c in every if c.target_key == row.target_key]),
                stale=evidence_digest(found) != row.evidence_digest,
                created_at=row.created_at))
        refused = [RefusedView(id=r.id, target_key=r.target_key,
                               target=words(DecisionTarget.model_validate(r.target)),
                               status=r.status, why=r.why, problems=list(r.problems))
                   for r in latest.values() if r.status in ("refused", "no_rule")]
        in_use = []
        folder = own_layer() / LEARNED
        for path in sorted(folder.glob("*.yml")) if folder.is_dir() else []:
            row = approved.get(path.stem)
            decision = Decision.model_validate(yaml.safe_load(path.read_text())["decisions"][0])
            target = decision.targets()[0]
            in_use.append(InUseView(
                slug=path.stem, target_key=target.key(), target=words(target),
                rows=[r.model_dump(mode="json", exclude_none=True) for r in decision.rows],
                learned=[(r.cite or "").startswith("kept pipelines ") for r in decision.rows],
                approved_by=row.decided_by if row else None,
                approved_at=row.decided_at if row else None, proposal=row.id if row else None))
    return ProposalsView(proposals=open_, refused=refused, in_use=in_use,
                         model=rules_ai.model_set())


# ── the sink: the installation's own layer ───────────────────────────────────────────────────


def _cannot(why: str) -> Refused:
    return Refused(coded("MI0500", f"a rule proposal cannot be approved as it stands: {why}"))


def _supersede(session, target_key: str) -> None:
    session.execute(sa.update(RuleProposal)
                    .where(RuleProposal.target_key == target_key,
                           RuleProposal.status == "approved")
                    .values(status="superseded"))


def approve(proposal_id: str, by: str) -> ProposalsView:
    """Write the table this proposal puts in force to the installation's own layer.

    The row is locked while it is judged. The file is written beside its place and renamed into
    it once the approval is committed, so a failure leaves neither a file nor an approval."""
    pending: Path | None = None
    try:
        with db.session_scope() as session:
            row = session.get(RuleProposal, proposal_id, with_for_update=True)
            if row is None:
                raise KeyError(proposal_id)
            if row.status != "proposed":
                raise _cannot(f"it is {row.status}")
            found = evidence(cases()).get(row.target_key, [])
            if evidence_digest(found) != row.evidence_digest:
                raise _cannot("people have answered since it was proposed; choose Propose again")
            problems = check(row)
            if problems:
                raise _cannot(problems[0])
            now = datetime.now(UTC)
            header = [
                f"Learned from people's answers (#462): approved by {by} on {now:%Y-%m-%d}.",
                f"Proposed by a model (ai_invocation {row.invocation}); checked by the engine.",
                "Evidence: kept pipelines " + ", ".join(sorted({c.pipeline for c in found}))
                + ".",
                "Withdraw it on the Learned rules page; edit it as any rule.",
            ]
            path = registry.ensure_own_layer() / LEARNED / f"{slug(row.target_key)}.yml"
            path.parent.mkdir(parents=True, exist_ok=True)
            pending = path.with_name(f".{path.name}.pending")
            pending.write_text(_file(_table(row), header))
            _supersede(session, row.target_key)
            row.status, row.decided_by, row.decided_at = "approved", by, now
        os.replace(pending, path)
        pending = None
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
            registry.retire_own_layer_if_empty()
    return read()


def reject(proposal_id: str, by: str) -> ProposalsView:
    with db.session_scope() as session:
        row = session.get(RuleProposal, proposal_id)
        if row is None:
            raise KeyError(proposal_id)
        if row.status != "proposed":
            raise _cannot(f"it is {row.status}")
        row.status, row.decided_by, row.decided_at = "rejected", by, datetime.now(UTC)
    return read()


def withdraw(name: str, by: str) -> ProposalsView:
    """Remove a learned table: the question it settled is asked again. The file goes once the
    withdrawal is committed."""
    path = own_layer() / LEARNED / f"{name}.yml"
    if "/" in name or not path.is_file():
        raise KeyError(name)
    with db.session_scope() as session:
        for row in session.scalars(sa.select(RuleProposal)
                                   .where(RuleProposal.status == "approved")
                                   .with_for_update()).all():
            if slug(row.target_key) == name:
                row.status, row.decided_by, row.decided_at = "withdrawn", by, datetime.now(UTC)
    path.unlink()
    registry.retire_own_layer_if_empty()
    return read()
