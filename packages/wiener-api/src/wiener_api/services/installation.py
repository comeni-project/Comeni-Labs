"""The one place Wiener builds its `Installation` (Part H). Read per use, never held, so a
change made on the menu reaches the next sweep; `.env` is read at call time for the same
reason."""

import os

from comeni_core.settings import CATALOGUE, Installation

from wiener_api import db, repository
from wiener_api.settings import settings


class Store:
    """Wiener's own stored settings. Running stays reported: `Installation.put` refuses a
    read-only setting before it reaches here."""

    def values(self):
        with db.session_scope() as session:
            return repository.setting_values(session, settings.lab_id)

    def put(self, key, value, by):
        with db.session_scope() as session:
            repository.put_setting(session, settings.lab_id, key, value, by)


def _reporters() -> dict:
    return {
        "running.runtime": lambda: settings.container_profile,
        "running.lost_after": lambda: f"{settings.lost_after_ms // 60000} minutes",
        "running.token": lambda: (
            "a token is required" if settings.api_token
            else "open: anyone who can reach this API can submit runs"
        ),
        "running.telemetry": lambda: "on" if settings.otlp_endpoint else "off",
    }


def installation() -> Installation:
    return Installation(CATALOGUE, Store(), os.environ, server="wiener",
                        reporters=_reporters())
