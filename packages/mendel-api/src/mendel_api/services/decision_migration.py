"""Read-only inventory over the versioned legacy snapshot; no transcript is reported."""

from dataclasses import asdict

from sqlalchemy import inspect, text

from mendel_api.migration_data.decisions_v1 import Conversion, convert, snapshots


def inventory(connection):
    # The additive ownership marker was written explicitly by the new application.
    # Its empty, zero-revision conversations already use the new authority too.
    if "goal" not in {c["name"] for c in inspect(connection).get_columns("pipeline_draft")}:
        return [
            dict(
                draft_id=row["draft_id"],
                session_id=row["snapshot"].get("session_id"),
                disposition=row["disposition"],
                reason=row["reason"],
                retired=row["disposition"] in ("ambiguous_manual", "obsolete_protocol"),
            )
            for row in connection.execute(
                text(
                    "SELECT draft_id, disposition, reason, snapshot "
                    "FROM pipeline_decision_migration "
                    "ORDER BY draft_id"
                )
            ).mappings()
        ]
    authored = set(
        connection.execute(
            text("SELECT id FROM pipeline_draft WHERE ownership='authored'")
        ).scalars()
    )
    return [
        dict(
            draft_id=snapshot.draft_id,
            session_id=snapshot.session_id,
            disposition=converted.disposition,
            retired=converted.retired,
            reason=converted.reason,
            selections=len(converted.selections),
            observations=len(converted.observations),
        )
        for snapshot in snapshots(connection)
        for converted in (
            Conversion("already_rows") if snapshot.draft_id in authored else convert(snapshot),
        )
    ]


def archive_payload(snapshot):
    return asdict(snapshot)
