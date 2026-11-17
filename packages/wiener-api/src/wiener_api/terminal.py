"""Run → Console's terminals (#511): Nextflow's own output, and shells in a run's folder.

**A shell here is host-level control** (#525): it runs with the worker's mounts, including the
host's Docker socket. That is the operator's decision for a local tool; it is behind the same
Wiener token as every other route, checked on the WebSocket's upgrade (the proxy presents it,
as it does for the API), and a hosted install revisits it before use.

Served by its own service, `wiener-term`, from the Wiener image with the worker's mounts, so a
shell sees what a run saw: `nextflow`, `docker`, the data roots read-only, the run's `work/`.

- `GET  /api/runs/{id}/terminal/console`: the last lines Nextflow printed, as plain text (for the
  assistant, which the browser carries it to).
- `WS   /api/runs/{id}/terminal/console`: everything Nextflow printed, then what it prints next.
- `WS   /api/runs/{id}/terminal/shell?cwd=`: a bash in the run's folder (or a folder under it).
- `POST /api/runs/{id}/terminal/exec`: one read-only command (`READ_ONLY`), for the assistant.
- `GET  /api/runs/{id}/terminal/commands`: the Commands list, for this run's steps.
"""

import asyncio
import fcntl
import json
import logging
import os
import pty
import re
import secrets
import shlex
import signal
import struct
import subprocess
import tempfile
import termios
import time
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from wiener_api import db, repository
from wiener_api.services import launcher
from wiener_api.settings import settings

READ_ONLY = frozenset({"cat", "head", "tail", "grep", "zgrep", "zcat", "ls", "wc", "du", "df",
                       "free", "nextflow"})
"""What the assistant may run itself: commands that read. Anything else it suggests, for a person
to run. `nextflow` only as `nextflow log`."""

_ANSI = re.compile(rb"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\r")
_COMMANDS = Path(__file__).with_name("commands.yml")


log = logging.getLogger(__name__)
_OUTPUT_CAP = 2_000_000
"""Bytes a read-only command may write before it is stopped: a `zcat` of a large file must not
fill the service's memory or disk within its 15 s."""


def _same_page(headers) -> bool:
    """A browser's upgrade comes from this page's own host: in development the proxy adds the
    token itself, so another page that knew a run id could otherwise open a shell (Checkpoint D).
    A sandboxed page says `null` and is refused; a client that sends no Origin is not a browser."""
    origin = headers.get("origin")
    if origin is None:
        return True
    host = headers.get("host", "").rsplit(":", 1)[0].strip("[]")
    return origin != "null" and urlsplit(origin).hostname == host


def _allowed(headers) -> bool:
    if not settings.api_token:
        return True
    offered = headers.get("authorization", "").removeprefix("Bearer ").strip()
    return bool(offered) and secrets.compare_digest(offered, settings.api_token)


def _run_dir(run_id: str) -> Path | None:
    with db.session_scope() as session:
        if repository.run(session, settings.lab_id, run_id) is None:
            return None
    root = launcher.work_dir(run_id).resolve()
    return root if root.is_dir() else None


def _under(root: Path, sub: str) -> Path:
    """`sub` under the run's folder, or the folder itself: a path that climbs out is not taken."""
    target = (root / sub).resolve() if sub else root
    return target if target.is_relative_to(root) and target.is_dir() else root


def plain_tail(path: Path, lines: int = 200) -> str:
    """The last `lines` of a terminal log as text: escape codes and carriage returns removed, and
    each redrawn progress line kept once."""
    if not path.exists():
        return ""
    data = path.read_bytes()[-512_000:]
    text = _ANSI.sub(b"", data).decode(errors="replace")
    kept: list[str] = []
    for line in text.splitlines():
        if line.strip() and (not kept or kept[-1] != line):
            kept.append(line)
    return "\n".join(kept[-lines:])


class Exec(BaseModel):
    command: str
    cwd: str = ""


class Ran(BaseModel):
    command: str
    output: str
    exit: int


def read_only(command: str, root: Path, cwd: Path | None = None) -> list[str] | None:
    """The command as argv when it only reads inside the run, else `None`: one command, no pipes,
    redirection or substitution, from `READ_ONLY`, `nextflow` only as `nextflow log`, and every
    path it names inside the run's folder once links are followed (Checkpoint D: `cat
    /proc/self/environ`, or a staged sample linked into the data roots, was otherwise read and its
    output sent to the model)."""
    if re.search(r"[|;&<>`$\n\\]", command):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv or argv[0] not in READ_ONLY:
        return None
    if argv[0] == "nextflow" and argv[1:2] != ["log"]:
        return None
    root = root.resolve()
    base = (cwd or root).resolve()
    for arg in argv[1:]:
        value = arg.split("=", 1)[1] if arg.startswith("-") and "=" in arg else (
            None if arg.startswith("-") else arg)
        if value and not (base / value).resolve().is_relative_to(root):
            return None
    return argv


def resume_command(run_id: str) -> str:
    """The command Wiener ran for this run, with `-resume`: the profile, config, work folder and
    `--outdir` it ran with (Checkpoint D: a hand-written one dropped containers and publishing)."""
    folder = launcher.work_dir(run_id)
    with db.session_scope() as session:
        run = repository.run(session, settings.lab_id, run_id)
        if run is None:
            raise KeyError(run_id)
        argv = launcher.command(run, str(folder), has_params=(folder / "params.json").exists())
    return shlex.join([*argv, "-resume"])


def _end(pid: int) -> None:
    """Hang up a shell and reap it, so a closed tab leaves no zombie."""
    try:
        os.kill(pid, signal.SIGHUP)
        for _ in range(20):
            if os.waitpid(pid, os.WNOHANG)[0]:
                return
            time.sleep(0.05)
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except OSError:
        pass


