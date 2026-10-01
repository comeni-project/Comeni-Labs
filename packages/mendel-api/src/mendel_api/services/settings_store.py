"""The settings store: one row per setting in `installation_setting` (spec §8).

Implements `comeni_core.settings.SettingsStore`. **An upsert, not read-then-write**, so two
saves of the same key cannot both decide the row is missing; two saves of different keys never
touch the same row at all.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from mendel_api.db import session_scope
from mendel_api.models import InstallationSetting


class PostgresStore:
    def values(self) -> dict[str, object]:
        with session_scope() as session:
            rows = session.execute(select(InstallationSetting.key, InstallationSetting.value))
            return {key: value for key, value in rows}

    def put(self, key: str, value: object, by: str) -> None:
        now = datetime.now(UTC)
        statement = insert(InstallationSetting).values(
            key=key, value=value, updated_at=now, updated_by=by
        )
        statement = statement.on_conflict_do_update(
            index_elements=[InstallationSetting.key],
            set_={"value": value, "updated_at": now, "updated_by": by},
        )
        with session_scope() as session:
            session.execute(statement)

    def who(self, key: str) -> str | None:
        with session_scope() as session:
            return session.scalar(
                select(InstallationSetting.updated_by).where(InstallationSetting.key == key)
            )
