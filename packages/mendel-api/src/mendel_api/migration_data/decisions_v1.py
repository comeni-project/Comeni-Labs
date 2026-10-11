"""Frozen Part F legacy interpretation, version f7b1c5d3a942.

Inputs and results carry JSON strings, not ORM instances. Adding a new interpretation
requires another version: migrations and inventory must continue to agree on this one.
No name or timestamp proves who made a decision. Goal values prove their recorded
origin, while their migration selection's chooser remains explicitly legacy-unknown.
"""

import json
from dataclasses import dataclass

VERSION = "f7b1c5d3a942"
WAIT_NODES = {"say", "reply", "card", "step_card", "wrap", "stopped", "failed"}
SOURCE = {"goal": "person_said", "measured": "measured", "model": "model_read"}
ORIGINS = {"person_said", "measured", "model_read", "open"}


@dataclass(frozen=True)
class Snapshot:
    draft_id: str
    session_id: str | None
    phase: str | None
    at: str | None
    session_goal: str | None
    draft_goal: str | None
    facts: str
    graph: str
    provenance: str
    blueprint: str
    reviewed: str
    policy: str | None
    decision_revision: int


@dataclass(frozen=True)
class Selection:
    family: str
    key: str
    fields: str
    actor_kind: str = "unknown"
    who: str = ""
    legacy: bool = True


@dataclass(frozen=True)
class Conversion:
    disposition: str
    retired: bool = False
    reason: str | None = None
    selections: tuple[Selection, ...] = ()
    observations: tuple[Selection, ...] = ()
    extraction: str | None = None
    goal: str | None = None


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _records(value, key):
    if isinstance(value, dict):
        return [{key: name, "states": states} for name, states in value.items()]
    return value or []


def goal_of(value):
    """Normalize only documented old Goal ergonomics, with no registry reinterpretation."""
    have = value.get("have", [])
    have = [{"type_id": item} if isinstance(item, str) else item for item in have]
    have = [
        dict(type_id=i["type_id"], name=i.get("name"), states=sorted(i.get("states", [])))
        for i in have
    ]
    constraints = value.get("constraints") or {}
    required = _records(constraints.get("required_states"), "type_id")
    required = [dict(type_id=r["type_id"], states=sorted(r.get("states", []))) for r in required]
    want = value.get("want") or []
    if any(r["type_id"] not in want or not r["states"] for r in required):
        raise ValueError("required states have no representable wanted output")
    if len({r["type_id"] for r in required}) != len(required):
        raise ValueError("repeated required-state records are ambiguous")
    params = constraints.get("params") or []
    if isinstance(params, dict):
        params = [{"name": name, "value": selected} for name, selected in params.items()]
    producers = constraints.get("producers") or []
    producers = [
        dict(
            site=dict(type_id=p["site"]["type_id"], states=sorted(p["site"].get("states", []))),
            contract=p["contract"],
        )
        for p in producers
    ]
    profile = value.get("profile") or {}
    measurements = profile.get("measurements")
    if measurements is None:
        measurements = [
            dict(measurement=k, value=v, source="goal", by=None) for k, v in sorted(profile.items())
        ]
    facts = []
    for measurement in measurements:
        if measurement.get("source", "goal") not in SOURCE:
            raise ValueError("an old evidence origin cannot be represented faithfully")
        fact = dict(
            measurement=measurement["measurement"],
            value=measurement["value"],
            source=measurement.get("source", "goal"),
            by=measurement.get("by"),
        )
        for field in ("pieces", "evidence"):
            if measurement.get(field):
                fact[field] = measurement[field]
        facts.append(fact)
    return dict(
        have=have,
        want=want,
        constraints=dict(required_states=required, params=params, producers=producers),
        profile=dict(measurements=facts),
    )


def _selection(family, key, **fields):
    return Selection(family, key, dump(fields))


