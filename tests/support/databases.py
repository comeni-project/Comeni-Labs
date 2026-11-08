"""Select isolated database URLs, and drop deploy secrets, before importing application settings."""

from collections.abc import MutableMapping

MENDEL_TEST_URL = "postgresql+psycopg://mendel:mendel@127.0.0.1:5442/mendel"
WIENER_TEST_URL = "postgresql+psycopg://mendel:mendel@127.0.0.1:5442/wiener"
# What a developer keeps in .env that changes what a test sees: deploy secrets, and the model
# `model_access()` reads at call time. A test that needs one sets it with monkeypatch.
DEPLOY_SECRETS = ("WIENER_API_TOKEN", "COMENI_FORGE_GITHUB_TOKEN", "COMENI_AI_MODEL",
                  "COMENI_AI_BASE_URL", "COMENI_AI_API_KEY")


def configure(environ: MutableMapping[str, str]) -> None:
    """Use explicit test URLs or local test defaults, never inherited application URLs or
    deploy secrets."""
    for name in DEPLOY_SECRETS:
        environ.pop(name, None)
    environ["MENDEL_DATABASE_URL"] = environ.get("MENDEL_TEST_DATABASE_URL", MENDEL_TEST_URL)
    environ["WIENER_TEST_DATABASE_URL"] = environ.get("WIENER_TEST_DATABASE_URL", WIENER_TEST_URL)
    environ["WIENER_DATABASE_URL"] = environ["WIENER_TEST_DATABASE_URL"]
