"""Read effective Compose models with synthetic configuration, without starting services."""

import os
import shutil
import subprocess

import pytest

from support.paths import ROOT


def configuration(tmp_path, production=False, token="", extra_env=None):
    """Return CLI output; exclude the checkout's real dotenv file and inherited credentials."""
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is unavailable")
    dotenv = tmp_path / ".env"
    dotenv.write_text("")
    env = {
        "PATH": os.environ["PATH"],
        "PWD": str(ROOT),
        "COMPOSE_PROJECT_NAME": "comeni-boundary-test",
        "WIENER_API_TOKEN": token,
        "POSTGRES_ADMIN_PASSWORD": "synthetic-admin",
        "MENDEL_DB_PASSWORD": "synthetic-mendel",
        "WIENER_DB_PASSWORD": "synthetic-wiener",
    }
    env.update(extra_env or {})
    cmd = ["docker", "compose", "--env-file", str(dotenv), "-f", str(ROOT / "docker-compose.yml")]
    if production:
        cmd += ["-f", str(ROOT / "docker-compose.prod.yml")]
    return subprocess.run(
        cmd + ["--profile", "*", "config", "--format", "json"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