def _goal_selections(goal):
    selected = []
    used = set()
    for item in goal["have"]:
        base = item["name"] or item["type_id"]
        key, number = base, 1
        while key in used:
            number += 1
            key = f"{base}#{number}"
        used.add(key)
        selected.append(_selection("input", key, **item, present=True, origin="person_said"))
    for wanted in goal["want"]:
        states = next(
            (r["states"] for r in goal["constraints"]["required_states"] if r["type_id"] == wanted),
            [],
        )
        states_order = next(
            (
                n
                for n, r in enumerate(goal["constraints"]["required_states"])
                if r["type_id"] == wanted
            ),
            None,
        )
        selected.append(
            _selection(
                "want",
                wanted,
                type_id=wanted,
                states=states,
                states_order=states_order,
                present=True,
            )
        )
    for fact in goal["profile"]["measurements"]:
        selected.append(
            _selection(
                "fact",
                fact["measurement"],
                value=fact["value"],
                origin=SOURCE[fact["source"]],
                measured_by=fact.get("by"),
                pieces=fact.get("pieces", []),
                evidence=fact.get("evidence"),
            )
        )
    for parameter in goal["constraints"]["params"]:
        selected.append(_selection("parameter", parameter["name"], **parameter))
    for pin in goal["constraints"]["producers"]:
        selected.append(
            _selection(
                "producer",
                dump(pin["site"]),
                type_id=pin["site"]["type_id"],
                states=pin["site"]["states"],
                contract=pin["contract"],
            )
        )
    return selected


def _fact_record(fact):
    origin = fact.get("source", "open")
    if origin not in ORIGINS:
        raise ValueError("unknown old fact source")
    return _selection(
        "fact",
        fact["subject"],
        value=fact.get("value"),
        origin=origin,
        measured_by=None,
        pieces=fact.get("pieces") or [],
        evidence=fact.get("evidence"),
    )


def _manual_graph(snapshot, blueprint):
    graph = json.loads(snapshot.graph)
    reviewed = json.loads(snapshot.reviewed)
    seen = {r if isinstance(r, str) else r["node"] for r in reviewed or []}
    steps = blueprint.get("pipeline", {}).get("steps", [])
    expected = []
    edges = []
    for step in steps:
        if step["id"] not in seen:
            continue
        expected.append(
            dict(
                id=step["id"],
                contract_id=step["module"]["contract_id"],
                params=[
                    dict(name=setting["name"], value=setting["value"])
                    for setting in step.get("settings", [])
                    if setting.get("why", {}).get("source") == "model"
                ],
            )
        )
        for wired in step.get("inputs", []):
            source = wired.get("source")
            if source:
                producer, port = source.split(".", 1)
                if producer in seen:
                    edges.append(
                        dict(
                            from_node=producer,
                            from_port=port,
                            to_node=step["id"],
                            to_port=wired["port"],
                        )
                    )
    actual = [
        dict(
            id=node["id"],
            contract_id=node["contract_id"],
            params=[dict(name=p["name"], value=p["value"]) for p in node.get("params", [])],
        )
        for node in graph.get("nodes", [])
    ]

    def ordered(values):
        return sorted(dump(item) for item in values)

    return (
        ordered(actual) != ordered(expected)
        or ordered(graph.get("edges", [])) != ordered(edges)
        or bool(graph.get("channels"))
    )


