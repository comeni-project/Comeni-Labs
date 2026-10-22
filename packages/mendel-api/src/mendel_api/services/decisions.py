"""Selected draft decisions, immutable observations, and ordered factual history.

All writes lock the draft first and join the dispatcher's transaction. Observations
never select themselves: only an explicit selection changes the goal.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from secrets import token_hex

from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal, Site
from mendel_authoring.decisions import (
    ActorKind,
    Attribution,
    Decisions,
    ExclusionChoice,
    FactDecision,
    FactOrigin,
    InputDecision,
    ParameterChoice,
    ProducerChoice,
    RoleChoice,
    SourceChoice,
    WantDecision,
)
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAsked,
    PipelineAskedRevision,
    PipelineDraft,
    PipelineEvidenceAccess,
    PipelineExclusion,
    PipelineExclusionRevision,
    PipelineFact,
    PipelineFactRevision,
    PipelineInput,
    PipelineInputRevision,
    PipelineObservation,
    PipelineParameter,
    PipelineParameterRevision,
    PipelineProducer,
    PipelineProducerRevision,
    PipelineReview,
    PipelineReviewRevision,
    PipelineRole,
    PipelineRoleRevision,
    PipelineSource,
    PipelineSourceRevision,
    PipelineWant,
    PipelineWantRevision,
)
from mendel_api.services import registry

_FAMILIES = {
    "input": (PipelineInput, PipelineInputRevision),
    "want": (PipelineWant, PipelineWantRevision),
    "fact": (PipelineFact, PipelineFactRevision),
    "producer": (PipelineProducer, PipelineProducerRevision),
    "parameter": (PipelineParameter, PipelineParameterRevision),
    "review": (PipelineReview, PipelineReviewRevision),
    "asked": (PipelineAsked, PipelineAskedRevision),
    # A person's structural intent (A1, the one-builder design).
    "role": (PipelineRole, PipelineRoleRevision),
    "exclusion": (PipelineExclusion, PipelineExclusionRevision),
    "source": (PipelineSource, PipelineSourceRevision),
}


def _heard(fields, heard, heard_seq):
    """The person's words beside a write, only when there are some: an unquoted write then
    compares equal to its predecessor exactly as before (Part I.0 §6.1)."""
    return {**fields, "heard": heard, "heard_seq": heard_seq} if heard is not None else fields


def _draft(db, draft_id, expected_revision=None):
    row = db.get(PipelineDraft, draft_id, with_for_update=True, populate_existing=True)
    if row is None:
        raise KeyError(draft_id)
    if expected_revision is not None and row.decision_revision != expected_revision:
        raise ValueError(coded("MI0201", "the selected decisions changed; read them again"))
    return row


def _seq(draft):
    draft.decision_sequence += 1
    return draft.decision_sequence


def _changed(db, draft):
    # One stamp per outer transaction, including multiple helpers in the same command.
    # Comparing the stamp also allows a caught SAVEPOINT rollback to restore its revision.
    stamps = db.info.setdefault("decision_stamps", {})
    key = (draft.id, db.get_transaction())
    if stamps.get(key) != draft.decision_revision:
        draft.decision_revision += 1
        stamps[key] = draft.decision_revision
    draft.projection_current = False


def _current(db, draft_id, family):
    subject, revision = _FAMILIES[family]
    return db.execute(
        select(subject, revision)
        .join(revision, subject.current_id == revision.id)
        .where(subject.draft_id == draft_id)
        .order_by(subject.position, subject.subject_key)
    ).all()


def _write(
    db,
    draft,
    family,
    key,
    fields,
    *,
    who,
    actor_kind=ActorKind.PERSON,
    action="select",
    position=None,
    acknowledge=False,
    legacy=False,
    proposal_id=None,
):
    attribution = Attribution(kind=actor_kind, who=who, legacy=legacy)
    subject_type, revision_type = _FAMILIES[family]
    subject = db.scalar(
        select(subject_type).where(
            subject_type.draft_id == draft.id, subject_type.subject_key == key
        )
    )
    current = db.get(revision_type, subject.current_id) if subject else None
    same = current is not None and all(
        getattr(current, name) == value for name, value in fields.items()
    )
    reordered = subject is not None and position is not None and position != subject.position
    if same and not acknowledge and proposal_id is None and not reordered:
        return current
    revision_id = token_hex(16)
    if subject is None:
        subject = subject_type(
            id=token_hex(16),
            draft_id=draft.id,
            subject_key=key,
            current_id=revision_id,
            position=position or 0,
        )
        db.add(subject)
        db.flush()  # Current-pointer FK is deferred, revision's subject FK is immediate.
    elif position is not None:
        subject.position = position
    recorded = dict(fields)
    if proposal_id is not None:
        recorded["proposal_id"] = proposal_id
    revision = revision_type(
        id=revision_id,
        draft_id=draft.id,
        subject_id=subject.id,
        seq=_seq(draft),
        at=datetime.now(UTC),
        action=action,
        actor_kind=attribution.kind,
        who=attribution.who,
        legacy=attribution.legacy,
        **recorded,
    )
    db.add(revision)
    subject.current_id = revision_id
    if family != "review" and (not same or reordered):
        _changed(db, draft)
    db.flush()
    return revision


def _observation(db, observation_id):
    return db.get(PipelineObservation, observation_id) if observation_id else None


def _fact(observation, subject):
    if observation is None:
        return FactDecision(subject=subject, origin=FactOrigin.OPEN)
    return FactDecision(
        subject=subject,
        value=observation.value,
        origin=observation.origin,
        by=observation.measured_by,
        pieces=observation.pieces,
        evidence=observation.evidence,
    )


def _observe(db, draft, fact, *, invocation_id=None, ingestion_key=None, heard=None,
             heard_seq=None):
    registry.stack().measurements.check(fact.subject, fact.value)
    if ingestion_key is not None:
        previous = db.scalar(
            select(PipelineObservation).where(
                PipelineObservation.draft_id == draft.id,
                PipelineObservation.ingestion_key == ingestion_key,
                PipelineObservation.subject == fact.subject,
            )
        )
        if previous is not None:
            if _fact(previous, fact.subject) != fact:
                raise ValueError("one evidence delivery cannot report two different observations")
            return previous
    observation = PipelineObservation(
        id=token_hex(16),
        draft_id=draft.id,
        subject=fact.subject,
        value=fact.value,
        origin=fact.origin,
        measured_by=fact.by,
        pieces=fact.pieces,
        evidence=fact.evidence.model_dump(mode="json") if fact.evidence else None,
        invocation_id=invocation_id,
        ingestion_key=ingestion_key,
        seq=_seq(draft),
        at=datetime.now(UTC),
        legacy=False,
        heard=heard,
        heard_seq=heard_seq,
    )
    db.add(observation)
    db.flush()
    db.add(PipelineEvidenceAccess(draft_id=draft.id, observation_id=observation.id))
    db.flush()
    return observation


def observe(
    draft_id,
    subject,
    value,
    *,
    origin=FactOrigin.MEASURED,
    by=None,
    pieces=(),
    evidence=None,
    invocation_id=None,
    ingestion_key=None,
):
    fact = FactDecision(
        subject=subject, value=value, origin=origin, by=by, pieces=list(pieces), evidence=evidence
    )
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _observe(
            db, draft, fact, invocation_id=invocation_id, ingestion_key=ingestion_key
        ).id


def set_fact(
    draft_id,
    subject,
    value,
    *,
    who,
    expected_revision=None,
    actor_kind=ActorKind.PERSON,
    proposal_id=None,
    heard=None,
    heard_seq=None,
):
    fact = FactDecision(
        subject=subject,
        value=value,
        origin=FactOrigin.OPEN if value is None else FactOrigin.PERSON_SAID,
    )
    registry.stack().measurements.get(subject)
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        for selected, revision in _current(db, draft_id, "fact"):
            if selected.subject_key == subject:
                old = _observation(db, revision.observation_id)
                if _fact(old, subject) == fact:
                    return _write(
                        db,
                        draft,
                        "fact",
                        subject,
                        {"observation_id": revision.observation_id},
                        who=who,
                        actor_kind=actor_kind,
                        action="retain",
                        acknowledge=True,
                        proposal_id=proposal_id,
                    ).id
        observation = (
            _observe(db, draft, fact, heard=heard, heard_seq=heard_seq)
            if value is not None else None
        )
        return _write(
            db,
            draft,
            "fact",
            subject,
            _heard({"observation_id": observation.id if observation else None}, heard, heard_seq),
            who=who,
            actor_kind=actor_kind,
            action="select" if observation else "retract",
            proposal_id=proposal_id,
        ).id


def select_observation(
    draft_id, subject, observation_id, *, who, expected_revision=None, proposal_id=None
):
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        if db.get(PipelineEvidenceAccess, (draft_id, observation_id)) is None:
            raise ValueError("this draft has no access to the evidence")
        observation = db.get(PipelineObservation, observation_id)
        if observation.subject != subject:
            raise ValueError("this evidence answers a different subject")
        return _write(
            db,
            draft,
            "fact",
            subject,
            {"observation_id": observation_id},
            who=who,
            proposal_id=proposal_id,
        ).id


def retain_fact(draft_id, subject, *, who, expected_revision=None):
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        for selected, revision in _current(db, draft_id, "fact"):
            if selected.subject_key == subject:
                return _write(
                    db,
                    draft,
                    "fact",
                    subject,
                    {"observation_id": revision.observation_id},
                    who=who,
                    action="retain",
                    acknowledge=True,
                ).id
        raise ValueError("there is no current fact to retain")


def read(draft_id):
    with session_scope() as db:
        _draft(db, draft_id)
        return Decisions(
            inputs=[
                InputDecision(
                    key=s.subject_key,
                    type_id=r.type_id,
                    name=r.name,
                    states=r.states,
                    present=r.present,
                    origin=r.origin,
                )
                for s, r in _current(db, draft_id, "input")
            ],
            wants=[
                WantDecision(
                    type_id=r.type_id,
                    states=r.states,
                    present=r.present,
                    states_order=r.states_order,
                )
                for s, r in _current(db, draft_id, "want")
            ],
            facts=[
                _fact(_observation(db, r.observation_id), s.subject_key)
                for s, r in _current(db, draft_id, "fact")
            ],
            producers=[
                ProducerChoice(site=Site(type_id=r.type_id, states=r.states), contract=r.contract)
                for s, r in _current(db, draft_id, "producer")
            ],
            parameters=[
                ParameterChoice(name=r.name, value=r.value)
                for s, r in _current(db, draft_id, "parameter")
            ],
            roles=[RoleChoice(role=r.role, absent=r.absent)
                   for s, r in _current(db, draft_id, "role")],
            exclusions=[
                ExclusionChoice(site=Site(type_id=r.type_id, states=r.states),
                                contract=r.contract, excluded=r.excluded)
                for s, r in _current(db, draft_id, "exclusion")
            ],
            sources=[SourceChoice(consumer=r.consumer, port=r.port, producer=r.producer)
                     for s, r in _current(db, draft_id, "source")],
        )


def goal(draft_id):
    return read(draft_id).goal(registry.stack().measurements)


def _site_key(site):
    return json.dumps(site.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def import_goal(draft_id, goal: Goal, *, who, expected_revision=None):
    decisions = Decisions.from_goal(goal)
    # Validate the full profile before writing even the first subject.
    decisions.goal(registry.stack().measurements)
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        families = {
            "input": [
                (i.key, i.model_dump(exclude={"key"}, mode="json")) for i in decisions.inputs
            ],
            "want": [(w.type_id, w.model_dump(mode="json")) for w in decisions.wants],
            "producer": [
                (
                    _site_key(p.site),
                    {
                        "type_id": p.site.type_id,
                        "states": sorted(p.site.states),
                        "contract": p.contract,
                    },
                )
                for p in decisions.producers
            ],
            "parameter": [(p.name, p.model_dump(mode="json")) for p in decisions.parameters],
            "role": [(r.role, {"role": r.role, "absent": True}) for r in decisions.roles],
            "exclusion": [
                (exclusion_key(e.site, e.contract),
                 {"type_id": e.site.type_id, "states": sorted(e.site.states),
                  "contract": e.contract, "excluded": True})
                for e in decisions.exclusions
            ],
            "source": [
                (source_key(p.consumer, p.port),
                 {"consumer": p.consumer, "port": p.port, "producer": p.producer})
                for p in decisions.sources
            ],
        }
        for family, values in families.items():
            included = {key for key, _ in values}
            for subject, revision in _current(db, draft_id, family):
                if subject.subject_key not in included:
                    fields = {name: getattr(revision, name) for name in _FIELDS[family]}
                    field, withdrawn = _WITHDRAWN[family]
                    fields[field] = withdrawn
                    _write(
                        db, draft, family, subject.subject_key, fields, who=who, action="retract"
                    )
            for position, (key, fields) in enumerate(values):
                if family == "input":
                    old = next(
                        (r for s, r in _current(db, draft_id, family) if s.subject_key == key), None
                    )
                    if old is not None and all(
                        getattr(old, name) == value
                        for name, value in fields.items()
                        if name != "origin"
                    ):
                        fields = {**fields, "origin": old.origin}
                _write(db, draft, family, key, fields, who=who, action="import", position=position)
        facts = {f.subject: f for f in decisions.facts}
        for subject, _revision in _current(db, draft_id, "fact"):
            if subject.subject_key not in facts:
                _write(
                    db,
                    draft,
                    "fact",
                    subject.subject_key,
                    {"observation_id": None},
                    who=who,
                    action="retract",
                )
        for fact in decisions.facts:
            previous = next(
                (r for s, r in _current(db, draft_id, "fact") if s.subject_key == fact.subject),
                None,
            )
            observation = _observation(db, previous.observation_id) if previous else None
            if previous and _fact(observation, fact.subject) == fact:
                continue
            observation = _observe(db, draft, fact) if fact.origin != FactOrigin.OPEN else None
            _write(
                db,
                draft,
                "fact",
                fact.subject,
                {"observation_id": observation.id if observation else None},
                who=who,
                action="import",
            )


def history(draft_id, subject):
    with session_scope() as db:
        draft = db.get(PipelineDraft, draft_id)
        if draft is None:
            raise KeyError(draft_id)
        rows = db.execute(
            select(PipelineFact, PipelineFactRevision)
            .join(PipelineFactRevision, PipelineFact.id == PipelineFactRevision.subject_id)
            .where(PipelineFact.draft_id == draft_id, PipelineFact.subject_key == subject)
        ).all()
        selected_ids = {r.observation_id for s, r in rows}
        result = []
        if not rows:
            inputs = db.execute(
                select(PipelineInput, PipelineInputRevision)
                .join(PipelineInputRevision, PipelineInput.id == PipelineInputRevision.subject_id)
                .where(PipelineInput.draft_id == draft_id, PipelineInput.subject_key == subject)
            ).all()
            for selected, revision in inputs:
                result.append(
                    dict(
                        seq=revision.seq,
                        value=None if revision.origin == "open" else revision.present,
                        origin=revision.origin,
                        selected=True,
                        current=selected.current_id == revision.id,
                        revision_id=revision.id,
                        observation_id=None,
                        actor_kind=revision.actor_kind,
                        who=revision.who,
                        action=revision.action,
                        at=revision.at,
                        legacy=revision.legacy,
                        observed_at=None,
                    )
                )
        for s, revision in rows:
            observation = _observation(db, revision.observation_id)
            fact = _fact(observation, subject)
            result.append(
                dict(
                    seq=revision.seq,
                    value=fact.value,
                    origin=fact.origin.value,
                    selected=True,
                    current=s.current_id == revision.id,
                    revision_id=revision.id,
                    observation_id=revision.observation_id,
                    actor_kind=revision.actor_kind,
                    who=revision.who,
                    action=revision.action,
                    at=revision.at,
                    legacy=revision.legacy,
                    observed_at=observation.at if observation else None,
                )
            )
        observations = db.scalars(
            select(PipelineObservation)
            .join(
                PipelineEvidenceAccess,
                PipelineEvidenceAccess.observation_id == PipelineObservation.id,
            )
            .where(
                PipelineEvidenceAccess.draft_id == draft_id, PipelineObservation.subject == subject
            )
        ).all()
        for observation in observations:
            if observation.id not in selected_ids:
                access = db.get(PipelineEvidenceAccess, (draft_id, observation.id))
                result.append(
                    dict(
                        seq=observation.seq,
                        value=observation.value,
                        origin=observation.origin,
                        selected=False,
                        current=False,
                        observation_id=observation.id,
                        at=observation.at,
                        observed_at=observation.at,
                        action="observed",
                        legacy=observation.legacy,
                        acknowledged_as=access.acknowledged_as,
                        acknowledged_at=access.acknowledged_at,
                        acknowledged_by=access.acknowledged_by,
                        acknowledged_kind=access.acknowledged_kind,
                    )
                )
        if draft.forked_from:
            inherited = history(draft.forked_from, subject)
            inherited = [
                dict(
                    entry,
                    current=False,
                    inherited=True,
                    source_draft_id=entry.get("source_draft_id", draft.forked_from),
                )
                for entry in inherited
                if entry["seq"] <= draft.fork_sequence
            ]
            # Parent acknowledgements after the fork are not part of this snapshot.
            for entry in inherited:
                if entry.get("acknowledged_at") and entry["acknowledged_at"] > draft.fork_at:
                    for key in (
                        "acknowledged_as",
                        "acknowledged_at",
                        "acknowledged_by",
                        "acknowledged_kind",
                    ):
                        entry[key] = None
            parent_observations = {entry.get("observation_id") for entry in inherited}
            result = [
                entry
                for entry in result
                if entry["selected"] or entry.get("observation_id") not in parent_observations
            ]
            result = inherited + result
        return sorted(result, key=lambda entry: entry["seq"])


class ObservationOutcome(StrEnum):
    UNKNOWN = "unknown"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"


def assess_observation(draft_id, observation_id):
    """A domain result for chat routing; assessment never selects the evidence."""
    with session_scope() as db:
        _draft(db, draft_id)
        if db.get(PipelineEvidenceAccess, (draft_id, observation_id)) is None:
            raise ValueError("this draft has no access to the evidence")
        observed = db.get(PipelineObservation, observation_id)
        for subject, revision in _current(db, draft_id, "fact"):
            if subject.subject_key == observed.subject:
                current = _observation(db, revision.observation_id)
                if current is None:
                    return ObservationOutcome.UNKNOWN
                return (
                    ObservationOutcome.AGREEMENT
                    if current.value == observed.value
                    else ObservationOutcome.DISAGREEMENT
                )
        return ObservationOutcome.UNKNOWN


_FIELDS = {
    "input": ("type_id", "name", "states", "present", "origin"),
    "want": ("type_id", "states", "present"),
    "producer": ("type_id", "states", "contract"),
    "parameter": ("name", "value"),
    "role": ("role", "absent"),
    "exclusion": ("type_id", "states", "contract", "excluded"),
    "source": ("consumer", "port", "producer"),
}

_WITHDRAWN = {
    "input": ("present", False),
    "want": ("present", False),
    "producer": ("contract", None),
    "parameter": ("value", None),
    "role": ("absent", False),
    "exclusion": ("excluded", False),
    "source": ("producer", None),
}
"""The field a retraction sets, and to what, per family."""


def _release(draft_id, family, key, *, who, expected_revision=None):
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        for subject, revision in _current(db, draft_id, family):
            if subject.subject_key == key:
                fields = {name: getattr(revision, name) for name in _FIELDS[family]}
                field, withdrawn = _WITHDRAWN[family]
                fields[field] = withdrawn
                return _write(db, draft, family, key, fields, who=who, action="retract").id
        raise ValueError(f"there is no current {family} choice for {key}")


def withdraw_input(draft_id, key, *, who, expected_revision=None):
    return _release(draft_id, "input", key, who=who, expected_revision=expected_revision)


def release_parameter(draft_id, name, *, who, expected_revision=None):
    return _release(draft_id, "parameter", name, who=who, expected_revision=expected_revision)


def release_producer(draft_id, site: Site, *, who, expected_revision=None):
    return _release(
        draft_id, "producer", _site_key(site), who=who, expected_revision=expected_revision
    )


def set_input(
    draft_id, decision: InputDecision, *, who, actor_kind=ActorKind.PERSON, proposal_id=None,
    heard=None, heard_seq=None,
):
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _write(
            db,
            draft,
            "input",
            decision.key,
            _heard(decision.model_dump(mode="json", exclude={"key"}), heard, heard_seq),
            who=who,
            actor_kind=actor_kind,
            proposal_id=proposal_id,
        ).id


def confirmed_goal(draft_id):
    return goal(draft_id) if confirmed(draft_id) else None


def confirmed(draft_id) -> bool:
    """Whether *That's right* was ever pressed for this draft — recorded, not inferred from a
    present want, which the rows hold from the first sentence on (Part I.0 §6.2)."""
    with session_scope() as db:
        draft = db.get(PipelineDraft, draft_id)
        if draft is None:
            raise KeyError(draft_id)
        return draft.confirmed_revision is not None


def confirm(draft_id) -> int:
    with session_scope() as db:
        draft = _draft(db, draft_id)
        draft.confirmed_revision = draft.decision_revision
        db.flush()
        return draft.confirmed_revision


def _current_of(db, draft_id, family, key):
    return next((r for s, r in _current(db, draft_id, family) if s.subject_key == key), None)


def set_want(draft_id, type_id, *, who, actor_kind=ActorKind.PERSON, heard=None, heard_seq=None,
             proposal_id=None):
    with session_scope() as db:
        draft = _draft(db, draft_id)
        old = _current_of(db, draft_id, "want", type_id)
        fields = {
            "type_id": type_id,
            "states": list(old.states) if old else [],
            "present": True,
            "states_order": old.states_order if old else None,
        }
        return _write(db, draft, "want", type_id, _heard(fields, heard, heard_seq), who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


def retract_want(draft_id, type_id, *, who, actor_kind=ActorKind.PERSON, proposal_id=None):
    """`None` when nothing was wanted: retracting what was never recorded changes nothing."""
    with session_scope() as db:
        draft = _draft(db, draft_id)
        old = _current_of(db, draft_id, "want", type_id)
        if old is None or not old.present:
            return None
        fields = {"type_id": type_id, "states": list(old.states), "present": False,
                  "states_order": old.states_order}
        return _write(db, draft, "want", type_id, fields, who=who, actor_kind=actor_kind,
                      action="retract", proposal_id=proposal_id).id


def require_states(draft_id, type_id, states, *, who, actor_kind=ActorKind.PERSON, heard=None,
                   heard_seq=None, proposal_id=None):
    with session_scope() as db:
        draft = _draft(db, draft_id)
        old = _current_of(db, draft_id, "want", type_id)
        if old is None or not old.present:
            raise ValueError(coded("MI0204", f"{type_id} is not something this goal wants"))
        fields = {"type_id": type_id, "states": sorted(states), "present": True,
                  "states_order": old.states_order}
        return _write(db, draft, "want", type_id, _heard(fields, heard, heard_seq), who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


def pin_producer(draft_id, site: Site, contract, *, who, actor_kind=ActorKind.PERSON, heard=None,
                 heard_seq=None, proposal_id=None):
    with session_scope() as db:
        draft = _draft(db, draft_id)
        # **Pinning a tool withdraws its exclusion at that site** (A1): the later intent wins,
        # and the two are never both applied.
        _withdraw(db, draft, "exclusion", exclusion_key(site, contract), who=who,
                  actor_kind=actor_kind)
        fields = {"type_id": site.type_id, "states": sorted(site.states), "contract": contract}
        return _write(db, draft, "producer", _site_key(site), _heard(fields, heard, heard_seq),
                      who=who, actor_kind=actor_kind, proposal_id=proposal_id).id


def exclusion_key(site: Site, contract) -> str:
    """An exclusion's subject: its site and its tool."""
    return f"{_site_key(site)}|{contract}"


