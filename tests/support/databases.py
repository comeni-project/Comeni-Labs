"""Select isolated database URLs, and drop deploy secrets, before importing application settings."""

from collections.abc import MutableMapping

MENDEL_TEST_URL = "postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel"
WIENER_TEST_URL = "postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener"
# Deploy secrets a developer keeps in .env; a test that needs one sets it with monkeypatch.
DEPLOY_SECRETS = ("WIENER_API_TOKEN", "COMENI_FORGE_GITHUB_TOKEN")


def configure(environ: MutableMapping[str, str]) -> None:
    """Use explicit test URLs or local test defaults, never inherited application URLs or
    deploy secrets."""
    for name in DEPLOY_SECRETS:
        environ.pop(name, None)
    environ["MENDEL_DATABASE_URL"] = environ.get("MENDEL_TEST_DATABASE_URL", MENDEL_TEST_URL)
    environ["WIENER_TEST_DATABASE_URL"] = environ.get("WIENER_TEST_DATABASE_URL", WIENER_TEST_URL)
    environ["WIENER_DATABASE_URL"] = environ["WIENER_TEST_DATABASE_URL"]