def convert(snapshot: Snapshot) -> Conversion:
    if snapshot.decision_revision:
        return Conversion("already_rows")
    if snapshot.session_id is None:
        return Conversion("manual")
    if snapshot.at is not None and snapshot.at not in WAIT_NODES:
        return Conversion("obsolete_protocol", True, "obsolete_protocol")
    try:
        session_goal = json.loads(snapshot.session_goal) if snapshot.session_goal else None
        draft_goal = json.loads(snapshot.draft_goal) if snapshot.draft_goal else None
        facts = json.loads(snapshot.facts)
        observations = tuple(
            _fact_record(f)
            for f in facts
            if f.get("kind") == "measurement" and f.get("value") is not None
        )
        confirmed = draft_goal is not None
        if confirmed:
            goal = goal_of(draft_goal)
            if session_goal is not None and goal_of(session_goal) != goal:
                return Conversion("ambiguous_manual", True, "ambiguous", observations=observations)
            blueprint = json.loads(snapshot.blueprint)
            before = blueprint.get("pipeline", {}).get("goal")
            if before is not None and goal_of(before) != goal:
                return Conversion("ambiguous_manual", True, "ambiguous", observations=observations)
            manual = _manual_graph(snapshot, blueprint)
            if manual and snapshot.phase != "complete":
                return Conversion("ambiguous_manual", True, "ambiguous", observations=observations)
            selected = _goal_selections(goal)
            if len({(s.family, s.key) for s in selected}) != len(selected):
                return Conversion("ambiguous_manual", True, "ambiguous", observations=observations)
            # Without verified historical fingerprints, old reviews stay archived only.
            return Conversion(
                "manual_confirmed" if manual else "confirmed",
                selections=tuple(selected),
                observations=observations,
                goal=dump(goal),
            )
        if session_goal is None or not session_goal.get("want"):
            if snapshot.phase == "understanding":
                return Conversion("understanding")
            return Conversion("ambiguous_manual", True, "ambiguous", observations=observations)
        extraction = {
            "want": session_goal["want"],
            "constraints": session_goal.get("constraints") or {},
            "suggested": session_goal.get("suggested") or [],
            "stated": session_goal.get("stated") or [],
        }
        selected = []
        for fact in facts:
            if fact.get("kind") == "input":
                selected.append(
                    _selection(
                        "input",
                        fact["subject"],
                        type_id=fact["subject"],
                        name=None,
                        states=sorted(fact.get("states") or []),
                        present=True,
                        origin=fact.get("source", "person_said"),
                    )
                )
            elif fact.get("kind") == "measurement":
                selected.append(_fact_record(fact))
        if len({(s.family, s.key) for s in selected}) != len(selected):
            return Conversion("ambiguous_manual", True, "ambiguous", observations=observations)
        proposed = goal_of({"want": extraction["want"], "constraints": extraction["constraints"]})
        active = _goal_selections(proposed)
        active = [s for s in active if s.family in ("producer", "parameter")]
        selected.extend(active)
        return Conversion(
            "gathering",
            selections=tuple(selected),
            observations=observations,
            extraction=dump(extraction),
        )
    except (KeyError, ValueError, TypeError, AttributeError):
        return Conversion("ambiguous_manual", True, "ambiguous")