def source_key(consumer, port) -> str:
    """A source pin's subject: the consumer and its port."""
    return f"{consumer}|{port}"


def _withdraw(db, draft, family, key, *, who, actor_kind=ActorKind.PERSON):
    """Retract `key`'s current choice in `family` if one is active; nothing otherwise."""
    current = _current_of(db, draft.id, family, key)
    field, withdrawn = _WITHDRAWN[family]
    if current is None or getattr(current, field) == withdrawn:
        return
    fields = {name: getattr(current, name) for name in _FIELDS[family]}
    fields[field] = withdrawn
    _write(db, draft, family, key, fields, who=who, actor_kind=actor_kind, action="retract")


def switch_off_role(draft_id, role, *, who, actor_kind=ActorKind.PERSON, proposal_id=None,
                    expected_revision=None):
    """A role a person switched off (A1)."""
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        return _write(db, draft, "role", role, {"role": role, "absent": True}, who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


def exclude_producer(draft_id, site: Site, contract, *, who, actor_kind=ActorKind.PERSON,
                     proposal_id=None, expected_revision=None):
    """A tool a person excluded at a site (A1). Withdraws a pin of that tool there."""
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        pinned = _current_of(db, draft_id, "producer", _site_key(site))
        if pinned is not None and pinned.contract == contract:
            _withdraw(db, draft, "producer", _site_key(site), who=who, actor_kind=actor_kind)
        fields = {"type_id": site.type_id, "states": sorted(site.states), "contract": contract,
                  "excluded": True}
        return _write(db, draft, "exclusion", exclusion_key(site, contract), fields, who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


def pin_source(draft_id, consumer, port, producer, *, who, actor_kind=ActorKind.PERSON,
               proposal_id=None, expected_revision=None):
    """What a person chose to feed a step's input (A1)."""
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        fields = {"consumer": consumer, "port": port, "producer": producer}
        return _write(db, draft, "source", source_key(consumer, port), fields, who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


_INTENTS = ("role", "exclusion", "source")


def release_intent(draft_id, family, key, *, who, expected_revision=None):
    """Withdraw a person's structural intent (A1); its history stays."""
    if family not in _INTENTS:
        raise ValueError(f"{family!r} is not a structural intent")
    return _release(draft_id, family, key, who=who, expected_revision=expected_revision)


def intent_history(draft_id, family, key) -> list[dict]:
    """Every revision of one structural intent, oldest first: who, when, by which kind of
    actor, and what was done (A1) — so a reader can say *you excluded STAR on 22 Oct*."""
    if family not in _INTENTS:
        raise ValueError(f"{family!r} is not a structural intent")
    subject_type, revision_type = _FAMILIES[family]
    with session_scope() as db:
        rows = db.scalars(
            select(revision_type)
            .join(subject_type, subject_type.id == revision_type.subject_id)
            .where(subject_type.draft_id == draft_id, subject_type.subject_key == key)
            .order_by(revision_type.seq, revision_type.at)
        ).all()
        return [dict(seq=r.seq, who=r.who, actor_kind=r.actor_kind, action=r.action, at=r.at,
                     **{name: getattr(r, name) for name in _FIELDS[family]}) for r in rows]


def set_parameter(draft_id, name, value, *, who, actor_kind=ActorKind.PERSON, heard=None,
                  heard_seq=None, proposal_id=None):
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _write(db, draft, "parameter", name,
                      _heard({"name": name, "value": value}, heard, heard_seq), who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


@dataclass(frozen=True)
class Asked:
    phrase: str
    heard_seq: int | None


def set_asked(draft_id, phrase, *, who, actor_kind=ActorKind.PERSON, heard=None, heard_seq=None,
              proposal_id=None):
    key = " ".join(phrase.split()).casefold()[:400]
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _write(db, draft, "asked", key,
                      _heard({"phrase": phrase, "present": True}, heard, heard_seq), who=who,
                      actor_kind=actor_kind, proposal_id=proposal_id).id


def retract_asked(draft_id, phrase, *, who, actor_kind=ActorKind.PERSON, proposal_id=None):
    key = " ".join(phrase.split()).casefold()[:400]
    with session_scope() as db:
        draft = _draft(db, draft_id)
        old = _current_of(db, draft_id, "asked", key)
        if old is None or not old.present:
            return None
        return _write(db, draft, "asked", key, {"phrase": old.phrase, "present": False},
                      who=who, actor_kind=actor_kind, action="retract",
                      proposal_id=proposal_id).id


def read_asked(draft_id) -> list[Asked]:
    with session_scope() as db:
        return [Asked(phrase=r.phrase, heard_seq=r.heard_seq)
                for _s, r in _current(db, draft_id, "asked") if r.present]


def heard_of(draft_id) -> dict[tuple[str, str], tuple[str, int | None]]:
    """`(family, key)` → the words each current decision was heard in. A fact's words live on
    the observation it selects."""
    found = {}
    with session_scope() as db:
        for family in ("input", "want", "producer", "parameter", "asked", *_INTENTS):
            for subject, revision in _current(db, draft_id, family):
                if revision.heard is not None:
                    found[(family, subject.subject_key)] = (revision.heard, revision.heard_seq)
        facts = [(s.subject_key, r.observation_id) for s, r in _current(db, draft_id, "fact")
                 if r.observation_id]
        observations = {o.id: o for o in db.scalars(
            select(PipelineObservation).where(PipelineObservation.id.in_([i for _, i in facts]))
        )} if facts else {}
        for key, observation_id in facts:
            observation = observations.get(observation_id)
            if observation is not None and observation.heard is not None:
                found[("fact", key)] = (observation.heard, observation.heard_seq)
    return found


@dataclass(frozen=True)
class ReviewState:
    """The reviews that still hold, and every step reviewed at least once: a superseded or
    removed review keeps its subject, so one query answers both."""

    retained: list
    previously_reviewed: frozenset[str]


def _review_state_in(db, draft_id) -> ReviewState:
    from mendel_authoring.reviews import Reviewed

    current = _current(db, draft_id, "review")
    return ReviewState(
        retained=[
            Reviewed(
                node=r.node,
                by=r.who,
                actor_kind=r.actor_kind,
                contract=r.contract,
                fingerprint=r.fingerprint,
            )
            for s, r in current
            if r.status == "reviewed"
        ],
        previously_reviewed=frozenset(r.node for s, r in current),
    )


def _reviews_in(db, draft_id):
    return _review_state_in(db, draft_id).retained


def review_state(draft_id) -> ReviewState:
    with session_scope() as db:
        _draft(db, draft_id)
        return _review_state_in(db, draft_id)


def reviews(draft_id):
    return review_state(draft_id).retained


def record_review(draft_id, blueprint, node, *, who, actor_kind=ActorKind.PERSON, proposal_id=None):
    from mendel_authoring.reviews import review

    chosen = review(blueprint, node, who, actor_kind=actor_kind)
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _write(
            db,
            draft,
            "review",
            node,
            {
                "node": node,
                "contract": chosen.contract,
                "fingerprint": chosen.fingerprint,
                "status": "reviewed",
                "decision_revision": draft.decision_revision,
                "proposal_id": proposal_id,
            },
            who=who,
            actor_kind=actor_kind,
        ).id


def cascade_reviews(draft_id, before, fresh):
    from mendel_authoring.reviews import Applicability, cascade

    with session_scope() as db:
        draft = _draft(db, draft_id)
        active = _reviews_in(db, draft_id)
        applicability = cascade(before, fresh, active)
        by_node = {o.node: o for o in applicability}
        for subject, revision in _current(db, draft_id, "review"):
            applied = by_node.get(subject.subject_key)
            if applied is not None and applied.status is not Applicability.RETAINED:
                _write(
                    db,
                    draft,
                    "review",
                    subject.subject_key,
                    {
                        "node": revision.node,
                        "contract": revision.contract,
                        "fingerprint": revision.fingerprint,
                        "status": applied.status.value,
                        "decision_revision": revision.decision_revision,
                        "proposal_id": revision.proposal_id,
                    },
                    who="resolver",
                    actor_kind=ActorKind.RESOLVER,
                )
        return applicability


def _acknowledge(db, draft, observation_id, disposition, *, who, actor_kind):
    from mendel_api.decision_models import EvidenceDisposition

    admitted = Attribution(kind=actor_kind, who=who)
    access = db.get(PipelineEvidenceAccess, (draft.id, observation_id))
    if access is None:
        raise ValueError("this draft has no access to the evidence")
    if access.acknowledged_as is None:
        access.acknowledged_as = EvidenceDisposition(disposition).value
        access.acknowledged_revision = draft.decision_revision
        access.acknowledged_at = datetime.now(UTC)
        access.acknowledged_by = admitted.who
        access.acknowledged_kind = admitted.kind.value


def acknowledge_observation(
    draft_id, observation_id, disposition, *, who, actor_kind=ActorKind.PERSON
):
    """An acknowledgement is metadata about evidence, never a selected factual value."""
    with session_scope() as db:
        draft = _draft(db, draft_id)
        _acknowledge(db, draft, observation_id, disposition, who=who, actor_kind=actor_kind)


def pending_evidence(draft_id):
    """Unseen evidence, compared afresh; obsolete/equal observations never reopen a question."""
    with session_scope() as db:
        draft = _draft(db, draft_id)
        selections = {s.subject_key: r for s, r in _current(db, draft_id, "fact")}
        selected_ids = set(
            db.scalars(
                select(PipelineFactRevision.observation_id).where(
                    PipelineFactRevision.draft_id == draft_id
                )
            )
        )
        observations = db.scalars(
            select(PipelineObservation)
            .join(
                PipelineEvidenceAccess,
                PipelineEvidenceAccess.observation_id == PipelineObservation.id,
            )
            .where(
                PipelineEvidenceAccess.draft_id == draft_id,
                PipelineEvidenceAccess.acknowledged_as.is_(None),
            )
            .order_by(PipelineObservation.seq, PipelineObservation.subject, PipelineObservation.id)
        )
        unseen = []
        for observed in observations:
            if observed.id in selected_ids:
                continue
            revision = selections.get(observed.subject)
            active = _fact(
                _observation(db, revision.observation_id) if revision else None, observed.subject
            )
            if observed.value == active.value:
                _acknowledge(
                    db,
                    draft,
                    observed.id,
                    "obsolete",
                    who="resolver",
                    actor_kind=ActorKind.RESOLVER,
                )
                continue
            unseen.append(
                dict(
                    subject=observed.subject,
                    observation_id=observed.id,
                    observed_value=observed.value,
                    observed_origin=observed.origin,
                    current_value=active.value,
                    current_origin=active.origin.value,
                    current_revision_id=revision.id if revision else None,
                )
            )
        return unseen


def inherit_in(db, parent, child):
    """Reference the parent's evidence and inherit selections, never copy inspections.

    The caller holds the parent lock. Old selections stay in the parent's frozen
    history; the new authored walk starts without approvals of the manual graph.
    """
    grants = db.scalars(
        select(PipelineEvidenceAccess).where(PipelineEvidenceAccess.draft_id == parent.id)
    ).all()
    child.decision_sequence = parent.decision_sequence
    for grant in grants:
        observation = db.get(PipelineObservation, grant.observation_id)
        child.decision_sequence = max(child.decision_sequence, observation.seq)
        db.add(
            PipelineEvidenceAccess(
                draft_id=child.id,
                observation_id=grant.observation_id,
                inherited=True,
                **{
                    key: getattr(grant, key)
                    for key in (
                        "acknowledged_as",
                        "acknowledged_revision",
                        "acknowledged_at",
                        "acknowledged_by",
                        "acknowledged_kind",
                    )
                },
            )
        )
    db.flush()
    old_selected = set(
        db.scalars(
            select(PipelineFactRevision.observation_id).where(
                PipelineFactRevision.draft_id == parent.id
            )
        )
    )
    for grant in grants:
        if grant.observation_id in old_selected:
            _acknowledge(
                db,
                child,
                grant.observation_id,
                "obsolete",
                who="resolver",
                actor_kind=ActorKind.RESOLVER,
            )
    metadata = {
        "id",
        "draft_id",
        "subject_id",
        "seq",
        "at",
        "action",
        "actor_kind",
        "who",
        "legacy",
        "turn_id",
        "proposal_id",
    }
    for family, (_, revision_type) in _FAMILIES.items():
        if family == "review":
            continue
        for subject, revision in _current(db, parent.id, family):
            fields = {
                column.key: getattr(revision, column.key)
                for column in revision_type.__table__.columns
                if column.key not in metadata
            }
            _write(
                db,
                child,
                family,
                subject.subject_key,
                fields,
                who=revision.who,
                actor_kind=revision.actor_kind,
                legacy=revision.legacy,
                action="inherit",
                position=subject.position,
            )
    child.projection_current = False
    db.flush()


def answers_in(db, draft_id):
    """Facts selected by an answered offer, not today's values substituted into yesterday."""
    result = {}
    for subject, revision in db.execute(
        select(PipelineFact, PipelineFactRevision)
        .join(PipelineFactRevision, PipelineFact.id == PipelineFactRevision.subject_id)
        .where(PipelineFact.draft_id == draft_id, PipelineFactRevision.proposal_id.is_not(None))
        .order_by(PipelineFactRevision.seq)
    ):
        fact = _fact(_observation(db, revision.observation_id), subject.subject_key)
        result.setdefault(revision.proposal_id, []).append(
            dict(
                kind="measurement",
                subject=subject.subject_key,
                value=fact.value,
                source=fact.origin,
            )
        )
    for _subject, revision in db.execute(
        select(PipelineInput, PipelineInputRevision)
        .join(PipelineInputRevision, PipelineInput.id == PipelineInputRevision.subject_id)
        .where(PipelineInput.draft_id == draft_id, PipelineInputRevision.proposal_id.is_not(None))
        .order_by(PipelineInputRevision.seq)
    ):
        result.setdefault(revision.proposal_id, []).append(
            dict(kind="input", subject=revision.type_id, source=revision.origin)
        )
    return result
