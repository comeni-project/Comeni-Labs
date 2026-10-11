"""Read-only inventory over the versioned legacy snapshot; no transcript is reported."""

import json
from dataclasses import asdict

from sqlalchemy import inspect, text

from mendel_api.migration_data.decisions_v1 import Snapshot, convert


def snapshots(connection):
    """Explicit SQL snapshot, independent of changing runtime ORM attributes."""
    columns = {column["name"] for column in inspect(connection).get_columns("pipeline_draft")}
    if "goal" not in columns:
        return []
    rows = connection.execute(text("""
        SELECT d.id AS draft_id, s.id AS session_id, s.phase, s.at,
               s.goal AS session_goal, d.goal AS draft_goal,
               s.facts, d.graph, d.provenance, s.blueprint, s.reviewed, s.policy,
               d.decision_revision
        FROM pipeline_draft d LEFT JOIN pipeline_authoring_session s ON s.draft_id=d.id
        ORDER BY d.id
    """)).mappings()
    result = []
    for row in rows:
        values = dict(row)
        for field in ("session_goal", "draft_goal", "facts", "graph", "provenance",
                      "blueprint", "reviewed", "policy"):
            value = values[field]
            if value is None:
                value = [] if field in ("facts", "reviewed") else {} if field in (
                    "graph", "provenance", "blueprint") else None
            values[field] = json.dumps(value) if value is not None else None
        result.append(Snapshot(**values))
    return result


def inventory(connection):
    return [dict(draft_id=snapshot.draft_id, session_id=snapshot.session_id,
                 disposition=converted.disposition, retired=converted.retired,
                 reason=converted.reason,
                 selections=len(converted.selections), observations=len(converted.observations))
            for snapshot in snapshots(connection) for converted in (convert(snapshot),)]


def archive_payload(snapshot):
    return asdict(snapshot)