# Frozen SQL application. The only dependencies are SQLAlchemy and the snapshot above;
# application services, current Goal parsing and mutable ORM metadata are never imported.
def apply(connection, snapshot: Snapshot, converted: Conversion, *, at):
    from dataclasses import asdict
    from hashlib import sha256
    from uuid import NAMESPACE_URL, uuid5

    from sqlalchemy import text

    def identity(*parts):
        return uuid5(NAMESPACE_URL, ":".join((VERSION, snapshot.draft_id, *parts))).hex

    def execute(sql, **values):
        return connection.execute(text(sql), values)

    if execute(
        "SELECT draft_id FROM pipeline_decision_migration WHERE draft_id=:draft",
        draft=snapshot.draft_id,
    ).first():
        return False
    execute(
        """INSERT INTO pipeline_decision_migration
        (draft_id, version, disposition, reason, at, snapshot)
        VALUES (:draft, :version, :disposition, :reason, :at, CAST(:snapshot AS JSON))""",
        draft=snapshot.draft_id,
        version=VERSION,
        disposition=converted.disposition,
        reason=converted.reason,
        at=at,
        snapshot=dump(asdict(snapshot)),
    )
    if converted.disposition in ("already_rows", "manual"):
        return True
    sequence = 0
    observation_ids = {}

    def observation(selection):
        nonlocal sequence
        fields = json.loads(selection.fields)
        if fields["value"] is None:
            return None
        payload = dump(dict(subject=selection.key, **fields))
        if payload in observation_ids:
            return observation_ids[payload]
        oid = identity("observation", sha256(payload.encode()).hexdigest())
        sequence += 1
        execute(
            """INSERT INTO pipeline_observation
            (id,draft_id,subject,value,origin,pieces,evidence,measured_by,seq,at,legacy,ingestion_key)
            VALUES (:id,:draft,:subject,CAST(:value AS JSON),:origin,CAST(:pieces AS JSON),
                    CAST(:evidence AS JSON),:measured_by,:seq,:at,true,:delivery)""",
            id=oid,
            draft=snapshot.draft_id,
            subject=selection.key,
            value=dump(fields["value"]),
            origin=fields["origin"],
            pieces=dump(fields.get("pieces") or []),
            evidence=dump(fields.get("evidence")),
            measured_by=fields.get("measured_by"),
            seq=sequence,
            at=at,
            delivery=f"migration:{VERSION}:{oid}",
        )
        execute(
            """INSERT INTO pipeline_evidence_access
            (draft_id,observation_id,inherited,acknowledged_as,acknowledged_revision,
             acknowledged_at,acknowledged_by,acknowledged_kind)
            VALUES (:draft,:observation,false,'obsolete',1,:at,'migration','resolver')""",
            draft=snapshot.draft_id,
            observation=oid,
            at=at,
        )
        observation_ids[payload] = oid
        return oid

    for old in converted.observations:
        observation(old)
    families = {"input", "want", "fact", "producer", "parameter"}
    for position, selection in enumerate(converted.selections):
        if selection.family not in families:
            raise ValueError("unrecognized frozen selection family")
        fields = json.loads(selection.fields)
        if selection.family == "fact":
            fields = {"observation_id": observation(selection)}
        subject_id = identity(selection.family, selection.key)
        revision_id = identity(selection.family, selection.key, "revision")
        family = selection.family
        sequence += 1
        # The FK is deferred; the subject and its first retained revision arrive together.
        execute(
            f"""INSERT INTO pipeline_{family}
            (id,draft_id,subject_key,position,current_id)
            VALUES (:id,:draft,:key,:position,:revision)""",
            id=subject_id,
            draft=snapshot.draft_id,
            key=selection.key,
            position=position,
            revision=revision_id,
        )
        names = list(fields)
        values = {key: dump(value) if key == "states" else value for key, value in fields.items()}
        expressions = [f"CAST(:{key} AS JSON)" if key == "states" else f":{key}" for key in names]
        execute(
            f"""INSERT INTO pipeline_{family}_revision
            (id,draft_id,subject_id,seq,at,actor_kind,who,legacy,action,{",".join(names)})
            VALUES (:id,:draft,:subject,:seq,:at,'unknown','',true,'import',
                    {",".join(expressions)})""",
            id=revision_id,
            draft=snapshot.draft_id,
            subject=subject_id,
            seq=sequence,
            at=at,
            **values,
        )
    manual = converted.disposition in ("manual_confirmed", "ambiguous_manual", "obsolete_protocol")
    graph = json.loads(snapshot.graph)
    fresh = converted.disposition == "manual_confirmed" or not graph.get("nodes")
    execute(
        """UPDATE pipeline_draft SET ownership=:ownership,
        decision_revision=:revision, decision_sequence=:seq,
        projection_current=:fresh, projection_revision=:projection WHERE id=:draft""",
        ownership="manual" if manual else "authored",
        revision=1 if converted.selections else 0,
        seq=sequence,
        fresh=fresh and not converted.retired,
        projection=1 if fresh and converted.selections else None,
        draft=snapshot.draft_id,
    )
    if snapshot.session_id:
        execute(
            """UPDATE pipeline_authoring_session SET retired=:retired,
            retirement_reason=:reason, extraction=CAST(:extraction AS JSON)
            WHERE id=:session""",
            retired=converted.retired,
            reason=converted.reason,
            extraction=converted.extraction,
            session=snapshot.session_id,
        )
        policy = json.loads(snapshot.policy) if snapshot.policy else {}
        if policy:
            execute(
                """UPDATE pipeline_authoring_session SET pacing=:pacing, show_gaps=:gaps
                       WHERE id=:session""",
                pacing=policy.get("pacing"),
                gaps=policy.get("show_gaps"),
                session=snapshot.session_id,
            )
        execute(
            """UPDATE pipeline_authoring_proposal SET state='stale',settled_at=:at
                   WHERE session_id=:session AND state='pending'""",
            at=at,
            session=snapshot.session_id,
        )
        if converted.disposition in ("confirmed", "gathering"):
            # Offer the recovered goal for an explicit fresh review. No old step approval
            # is silently carried onto a semantic fingerprint it never recorded.
            goal = json.loads(converted.goal) if converted.goal else _proposed_goal(converted)
            revision = execute(
                "SELECT revision FROM pipeline_draft WHERE id=:draft", draft=snapshot.draft_id
            ).scalar_one()
            version = (
                execute(
                    "SELECT row_version FROM pipeline_authoring_session WHERE id=:id",
                    id=snapshot.session_id,
                ).scalar_one()
                + 1
            )
            context = dict(
                draft_revision=revision, decision_revision=1, session_version=version, registry=""
            )
            block = dict(
                kind="goal_summary",
                id=identity("recovered-goal"),
                goal=goal,
                have=", ".join(i["type_id"] for i in goal["have"]),
                do="Review the recovered analysis goal",
                get=", ".join(goal["want"]),
            )
            offer = dict(
                offer="goal", context=context, options={"accept": "accept"}, goal=goal, block=block
            )
            execute(
                """INSERT INTO pipeline_authoring_proposal
                (id,session_id,kind,payload,state,draft_revision,created_at)
                VALUES (:id,:session,'goal',CAST(:payload AS JSON),'pending',:revision,:at)""",
                id=identity("recovered-offer"),
                session=snapshot.session_id,
                payload=dump(offer),
                revision=revision,
                at=at,
            )
            execute(
                """UPDATE pipeline_authoring_session SET at='card',phase='goal_review',
                       row_version=:version WHERE id=:id""",
                version=version,
                id=snapshot.session_id,
            )
    return True


