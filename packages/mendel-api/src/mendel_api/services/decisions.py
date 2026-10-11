"""Selected draft decisions, immutable observations, and ordered factual history.

All writes lock the draft first and join the dispatcher's transaction. Observations
never select themselves: only an explicit selection changes the goal.
"""

import json
from datetime import UTC, datetime
from enum import StrEnum
from secrets import token_hex

from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal, Site
from mendel_authoring.decisions import (
    ActorKind,
    Attribution,
    Decisions,
    FactDecision,
    FactOrigin,
    InputDecision,
    ParameterChoice,
    ProducerChoice,
    WantDecision,
)
from sqlalchemy import select

from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineDraft,
    PipelineEvidenceAccess,
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
}


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
    return db.execute(select(subject, revision).join(
        revision, subject.current_id == revision.id
    ).where(subject.draft_id == draft_id).order_by(subject.position, subject.subject_key)).all()


def _write(db, draft, family, key, fields, *, who, actor_kind=ActorKind.PERSON,
           action="select", position=None, acknowledge=False):
    attribution = Attribution(kind=actor_kind, who=who)
    subject_type, revision_type = _FAMILIES[family]
    subject = db.scalar(select(subject_type).where(
        subject_type.draft_id == draft.id, subject_type.subject_key == key
    ))
    current = db.get(revision_type, subject.current_id) if subject else None
    same = current is not None and all(getattr(current, name) == value
                                       for name, value in fields.items())
    reordered = subject is not None and position is not None and position != subject.position
    if same and not acknowledge and not reordered:
        return current
    revision_id = token_hex(16)
    if subject is None:
        subject = subject_type(id=token_hex(16), draft_id=draft.id, subject_key=key,
                               current_id=revision_id, position=position or 0)
        db.add(subject)
        db.flush()  # Current-pointer FK is deferred, revision's subject FK is immediate.
    elif position is not None:
        subject.position = position
    revision = revision_type(id=revision_id, draft_id=draft.id, subject_id=subject.id,
                             seq=_seq(draft), at=datetime.now(UTC), action=action,
                             actor_kind=attribution.kind, who=attribution.who,
                             legacy=attribution.legacy, **fields)
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
    return FactDecision(subject=subject, value=observation.value, origin=observation.origin,
                        by=observation.measured_by, pieces=observation.pieces,
                        evidence=observation.evidence)


def _observe(db, draft, fact, *, invocation_id=None):
    registry.stack().measurements.check(fact.subject, fact.value)
    observation = PipelineObservation(
        id=token_hex(16), draft_id=draft.id, subject=fact.subject, value=fact.value,
        origin=fact.origin, measured_by=fact.by, pieces=fact.pieces,
        evidence=fact.evidence.model_dump(mode="json") if fact.evidence else None,
        invocation_id=invocation_id, seq=_seq(draft), at=datetime.now(UTC), legacy=False,
    )
    db.add(observation)
    db.flush()
    db.add(PipelineEvidenceAccess(draft_id=draft.id, observation_id=observation.id))
    db.flush()
    return observation


def observe(draft_id, subject, value, *, origin=FactOrigin.MEASURED, by=None,
            pieces=(), evidence=None, invocation_id=None):
    fact = FactDecision(subject=subject, value=value, origin=origin, by=by,
                        pieces=list(pieces), evidence=evidence)
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _observe(db, draft, fact, invocation_id=invocation_id).id


def set_fact(draft_id, subject, value, *, who, expected_revision=None,
             actor_kind=ActorKind.PERSON):
    fact = FactDecision(subject=subject, value=value,
                        origin=FactOrigin.OPEN if value is None else FactOrigin.PERSON_SAID)
    registry.stack().measurements.get(subject)
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        for selected, revision in _current(db, draft_id, "fact"):
            if selected.subject_key == subject:
                old = _observation(db, revision.observation_id)
                if _fact(old, subject) == fact:
                    return _write(db, draft, "fact", subject,
                                  {"observation_id": revision.observation_id}, who=who,
                                  actor_kind=actor_kind, action="retain", acknowledge=True).id
        observation = _observe(db, draft, fact) if value is not None else None
        return _write(db, draft, "fact", subject,
                      {"observation_id": observation.id if observation else None},
                      who=who, actor_kind=actor_kind,
                      action="select" if observation else "retract").id


