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
def test_a_command_that_only_reads_is_run(command, tmp_path):
    assert terminal.read_only(command, tmp_path) is not None


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
def test_anything_else_is_only_suggested(command, tmp_path):
    assert terminal.read_only(command, tmp_path) is None


@pytest.mark.parametrize(
    "command",
    ["cat /proc/self/environ", "cat ../../secrets", "head /etc/passwd", "grep -r x /data",
     "cat --file=/etc/passwd", "zcat work/ab/staged.fq.gz"],
)
def test_a_read_only_command_reads_only_inside_the_run(command, tmp_path):
    """Checkpoint D, C1: the program was checked and its paths were not, so the model could read
    /proc/self/environ (the Wiener token) or a staged sample (a symlink into the data roots) and
    the page sent it back. Every path a command names must resolve inside the run's folder."""
    outside = tmp_path / "data"
    outside.mkdir()
    (outside / "sample.fq.gz").write_bytes(b"@r\nACGT\n")
    run = tmp_path / "run"
    (run / "work" / "ab").mkdir(parents=True)
    (run / "work" / "ab" / "staged.fq.gz").symlink_to(outside / "sample.fq.gz")
    assert terminal.read_only(command, run) is None


def test_a_path_inside_the_run_is_read(tmp_path):
    (tmp_path / "work").mkdir()
    assert terminal.read_only("tail -n 40 work/.command.err", tmp_path) is not None
    assert terminal.read_only("nextflow log wiener-x -f process,status", tmp_path) is not None


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


def test_every_websocket_and_the_commands_want_the_token(term, a_run, monkeypatch):
    """Checkpoint D, I5: the token test covered two routes of five."""
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setattr(settings, "api_token", "secret")
    launcher.work_dir(a_run.id).mkdir(parents=True)
    assert term.get(f"/api/runs/{a_run.id}/terminal/commands").status_code == 401
    for kind in ("console", "shell"):
        with (pytest.raises(WebSocketDisconnect) as closed,
              term.websocket_connect(f"/api/runs/{a_run.id}/terminal/{kind}") as socket):
            socket.receive_bytes()
        assert closed.value.code == 4401


def test_a_websocket_from_another_page_is_refused(term, a_run):
    """Checkpoint D, I3: in development the proxy adds the token itself, so any page that knew a
    run id could open a shell. The upgrade's Origin must be this page's own host."""
    from starlette.websockets import WebSocketDisconnect

    launcher.work_dir(a_run.id).mkdir(parents=True)
    for origin in ("http://evil.example", "null"):
        with (pytest.raises(WebSocketDisconnect) as closed,
              term.websocket_connect(f"/api/runs/{a_run.id}/terminal/shell",
                                     headers={"origin": origin, "host": "localhost"}) as socket):
            socket.receive_bytes()
        assert closed.value.code == 4403


def test_resume_is_the_command_wiener_ran_with_resume(term, a_run):
    """Checkpoint D, I4: Resume dropped -profile and --outdir, so tasks ran without containers
    and nothing was published."""
    import shlex

    folder = launcher.work_dir(a_run.id)
    folder.mkdir(parents=True)
    (folder / "params.json").write_text("{}")
    resume = shlex.split(terminal.resume_command(a_run.id))
    assert resume == [*launcher.command(a_run, str(folder), has_params=True), "-resume"]
    listed = term.get(f"/api/runs/{a_run.id}/terminal/commands").json()["commands"]
    assert next(c for c in listed if c["name"] == "Resume the run")["command"] == shlex.join(resume)



def test_the_console_tail_reads_only_the_end_of_the_log(tmp_path, monkeypatch):
    """#567. The console's tail read the whole `console.log` to keep its last 512 KB; a long
    run's log is many megabytes, read on every open of Run → Console. It seeks to the end."""
    from pathlib import Path

    from wiener_api import terminal

    log = tmp_path / "console.log"
    log.write_bytes(b"early line\n" * 300_000 + b"the last line\n")

    def whole(self, *args, **kwargs):
        raise AssertionError("the whole log was read")

    monkeypatch.setattr(Path, "read_bytes", whole)
    tail = terminal.plain_tail(log, lines=3)
    assert tail.splitlines()[-1] == "the last line"
    assert "early line" in tail