def _proposed_goal(converted):
    extraction = json.loads(converted.extraction)
    goal = goal_of(dict(want=extraction["want"], constraints=extraction["constraints"]))
    for selection in converted.selections:
        fields = json.loads(selection.fields)
        if selection.family == "input" and fields["present"]:
            goal["have"].append({key: fields[key] for key in ("type_id", "name", "states")})
        if selection.family == "fact" and fields["value"] is not None:
            fact = dict(
                measurement=selection.key,
                value=fields["value"],
                source={v: k for k, v in SOURCE.items()}[fields["origin"]],
                by=fields.get("measured_by"),
            )
            for key in ("pieces", "evidence"):
                if fields.get(key):
                    fact[key] = fields[key]
            goal["profile"]["measurements"].append(fact)
    return goal


def snapshots(connection):
    from sqlalchemy import inspect, text

    """Explicit SQL snapshot, independent of changing runtime ORM attributes."""
    columns = {column["name"] for column in inspect(connection).get_columns("pipeline_draft")}
    if "goal" not in columns:
        return []
    rows = connection.execute(
        text("""
        SELECT d.id AS draft_id, s.id AS session_id, s.phase, s.at,
               s.goal AS session_goal, d.goal AS draft_goal,
               s.facts, d.graph, d.provenance, s.blueprint, s.reviewed, s.policy,
               d.decision_revision
        FROM pipeline_draft d LEFT JOIN pipeline_authoring_session s ON s.draft_id=d.id
        ORDER BY d.id
    """)
    ).mappings()
    result = []
    for row in rows:
        values = dict(row)
        for field in (
            "session_goal",
            "draft_goal",
            "facts",
            "graph",
            "provenance",
            "blueprint",
            "reviewed",
            "policy",
        ):
            value = values[field]
            if value is None:
                value = (
                    []
                    if field in ("facts", "reviewed")
                    else {}
                    if field in ("graph", "provenance", "blueprint")
                    else None
                )
            values[field] = json.dumps(value) if value is not None else None
        result.append(Snapshot(**values))
    return result