def select_observation(draft_id, subject, observation_id, *, who, expected_revision=None):
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        if db.get(PipelineEvidenceAccess, (draft_id, observation_id)) is None:
            raise ValueError("this draft has no access to the evidence")
        observation = db.get(PipelineObservation, observation_id)
        if observation.subject != subject:
            raise ValueError("this evidence answers a different subject")
        return _write(db, draft, "fact", subject, {"observation_id": observation_id},
                      who=who).id


def retain_fact(draft_id, subject, *, who, expected_revision=None):
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        for selected, revision in _current(db, draft_id, "fact"):
            if selected.subject_key == subject:
                return _write(db, draft, "fact", subject,
                              {"observation_id": revision.observation_id}, who=who,
                              action="retain", acknowledge=True).id
        raise ValueError("there is no current fact to retain")


def read(draft_id):
    with session_scope() as db:
        _draft(db, draft_id)
        return Decisions(
            inputs=[InputDecision(key=s.subject_key, type_id=r.type_id, name=r.name,
                                  states=r.states, present=r.present, origin=r.origin)
                    for s, r in _current(db, draft_id, "input")],
            wants=[WantDecision(type_id=r.type_id, states=r.states, present=r.present)
                   for s, r in _current(db, draft_id, "want")],
            facts=[_fact(_observation(db, r.observation_id), s.subject_key)
                   for s, r in _current(db, draft_id, "fact")],
            producers=[ProducerChoice(site=Site(type_id=r.type_id, states=r.states),
                                      contract=r.contract)
                       for s, r in _current(db, draft_id, "producer")],
            parameters=[ParameterChoice(name=r.name, value=r.value)
                        for s, r in _current(db, draft_id, "parameter")],
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
            "input": [(i.key, i.model_dump(exclude={"key"}, mode="json"))
                      for i in decisions.inputs],
            "want": [(w.type_id, w.model_dump(mode="json")) for w in decisions.wants],
            "producer": [(_site_key(p.site), {"type_id": p.site.type_id,
                          "states": sorted(p.site.states), "contract": p.contract})
                         for p in decisions.producers],
            "parameter": [(p.name, p.model_dump(mode="json")) for p in decisions.parameters],
        }
        for family, values in families.items():
            included = {key for key, _ in values}
            for subject, revision in _current(db, draft_id, family):
                if subject.subject_key not in included:
                    fields = {name: getattr(revision, name) for name in _FIELDS[family]}
                    fields[{"input": "present", "want": "present", "producer": "contract",
                            "parameter": "value"}[family]] = (
                                False if family in ("input", "want") else None)
                    _write(db, draft, family, subject.subject_key, fields,
                           who=who, action="retract")
            for position, (key, fields) in enumerate(values):
                if family == "input":
                    old = next((r for s, r in _current(db, draft_id, family)
                                if s.subject_key == key), None)
                    if old is not None and all(getattr(old, name) == value for name, value in
                                               fields.items() if name != "origin"):
                        fields = {**fields, "origin": old.origin}
                _write(db, draft, family, key, fields, who=who, action="import", position=position)
        facts = {f.subject: f for f in decisions.facts}
        for subject, _revision in _current(db, draft_id, "fact"):
            if subject.subject_key not in facts:
                _write(db, draft, "fact", subject.subject_key, {"observation_id": None},
                       who=who, action="retract")
        for fact in decisions.facts:
            previous = next((r for s, r in _current(db, draft_id, "fact")
                             if s.subject_key == fact.subject), None)
            observation = _observation(db, previous.observation_id) if previous else None
            if previous and _fact(observation, fact.subject) == fact:
                continue
            observation = _observe(db, draft, fact) if fact.origin != FactOrigin.OPEN else None
            _write(db, draft, "fact", fact.subject,
                   {"observation_id": observation.id if observation else None},
                   who=who, action="import")


