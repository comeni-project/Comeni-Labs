"""The one place an `Installation` is built (spec §8).

**Built per request, never held**: the store is read on every use, and `.env` is read at call
time for the reason `settings.model_access` gives. A test overrides this dependency rather than
monkeypatching the store.
"""

import os

from comeni_core.settings import CATALOGUE, Installation

from mendel_api.services.settings_codec import codec_from_env, key_problem
from mendel_api.services.settings_store import PostgresStore


def _store():
    """The store `installation()` reads. A seam: the suite swaps in an empty one (`conftest.py`),
    so tests that only set the environment keep meaning what they meant before settings."""
    return PostgresStore()


def installation() -> Installation:
    from mendel_api.services.models import where_purposes

    # **Strict, not tolerant**: a secret sealed under a rotated key raises when opened, so
    # the code that uses it learns it cannot be read; the menu shows it as not set, with why.
    inst = Installation(
        CATALOGUE,
        _store(),
        os.environ,
        codec=codec_from_env(os.environ),
        secrets_need=key_problem(os.environ),
    )
    inst.reporters = {"privacy.where": lambda: where_purposes(inst)}
    return inst
