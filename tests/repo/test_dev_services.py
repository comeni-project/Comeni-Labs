"""Development helpers preserve Git work and fail visibly when startup cannot succeed."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest
from support.paths import ROOT


def _module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def _commit(root, filename, text):
    (root / filename).write_text(text)
    _git(root, "add", filename)
    _git(
        root,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        filename,
    )
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def registry(tmp_path):
    source = tmp_path / "registry"
    source.mkdir()
    _git(source, "init", "-q")
    _commit(source, "contract.yml", "first")
    module = _module("dev_services")
    target = tmp_path / ".run/registry"
    module.refresh_registry(source, target)
    return module, source, target


def test_registry_refresh_fast_forwards_and_then_is_idempotent(registry):
    module, source, target = registry
    wanted = _commit(source, "new.yml", "upstream")
    module.refresh_registry(source, target)
    assert _git(target, "rev-parse", "HEAD") == wanted
    module.refresh_registry(source, target)
    assert (target / "new.yml").read_text() == "upstream"


@pytest.mark.parametrize("state", ["dirty", "ahead", "divergent"])
def test_registry_refresh_preserves_local_work(registry, state):
    module, source, target = registry
    if state == "dirty":
        (target / "local.yml").write_text("uncommitted")
    else:
        _commit(target, "local.yml", "accepted local work")
    before = _git(target, "rev-parse", "HEAD")
    if state != "ahead":
        _commit(source, "upstream.yml", "upstream changed")
    module.refresh_registry(source, target)
    assert _git(target, "rev-parse", "HEAD") == before
    assert (target / "local.yml").exists()


def test_cloning_a_detached_submodule_creates_a_writable_branch(tmp_path):
    module = _module("dev_services")
    source = tmp_path / "registry"
    source.mkdir()
    _git(source, "init", "-q")
    commit = _commit(source, "contract.yml", "declared data")
    _git(source, "checkout", "-q", "--detach", commit)
    target = tmp_path / ".run/registry"
    module.refresh_registry(source, target)
    assert _git(target, "symbolic-ref", "--short", "HEAD")
    assert _git(source, "rev-parse", "HEAD") == commit


def test_preparation_keeps_environment_and_existing_data(registry, tmp_path):
    module, _, _ = registry
    (tmp_path / ".env").write_text("LOCAL_VALUE=preserve\n")
    data = tmp_path / ".run/wiener/artifacts/keep.txt"
    data.parent.mkdir(parents=True)
    data.write_text("stored artifact")
    module.prepare(tmp_path)
    assert (tmp_path / ".env").read_text() == "LOCAL_VALUE=preserve\n"
    assert data.read_text() == "stored artifact"
    assert (tmp_path / ".run/drafts").is_dir()


def test_compose_dotenv_quotes_interpolation_and_literals_are_not_make_code(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Compose CLI is unavailable")
    module = _module("command_env")
    trap = tmp_path / "must-not-exist"
    (tmp_path / ".env").write_text(
        'API_HOST_PORT="58000"\nBASE=hello\nINTERPOLATED="${BASE}-world"\n'
        "LITERAL='${NOT_EXPANDED} # value'\n"
        f"MAKE_CODE='$(shell touch {trap})'\n"
        "MULTILINE='first\nsecond'\n"
    )
    env = module.environment(tmp_path, {"PATH": os.environ["PATH"], "BASE": "override"})
    assert env["API_HOST_PORT"] == "58000"
    assert env["INTERPOLATED"] == "override-world"
    assert env["LITERAL"] == "${NOT_EXPANDED} # value"
    assert env["MULTILINE"] == "first\nsecond"
    assert env["MAKE_CODE"] == f"$(shell touch {trap})"
    assert not trap.exists()


def test_make_recipe_receives_values_without_executing_them(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Compose CLI is unavailable")
    (tmp_path / "tools").mkdir()
    shutil.copyfile(ROOT / "tools/command_env.py", tmp_path / "tools/command_env.py")
    (tmp_path / "tools/command_env.py").chmod(0o755)
    trap = tmp_path / "must-not-exist"
    (tmp_path / ".env").write_text(f"VALUE='$(shell touch {trap}) # literal'\n")
    (tmp_path / "Makefile").write_text(
        "SHELL := $(CURDIR)/tools/command_env.py\n"
        "test:\n\t@python3 -c 'import os,json; print(json.dumps(os.environ[\"VALUE\"]))'\n"
    )
    result = subprocess.run(
        ["make", "-s", "-C", str(tmp_path), "test"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == f"$(shell touch {trap}) # literal"
    assert not trap.exists()


@pytest.mark.parametrize("mode", ["early-exit", "timeout"])
def test_vite_failure_is_bounded_and_removes_its_pid(tmp_path, monkeypatch, mode):
    module = _module("dev_services")
    (tmp_path / "frontend").mkdir()
    monkeypatch.setattr(module, "_ready", lambda _: False)
    code = "raise SystemExit(7)" if mode == "early-exit" else "import time; time.sleep(20)"
    with pytest.raises(RuntimeError, match="Vite (exited|startup timed out)"):
        module.start_vite(tmp_path, command=[sys.executable, "-c", code], timeout=0.3)
    assert not (tmp_path / ".run/vite.pid").exists()
    assert (tmp_path / ".run/vite.log").exists()


def test_an_existing_ready_vite_is_reused(tmp_path, monkeypatch):
    module = _module("dev_services")
    runtime = tmp_path / ".run"
    runtime.mkdir()
    (runtime / "vite.pid").write_text(str(os.getpid()))
    monkeypatch.setattr(module, "_ready", lambda _: True)
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *a, **k: pytest.fail("started another Vite")
    )
    module.start_vite(tmp_path)


def test_test_database_timeout_prints_diagnostics(monkeypatch):
    module = _module("dev_services")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(module.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="did not become ready"):
        module.wait_postgres("synthetic-unready-db", timeout=0.01)
    assert any(command[:2] == ["docker", "logs"] for command in calls)


def test_test_database_returns_after_delayed_readiness(monkeypatch):
    module = _module("dev_services")
    results = iter([1, 1, 0])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, next(results))

    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    module.wait_postgres("synthetic-delayed-db", timeout=1)
    assert len(calls) == 3
    assert all(command[:2] == ["docker", "exec"] for command in calls)


def test_parallel_development_targets_prepare_once_before_startup(tmp_path):
    (tmp_path / "tools").mkdir()
    shutil.copyfile(ROOT / "tools/command_env.py", tmp_path / "tools/command_env.py")
    (tmp_path / "tools/command_env.py").chmod(0o755)
    (tmp_path / "Makefile").write_text(
        (ROOT / "Makefile").read_text()
        + "\nprepare:\n\t@echo prepared >> order\n"
        + "dev:\n\t@test -s order\n\t@echo started >> order\n"
        + "names-free:\n\t@true\nwiki-tools:\n\t@true\ndatabase-ready:\n\t@true\n"
    )
    run = subprocess.run(
        ["make", "-s", "-j8", "NODEDEPS=", "dev", "dev-refresh"], cwd=tmp_path,
        text=True, capture_output=True, check=False,
    )
    assert run.returncode == 0, run.stderr
    assert (tmp_path / "order").read_text().splitlines() == ["prepared", "started"]


def test_vite_replaces_a_malformed_pid_only_after_successful_startup(tmp_path, monkeypatch):
    module = _module("dev_services")
    (tmp_path / "frontend").mkdir()
    runtime = tmp_path / ".run"
    runtime.mkdir()
    pidfile = runtime / "vite.pid"
    pidfile.write_text("stale invalid pid")
    readiness = iter([False, True])
    monkeypatch.setattr(module, "_ready", lambda _: next(readiness))
    module.start_vite(
        tmp_path, command=[sys.executable, "-c", "import time; time.sleep(20)"], timeout=1
    )
    pid = int(pidfile.read_text())
    try:
        assert pid > 0 and pid != os.getpid()
        assert module._alive(pid)
    finally:
        os.kill(pid, 15)
        os.waitpid(pid, 0)


def test_make_preserves_configured_runtime_identity(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Compose CLI is unavailable")
    (tmp_path / "tools").mkdir()
    shutil.copyfile(ROOT / "tools/command_env.py", tmp_path / "tools/command_env.py")
    (tmp_path / "tools/command_env.py").chmod(0o755)
    (tmp_path / ".env").write_text('DOCKER_UID="12001"\nDOCKER_GID="12002"\n')
    (tmp_path / "Makefile").write_text(
        (ROOT / "Makefile").read_text()
        + '\nidentity:\n\t@echo "$$DOCKER_UID:$$DOCKER_GID"\n'
    )
    env = {key: value for key, value in os.environ.items()
           if key not in {"DOCKER_UID", "DOCKER_GID"}}
    run = subprocess.run(
        ["make", "-s", "identity"], cwd=tmp_path, env=env,
        text=True, capture_output=True, check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "12001:12002"
