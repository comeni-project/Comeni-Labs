"""Prepare local state, preserve registry work, and manage bounded development startup.

Make remains the command entry point. Helpers accept explicit paths and commands so tests
can use disposable repositories and fake processes rather than a live application.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def refresh_registry(source: Path, target: Path) -> None:
    """Clone a missing registry or fast-forward a clean copy; retain dirty/ahead/divergent work."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(source.resolve()), str(target)], check=True
        )
        branch = subprocess.run(
            ["git", "-C", str(target), "symbolic-ref", "-q", "HEAD"],
            capture_output=True,
            check=False,
        )
        if branch.returncode:
            subprocess.run(["git", "-C", str(target), "switch", "-c", "comeni-local"], check=True)
        return
    if git(target, "status", "--porcelain"):
        print("Registry has uncommitted work; left alone.")
        return
    subprocess.run(
        ["git", "-C", str(target), "fetch", "-q", str(source.resolve()), "HEAD"], check=True
    )
    current, wanted = git(target, "rev-parse", "HEAD"), git(target, "rev-parse", "FETCH_HEAD")
    if current == wanted:
        return
    ancestor = subprocess.run(
        ["git", "-C", str(target), "merge-base", "--is-ancestor", current, wanted], check=False
    )
    if ancestor.returncode == 1:
        print("Registry has local or divergent commits; left alone.")
        return
    if ancestor.returncode:
        raise RuntimeError("Could not determine registry ancestry; registry left alone.")
    subprocess.run(["git", "-C", str(target), "merge", "--ff-only", "FETCH_HEAD"], check=True)


def prepare(root: Path) -> None:
    """Create host-owned runtime paths and a writable registry, retaining existing data."""
    env = root / ".env"
    if not env.exists():
        # Exclusive creation avoids replacing an environment created by another invocation.
        try:
            with env.open("x") as stream:
                stream.write((root / ".env.example").read_text())
        except FileExistsError:
            pass
    for path in [".run/wiener/artifacts", ".run/wiener/work", ".run/drafts", "workspace"]:
        (root / path).mkdir(parents=True, exist_ok=True)
    refresh_registry(root / "registry", root / ".run/registry")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.3) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def start_vite(root: Path, command=None, timeout=20.0, port=None) -> None:
    """Start Vite or reuse a ready recorded process; fail and remove its PID on timeout/exit."""
    port = int(port or os.environ.get("VITE_HOST_PORT", "5173"))
    if not 1 <= port <= 65535:
        raise ValueError("VITE_HOST_PORT must be a port number")
    runtime = root / ".run"
    runtime.mkdir(exist_ok=True)
    pidfile, logfile = runtime / "vite.pid", runtime / "vite.log"
    url = f"http://127.0.0.1:{port}/"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
        except ValueError:
            pid = 0
        if pid > 0 and _alive(pid):
            if _ready(url):
                print(f"Vite already ready: {url}")
                return
            raise RuntimeError("Recorded Vite process is not ready; inspect .run/vite.log")
        pidfile.unlink()
    if _ready(url):
        raise RuntimeError(
            "Vite port is already serving an unrecorded process; choose another port"
        )
    command = command or [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--strictPort",
    ]
    with logfile.open("ab") as log:
        child = subprocess.Popen(
            command, cwd=root / "frontend", stdout=log, stderr=log, start_new_session=True
        )
    pidfile.write_text(str(child.pid))
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f"Vite exited with status {child.returncode}; see .run/vite.log")
            if _ready(url):
                print(f"Vite ready: {url}")
                return
            time.sleep(0.1)
        raise RuntimeError("Vite startup timed out; see .run/vite.log")
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        pidfile.unlink(missing_ok=True)
        raise


def wait_postgres(container: str, timeout=30.0) -> None:
    """Bound test-server readiness and print container diagnostics if it never becomes ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            ready = subprocess.run(
                ["docker", "exec", container, "psql", "-U", "mendel", "-qtAc", "SELECT 1"],
                capture_output=True,
                timeout=3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            continue
        if ready.returncode == 0:
            return
        time.sleep(0.2)
    with suppress(subprocess.TimeoutExpired):
        subprocess.run(["docker", "logs", "--tail", "30", container], check=False, timeout=3)
    raise RuntimeError(f"Test PostgreSQL did not become ready within {timeout:g}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="verb", required=True)
    for verb in ["prepare", "registry", "vite"]:
        p = sub.add_parser(verb)
        p.add_argument("--root", type=Path, default=Path.cwd())
        if verb == "vite":
            p.add_argument("--timeout", type=float, default=20)
    p = sub.add_parser("wait-db")
    p.add_argument("container")
    p.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.verb == "prepare":
        prepare(args.root)
    elif args.verb == "registry":
        refresh_registry(args.root / "registry", args.root / ".run/registry")
    elif args.verb == "vite":
        start_vite(args.root, timeout=args.timeout)
    else:
        wait_postgres(args.container, args.timeout)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, subprocess.SubprocessError, OSError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
