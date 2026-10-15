"""Local state stays outside commits/builds; deployment ports and authentication are explicit."""

import json
import shutil
import subprocess

import pytest
from support.compose import configuration as _compose
from support.paths import ROOT

PRIVATE_PATHS = [
    ".env",
    ".env.production",
    ".env.test",
    ".env.development",
    "packages/demo/.env",
    "frontend/.env.local",
    "var/wiener/artifacts/pipeline.yml",
    "var/wiener/artifacts/params.json",
    "var/wiener/work/task.txt",
    "profile-build/main.nf",
    "packages/demo/__pycache__/module.pyc",
    "packages/demo/stray.pyc",
    "packages/demo/.pytest_cache/state",
    ".worktrees/other/secret.txt",
    ".claude/worktrees/other/secret.txt",
]
AUTHORED_PATHS = [
    ".env.example",
    "frontend/.env.example",
    "examples/rnaseq-goal.yml",
    "packages/demo/pyproject.toml",
    "packages/demo/src/demo/build/__init__.py",
    "frontend/src/app.tsx",
    "frontend/package-lock.json",
    "ops/nginx/default.conf",
    "registry/tools/demo/contract.yml",
    "registry/tools/demo/module/main.nf",
    "docs/how-to/index.md",
    "docs/tools/index.md",
    "tools/README.md",
]


def _files(root, names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture\n")


def test_git_excludes_local_state_and_preserves_authored_inputs(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    names = PRIVATE_PATHS + AUTHORED_PATHS
    _files(tmp_path, names)
    result = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", "--no-index", "--stdin"],
        input="\n".join(names),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    ignored = set(result.stdout.splitlines())
    assert set(PRIVATE_PATHS) <= ignored
    assert not (set(AUTHORED_PATHS) & ignored)


def test_development_publications_are_loopback_only(tmp_path):
    result = _compose(tmp_path)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    ports = [p for service in services.values() for p in service.get("ports", [])]
    assert ports
    assert all(p["host_ip"] == "127.0.0.1" for p in ports)


def test_production_refuses_an_empty_execution_token(tmp_path):
    result = _compose(tmp_path, production=True)
    assert result.returncode != 0
    assert "WIENER_API_TOKEN" in result.stderr


def test_production_passes_the_required_token_to_wiener(tmp_path):
    result = _compose(tmp_path, production=True, token="synthetic-test-token")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    assert services["wiener-api"]["environment"]["WIENER_API_TOKEN"] == "synthetic-test-token"


@pytest.mark.slow
def test_docker_context_excludes_local_state_and_keeps_build_inputs(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    context = tmp_path / "context"
    context.mkdir()
    shutil.copyfile(ROOT / ".dockerignore", context / ".dockerignore")
    _files(context, PRIVATE_PATHS + AUTHORED_PATHS)
    (context / "Dockerfile").write_text("FROM scratch\nCOPY . /context/\n")
    output = tmp_path / "output"
    result = subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--network=none",
            "--output",
            f"type=local,dest={output}",
            str(context),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    copied = {
        p.relative_to(output / "context").as_posix()
        for p in (output / "context").rglob("*")
        if p.is_file()
    }
    assert not (set(PRIVATE_PATHS) & copied)
    assert set(AUTHORED_PATHS) <= copied


def test_effective_production_has_no_source_mounts_and_only_web_is_published(tmp_path):
    result = _compose(tmp_path, production=True, token="synthetic-test-token")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in ["api", "mendel-worker", "ai-worker"]:
        mounts = {v["target"]: v for v in services[name]["volumes"]}
        assert "/app/packages" not in mounts, name
        assert {"/app/registry", "/app/workspace", "/app/drafts"} <= set(mounts), name
    published = {name for name, service in services.items() if service.get("ports")}
    assert published == {"web"}


def test_python_image_cache_ownership_matches_configured_runtime_identity(tmp_path):
    result = _compose(
        tmp_path,
        production=True,
        token="synthetic-test-token",
        extra_env={"DOCKER_UID": "12001", "DOCKER_GID": "12002"},
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in [
        "api",
        "mendel-worker",
        "ai-worker",
        "wiener-api",
        "wiener-worker",
        "wiener-ingest",
    ]:
        assert services[name]["user"] == "12001:12002"
        assert services[name]["build"]["args"]["RUNTIME_UID"] == "12001"
        assert services[name]["build"]["args"]["RUNTIME_GID"] == "12002"


# Each process that reads a database the API migrates, with the API that migrates it (issue 330).
MIGRATED_BY = {
    "mendel-worker": "api",
    "ai-worker": "api",
    "wiener-worker": "wiener-api",
    "wiener-ingest": "wiener-api",
}


@pytest.mark.parametrize("production", [False, True])
def test_a_worker_starts_after_the_api_that_migrates_its_database(tmp_path, production):
    """Issue 330: on a fresh database the AI worker's startup sweep queried `forge_adaptation`
    before the API had created it. Postgres being healthy is not the schema being there."""
    result = _compose(tmp_path, production=production, token="synthetic-test-token")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for api in set(MIGRATED_BY.values()):
        assert services[api].get("healthcheck"), f"{api} has no healthcheck to wait on"
    for worker, api in MIGRATED_BY.items():
        if worker not in services:
            continue
        wait = services[worker].get("depends_on", {}).get(api, {})
        assert wait.get("condition") == "service_healthy", f"{worker} does not wait for {api}"