def commands_for(processes: set[str]) -> list[dict]:
    """The Commands list: every general command, and a tool's own only when its step is in the
    run (by Nextflow process name)."""
    listed = yaml.safe_load(_COMMANDS.read_text())["commands"]
    return [c for c in listed if not c.get("tool") or c["tool"] in processes]


def create_app() -> FastAPI:
    app = FastAPI(title="wiener-term", docs_url=None, redoc_url=None)
    if not settings.api_token:
        log.warning("WIENER_API_TOKEN is not set: wiener-term's shells are open to anyone who can "
                    "reach it")

    @app.get("/api/runs/{run_id}/terminal/console")
    def console_text(run_id: str, request: Request, lines: int = 200) -> dict:
        if not _allowed(request.headers):
            raise HTTPException(status_code=401)
        root = _run_dir(run_id)
        if root is None:
            raise HTTPException(status_code=404)
        return {"text": plain_tail(root / launcher.CONSOLE, max(1, min(lines, 2000)))}

    @app.get("/api/runs/{run_id}/terminal/commands")
    def commands(run_id: str, request: Request) -> dict:
        if not _allowed(request.headers):
            raise HTTPException(status_code=401)
        if _run_dir(run_id) is None:
            raise HTTPException(status_code=404)
        with db.session_scope() as session:
            processes = {t.process for t in repository.tasks(session, settings.lab_id, run_id)}
        resume = resume_command(run_id)
        return {"commands": [{**c, "command": resume} if c["name"] == "Resume the run" else c
                             for c in commands_for(processes)]}

    @app.post("/api/runs/{run_id}/terminal/exec")
    def run_read_only(run_id: str, body: Exec, request: Request) -> Ran:
        if not _allowed(request.headers):
            raise HTTPException(status_code=401)
        root = _run_dir(run_id)
        if root is None:
            raise HTTPException(status_code=404)
        where = _under(root, body.cwd)
        argv = read_only(body.command, root, where)
        if argv is None:
            raise HTTPException(status_code=422,
                                detail="only a single read-only command, reading inside the run, "
                                       "is run here")

        def capped() -> None:
            import resource

            resource.setrlimit(resource.RLIMIT_FSIZE, (_OUTPUT_CAP, _OUTPUT_CAP))

        with tempfile.TemporaryFile() as sink:
            try:
                done = subprocess.run(argv, cwd=where, stdout=sink, stderr=subprocess.STDOUT,
                                      timeout=15, preexec_fn=capped)  # noqa: PLW1509
                code = done.returncode
            except subprocess.TimeoutExpired:
                return Ran(command=body.command, output="(stopped after 15 s)", exit=124)
            sink.seek(max(0, sink.seek(0, os.SEEK_END) - 20_000))
            output = sink.read().decode(errors="replace")
        return Ran(command=body.command, output=output, exit=code)

    @app.websocket("/api/runs/{run_id}/terminal/console")
    async def console(socket: WebSocket, run_id: str) -> None:
        if not _allowed(socket.headers):
            await socket.close(code=4401)
            return
        if not _same_page(socket.headers):
            await socket.close(code=4403)
            return
        root = _run_dir(run_id)
        if root is None:
            await socket.close(code=4404)
            return
        await socket.accept()
        path, at = root / launcher.CONSOLE, 0
        try:
            while True:
                data = b""
                if path.exists():
                    with path.open("rb") as log:
                        log.seek(at)
                        data = log.read(65536)
                if data:
                    at += len(data)
                    await socket.send_bytes(data)
                else:
                    await asyncio.sleep(0.25)
        except (WebSocketDisconnect, RuntimeError):
            return

    @app.websocket("/api/runs/{run_id}/terminal/shell")
    async def shell(socket: WebSocket, run_id: str, cwd: str = "") -> None:
        if not _allowed(socket.headers):
            await socket.close(code=4401)
            return
        if not _same_page(socket.headers):
            await socket.close(code=4403)
            return
        root = _run_dir(run_id)
        if root is None:
            await socket.close(code=4404)
            return
        await socket.accept()
        where = _under(root, cwd)
        pid, fd = pty.fork()
        if pid == 0:  # the shell; it never returns into a copy of this server
            try:
                os.chdir(where)
                prompt = r"\[\e[1;32m\]\W\[\e[0m\] \[\e[34m\]$\[\e[0m\] "
                os.environ.update(TERM="xterm-256color", PS1=prompt)
                os.execvp("bash", ["bash", "--norc", "-i"])
            finally:
                os._exit(1)
        loop = asyncio.get_running_loop()
        out: asyncio.Queue[bytes] = asyncio.Queue()

        def readable() -> None:
            try:
                out.put_nowait(os.read(fd, 65536))
            except OSError:
                out.put_nowait(b"")

        loop.add_reader(fd, readable)

        async def pump() -> None:
            while True:
                data = await out.get()
                if not data:
                    await socket.close()
                    return
                await socket.send_bytes(data)

        pumping = asyncio.create_task(pump())
        try:
            while True:
                message = await socket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    os.write(fd, message["bytes"])
                elif message.get("text"):
                    sent = json.loads(message["text"])
                    if sent.get("type") == "resize":
                        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                                    struct.pack("HHHH", int(sent["rows"]), int(sent["cols"]), 0, 0))
                    elif sent.get("type") == "input":
                        os.write(fd, str(sent["data"]).encode())
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass
        finally:
            loop.remove_reader(fd)
            pumping.cancel()
            _end(pid)
            os.close(fd)

    return app
