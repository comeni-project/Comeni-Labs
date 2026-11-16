"""Run → Console's terminal service (#511, #525): what the assistant may run itself, Nextflow's
output as text, the Commands list, and the token on every route."""

import pytest
from fastapi.testclient import TestClient
from wiener_api import terminal
from wiener_api.services import launcher
from wiener_api.settings import settings


@pytest.fixture
def term(session, tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    return TestClient(terminal.create_app())


@pytest.mark.parametrize(
    "command",
    [
        "cat .command.err",
        "tail -n 40 .nextflow.log",
        "ls work",
        "nextflow log wiener-x -f process,status",
        "du -sh work",
    ],
)
def test_a_command_that_only_reads_is_run(command):
    assert terminal.read_only(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf work",
        "nextflow run . -resume",
        "cat a | sh",
        "ls; rm x",
        "cat $(echo x)",
        "tail x > y",
        "bash .command.run",
        "cat `id`",
        "",
    ],
)
def test_anything_else_is_only_suggested(command):
    assert terminal.read_only(command) is None


def test_the_console_as_text_drops_escape_codes_and_redraws(tmp_path):
    log = tmp_path / "console.log"
    log.write_bytes(
        b"\x1b[2K\rexecutor >  local (2)\r\n\x1b[32m[ab/cd12] STAR_ALIGN [ 50%]\x1b[0m\n"
        b"\x1b[1A\x1b[2K[ab/cd12] STAR_ALIGN [ 50%]\nERROR ~ boom\n"
    )
    text = terminal.plain_tail(log)
    assert "\x1b" not in text and "\r" not in text
    assert text.splitlines() == [
        "executor >  local (2)",
        "[ab/cd12] STAR_ALIGN [ 50%]",
        "ERROR ~ boom",
    ]


def test_a_tools_command_shows_only_when_its_step_ran():
    general = terminal.commands_for(set())
    assert general and not any(c.get("tool") for c in general)
    with_star = terminal.commands_for({"STAR_ALIGN"})
    assert any(c.get("tool") == "STAR_ALIGN" for c in with_star)
    assert not any(c.get("tool") == "QUAST" for c in with_star)


def test_exec_runs_a_read_only_command_in_the_run_folder_and_refuses_the_rest(term, a_run):
    folder = launcher.work_dir(a_run.id)
    folder.mkdir(parents=True)
    (folder / "params.json").write_text('{"reads": "x"}')
    ran = term.post(f"/api/runs/{a_run.id}/terminal/exec", json={"command": "cat params.json"})
    assert (
        ran.status_code == 200
        and ran.json()["output"] == '{"reads": "x"}'
        and ran.json()["exit"] == 0
    )
    refused = term.post(f"/api/runs/{a_run.id}/terminal/exec", json={"command": "rm params.json"})
    assert refused.status_code == 422
    assert (folder / "params.json").exists()


def test_a_folder_outside_the_run_is_not_taken(term, a_run):
    folder = launcher.work_dir(a_run.id)
    folder.mkdir(parents=True)
    ran = term.post(f"/api/runs/{a_run.id}/terminal/exec", json={"command": "ls", "cwd": "../.."})
    assert ran.status_code == 200
    # `..` climbs out, so the command ran in the run's own folder instead.
    assert ran.json()["output"] == ""


def test_every_route_wants_the_token(term, a_run, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "secret")
    launcher.work_dir(a_run.id).mkdir(parents=True)
    assert term.get(f"/api/runs/{a_run.id}/terminal/console").status_code == 401
    assert (
        term.post(f"/api/runs/{a_run.id}/terminal/exec", json={"command": "ls"}).status_code == 401
    )
    ok = term.get(
        f"/api/runs/{a_run.id}/terminal/console", headers={"Authorization": "Bearer secret"}
    )
    assert ok.status_code == 200
