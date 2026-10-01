"""The one place an `Installation` is built (spec §8).

**Built per request, never held**: the store is read on every use, and `.env` is read at call
time for the reason `settings.model_access` gives. A test overrides this dependency rather than
monkeypatching the store.
"""

import os

from comeni_core.settings import CATALOGUE, Installation

from mendel_api.services.settings_codec import Tolerant, codec_from_env
from mendel_api.services.settings_store import PostgresStore


def installation() -> Installation:
    codec = codec_from_env(os.environ)
    return Installation(
        CATALOGUE, PostgresStore(), os.environ, codec=Tolerant(codec) if codec else None
    )
