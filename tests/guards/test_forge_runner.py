"""Mendel calls Wiener for forge tests and nothing else (forge MVP 4, spec §2).

The browser stays the courier for a laboratory's pipeline. A second importer of the runner is how
this one exception would become a way to run one, with no decision taken.
"""

import yaml
from support.paths import ROOT

ALLOWED = {"packages/mendel-api/src/mendel_api/services/forge_tests.py",
           "packages/mendel-api/src/mendel_api/services/wiener_runner.py"}


def test_only_the_forge_test_job_holds_the_runner():
    importers = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "packages/mendel-api/src").rglob("*.py")
        if "wiener_runner" in path.read_text() or "WienerRunner" in path.read_text()
    }
    assert importers, "the runner exists"
    assert importers <= ALLOWED


PUBLISHER_ALLOWED = {"packages/mendel-api/src/mendel_api/services/forge_publish.py",
                     "packages/mendel-api/src/mendel_api/services/github_publisher.py"}


def test_only_the_publish_service_holds_the_publisher():
    importers = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "packages/mendel-api/src").rglob("*.py")
        if "github_publisher" in path.read_text() or "GitHubPublisher" in path.read_text()
    }
    assert importers, "the publisher exists"
    assert importers <= PUBLISHER_ALLOWED


def test_only_the_worker_is_given_wieners_token():
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    holders = [name for name, service in services.items()
               if "MENDEL_WIENER_TOKEN" in (service.get("environment") or {})]
    assert holders == ["mendel-worker"]
