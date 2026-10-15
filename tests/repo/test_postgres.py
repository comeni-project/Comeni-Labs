"""The shared server keeps database identity, credentials and migration ownership separate."""

import json
from urllib.parse import urlsplit

import pytest
from support.compose import configuration


def test_application_connections_share_only_the_server(tmp_path):
    result = configuration(tmp_path)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    servers = [
        name
        for name, service in services.items()
        if service.get("image", "").startswith("postgres:")
    ]
    assert servers == ["postgres"]
    clients = {}
    for name, service in services.items():
        for key, value in service.get("environment", {}).items():
            if key.endswith("_DATABASE_URL"):
                url = urlsplit(value)
                owner = key.removesuffix("_DATABASE_URL").lower()
                assert url.hostname == "postgres" and url.port == 5432
                assert url.username == owner and url.path == f"/{owner}"
                assert url.password == f"synthetic-{owner}"
                assert service["depends_on"]["postgres"]["condition"] == "service_healthy"
                clients[name] = owner
    assert set(clients.values()) == {"mendel", "wiener"}
    assert len(clients) == 6
    assert services["postgres"]["environment"]["POSTGRES_USER"] == "comeni_admin"
    data = next(
        v for v in services["postgres"]["volumes"] if v["target"] == "/var/lib/postgresql/data"
    )
    assert data["source"] == "comeni-pg"


@pytest.mark.parametrize(
    "setting", ["POSTGRES_ADMIN_PASSWORD", "MENDEL_DB_PASSWORD", "WIENER_DB_PASSWORD"]
)
def test_production_requires_each_database_credential(tmp_path, setting):
    result = configuration(
        tmp_path, production=True, token="synthetic-token", extra_env={setting: ""}
    )
    assert result.returncode != 0
    assert setting in result.stderr