def history(draft_id, subject):
    with session_scope() as db:
        _draft(db, draft_id)
        rows = db.execute(select(PipelineFact, PipelineFactRevision).join(
            PipelineFactRevision, PipelineFact.id == PipelineFactRevision.subject_id
        ).where(PipelineFact.draft_id == draft_id, PipelineFact.subject_key == subject)).all()
        selected_ids = {r.observation_id for s, r in rows}
        result = []
        for s, revision in rows:
            observation = _observation(db, revision.observation_id)
            fact = _fact(observation, subject)
            result.append(dict(seq=revision.seq, value=fact.value, origin=fact.origin.value,
                               selected=True, current=s.current_id == revision.id,
                               revision_id=revision.id, observation_id=revision.observation_id,
                               actor_kind=revision.actor_kind, who=revision.who,
                               action=revision.action, at=revision.at,
                               observed_at=observation.at if observation else None))
        observations = db.scalars(select(PipelineObservation).join(
            PipelineEvidenceAccess,
            PipelineEvidenceAccess.observation_id == PipelineObservation.id,
        ).where(PipelineEvidenceAccess.draft_id == draft_id,
                PipelineObservation.subject == subject)).all()
        for observation in observations:
            if observation.id not in selected_ids:
                result.append(dict(seq=observation.seq, value=observation.value,
                                   origin=observation.origin, selected=False, current=False,
                                   observation_id=observation.id, at=observation.at,
                                   observed_at=observation.at))
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
                return (ObservationOutcome.AGREEMENT if current.value == observed.value
                        else ObservationOutcome.DISAGREEMENT)
        return ObservationOutcome.UNKNOWN


_FIELDS = {
    "input": ("type_id", "name", "states", "present", "origin"),
    "want": ("type_id", "states", "present"),
    "producer": ("type_id", "states", "contract"),
    "parameter": ("name", "value"),
}


def _release(draft_id, family, key, *, who, expected_revision=None):
    with session_scope() as db:
        draft = _draft(db, draft_id, expected_revision)
        for subject, revision in _current(db, draft_id, family):
            if subject.subject_key == key:
                fields = {name: getattr(revision, name) for name in _FIELDS[family]}
                fields[{"input": "present", "want": "present", "producer": "contract",
                        "parameter": "value"}[family]] = (
                            False if family in ("input", "want") else None)
                return _write(db, draft, family, key, fields, who=who, action="retract").id
        raise ValueError(f"there is no current {family} choice for {key}")


def withdraw_input(draft_id, key, *, who, expected_revision=None):
    return _release(draft_id, "input", key, who=who, expected_revision=expected_revision)


def release_parameter(draft_id, name, *, who, expected_revision=None):
    return _release(draft_id, "parameter", name, who=who, expected_revision=expected_revision)


def release_producer(draft_id, site: Site, *, who, expected_revision=None):
    return _release(draft_id, "producer", _site_key(site), who=who,
                    expected_revision=expected_revision)


def set_input(draft_id, decision: InputDecision, *, who, actor_kind=ActorKind.PERSON):
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _write(db, draft, "input", decision.key,
                      decision.model_dump(mode="json", exclude={"key"}),
                      who=who, actor_kind=actor_kind).id


def confirmed_goal(draft_id):
    current = read(draft_id)
    return (current.goal(registry.stack().measurements)
            if any(w.present for w in current.wants) else None)


def _reviews_in(db, draft_id):
    from mendel_authoring.reviews import Reviewed

    return [Reviewed(node=r.node, by=r.who, actor_kind=r.actor_kind,
                     contract=r.contract, fingerprint=r.fingerprint)
            for s, r in _current(db, draft_id, "review") if r.status == "reviewed"]


def reviews(draft_id):
    with session_scope() as db:
        _draft(db, draft_id)
        return _reviews_in(db, draft_id)


def record_review(draft_id, blueprint, node, *, who, actor_kind=ActorKind.PERSON):
    from mendel_authoring.reviews import review

    chosen = review(blueprint, node, who, actor_kind=actor_kind)
    with session_scope() as db:
        draft = _draft(db, draft_id)
        return _write(db, draft, "review", node, {
            "node": node, "contract": chosen.contract, "fingerprint": chosen.fingerprint,
            "status": "reviewed", "decision_revision": draft.decision_revision,
        }, who=who, actor_kind=actor_kind).id


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
                _write(db, draft, "review", subject.subject_key, {
                    "node": revision.node, "contract": revision.contract,
                    "fingerprint": revision.fingerprint, "status": applied.status.value,
                    "decision_revision": revision.decision_revision,
                }, who="resolver", actor_kind=ActorKind.RESOLVER)
        return applicability
