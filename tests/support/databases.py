"""Select isolated database URLs before importing application settings during collection."""

from collections.abc import MutableMapping

MENDEL_TEST_URL = "postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel"
WIENER_TEST_URL = "postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener"


def configure(environ: MutableMapping[str, str]) -> None:
    """Use explicit test URLs or local test defaults, never inherited application URLs."""
    environ["MENDEL_DATABASE_URL"] = environ.get("MENDEL_TEST_DATABASE_URL", MENDEL_TEST_URL)
    environ["WIENER_TEST_DATABASE_URL"] = environ.get("WIENER_TEST_DATABASE_URL", WIENER_TEST_URL)
    environ["WIENER_DATABASE_URL"] = environ["WIENER_TEST_DATABASE_URL"]
