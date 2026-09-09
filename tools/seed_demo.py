#!/usr/bin/env python
"""Seed the running website with a demo pipeline.

The browser's empty-state path can show the example pipeline, but the home page reads stored
drafts. This script turns a goal file into the same `DraftGraph` shape the builder saves and
posts it through the public API, so a demo starts with a visible pipeline row.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOAL = ROOT / "examples" / "rnaseq-goal.yml"


class Api:
    def __init__(self, base: str, timeout: float) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: object | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(
            f"{self.base}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{method} {req.full_url} failed with HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"{method} {req.full_url} failed: {error.reason}") from error
        return json.loads(raw) if raw else None

    def upload(self, bundle: bytes, name: str) -> dict[str, Any]:
        boundary = "----comeni-demo-seed"
        body = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="bundle"; filename="pipeline.zip"\r\n'
                "Content-Type: application/zip\r\n\r\n"
            ).encode()
            + bundle
            + (
                f"\r\n--{boundary}\r\n"
                f'Content-Disposition: form-data; name="name"\r\n\r\n{name}\r\n'
                f"--{boundary}--\r\n"
            ).encode()
        )
        req = Request(
            f"{self.base}/artifacts",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as error:
            detail = (
                error.read().decode("utf-8", errors="replace")
                if isinstance(error, HTTPError)
                else error.reason
            )
            raise RuntimeError(f"POST {req.full_url} failed: {detail}") from error


def load_goal(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"goal file does not exist: {path}") from error
    if not isinstance(loaded, dict):
        raise RuntimeError(f"goal file must contain a YAML object: {path}")
    return loaded


def graph_of(built: dict[str, Any], goal: dict[str, Any]) -> dict[str, Any]:
    """The frontend's `graphOf`, plus the goal profile the API view does not carry."""
    graph: dict[str, Any] = {
        "nodes": [
            {"id": step["id"], "contract_id": step["contract_id"], "params": []}
            for step in built.get("steps", [])
        ],
        "edges": [
            {
                "from_node": wire["from_node"],
                "from_port": wire["from_port"],
                "to_node": wire["to_node"],
                "to_port": wire["to_port"],
            }
            for wire in built.get("layout", {}).get("wires", [])
        ],
    }
    if isinstance(goal.get("profile"), dict):
        graph["profile"] = goal["profile"]
    return graph


def existing_draft(api: Api, name: str) -> str | None:
    page = api.request("GET", "/pipeline/drafts")
    for row in page.get("drafts", []):
        if row.get("name") == name:
            return row.get("id")
    return None


def bundle_of(draft_id: str) -> bytes:
    root = ROOT / ".run" / "drafts" / draft_id
    if not (root / "pipeline.yml").is_file():
        raise RuntimeError(f"kept draft has no pipeline.yml: {root}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    return buffer.getvalue()


def seed_fake_runs(
    api: Api, draft_id: str, name: str, steps: list[dict[str, Any]], running: bool = False
) -> list[str]:
    """Insert demo runs and replay their events through the projection tables.

    Wiener deliberately has no public "fake run" endpoint. This uses psql only from this
    operator-facing demo command, while the event payloads remain the same shape as a real run.
    """
    existing = api.request("GET", "/runs?limit=200")
    if any(row.get("name") == name for row in existing.get("runs", [])):
        return []

    artifact = api.upload(bundle_of(draft_id), name)
    artifact_id = artifact["artifact_id"]
    now = datetime.now(UTC).replace(microsecond=0)
    statements: list[str] = []
    specs = ((5, False),) if running else tuple(enumerate((False, False, False, True), start=1))
    for run_number, failed in specs:
        run_id = hashlib.sha256(f"comeni-demo:{draft_id}:{run_number}".encode()).hexdigest()[:32]
        started = (
            now - timedelta(minutes=3)
            if running
            else now - timedelta(days=run_number - 1, hours=run_number)
        )
        base_ms = int(started.timestamp() * 1000)
        ended = started + timedelta(minutes=31 + run_number * 4)
        phase = "running" if running else ("failed" if failed else "succeeded")
        sql_time = started.isoformat()
        sql_end = ended.isoformat()
        exit_code = "NULL" if running else (1 if failed else 0)
        end_value = "NULL" if running else f"'{sql_end}'"
        statements.append(
            "INSERT INTO run (id, lab_id, artifact_id, submitted_by, submitted_at, phase, "
            "executor, ingest_secret, nextflow_run_name, exit_code, ended_at) "
            f"VALUES ('{run_id}', 'local', '{artifact_id}', 'demo', '{sql_time}', "
            f"'{phase}', 'local', '{run_id}demo', 'rnaseq-demo-{run_number}', "
            f"{exit_code}, {end_value}) ON CONFLICT (id) DO NOTHING;"
        )

        task_total = 21 if running else (2, 5, 8, 5)[run_number - 1]
        stage_indices = [
            min((task_id - 1) * len(steps) // task_total, len(steps) - 1)
            for task_id in range(1, task_total + 1)
        ]
        event_rows = [{"kind": "started", "trace": None, "manifest": None}]
        tasks: list[tuple[int, dict[str, Any], str]] = []
        for task_id in range(1, task_total + 1):
            stage_index = stage_indices[task_id - 1]
            stage_order = stage_indices[: task_id - 1].count(stage_index)
            step = steps[stage_index]
            task_failed = failed and task_id == task_total
            process = step.get("process", step.get("id", "STEP"))
            task_running = running and task_id > task_total - 4
            status = "RUNNING" if task_running else ("FAILED" if task_failed else "COMPLETED")
            # Tight spacing lets repeated samples overlap in the same process lane, making
            # parallel cores visible rather than looking like a serial pipeline.
            start_gap = 55000 if running else 120000 + run_number * 7000
            start_ms = (
                base_ms + stage_index * start_gap + stage_order * 5000
                if running
                else base_ms + task_id * start_gap
            )
            complete_ms = (
                base_ms + stage_index * start_gap + 50000 + stage_order * 1000
                if running
                else start_ms + 120000 + task_id * 18000 + run_number * 5000
            )
            cpus = (2, 4, 8, 6, 12)[(task_id + run_number - 2) % 5]
            memory_bytes = (4, 8, 16, 8, 32)[(task_id + run_number - 2) % 5] * 1024**3
            peak_rss_bytes = int(memory_bytes * (0.28 + task_id * 0.06))
            pct_cpu = 42.5 + ((task_id * 19 + run_number * 11) % 53)
            trace = {
                "task_id": task_id,
                "process": process,
                "name": f"{process} (demo)",
                "status": status,
                "exit": None if task_running else (1 if task_failed else 0),
                "attempt": 1,
                "submit_ms": start_ms - 500,
                "start_ms": start_ms,
                "complete_ms": None if task_running else complete_ms,
                "duration_ms": None if task_running else complete_ms - start_ms,
                "realtime_ms": None if task_running else complete_ms - start_ms - 12000,
                "cpus": cpus,
                "memory_bytes": memory_bytes,
                "peak_rss_bytes": peak_rss_bytes,
                "pct_cpu": pct_cpu,
                "read_bytes": (40 + task_id * 35) * 1024**2,
                "write_bytes": (18 + task_id * 21) * 1024**2,
                "hash": f"demo/{task_id:06x}",
                "tag": f"sample_{task_id:02d}",
            }
            event_rows.extend(
                [
                    {
                        "kind": "process_submitted",
                        "trace": {
                            **trace,
                            "status": "SUBMITTED",
                            "exit": None,
                            "start_ms": None,
                            "complete_ms": None,
                            "duration_ms": None,
                            "realtime_ms": None,
                        },
                    },
                    {
                        "kind": "process_started",
                        "trace": {
                            **trace,
                            "status": "RUNNING",
                            "exit": None,
                            "complete_ms": None,
                            "duration_ms": None,
                            "realtime_ms": None,
                        },
                    },
                    *(
                        []
                        if task_running
                        else [{"kind": "process_completed", "trace": trace, "manifest": None}]
                    ),
                ]
            )
            attempts = json.dumps(
                [
                    {
                        "n": 1,
                        "status": status,
                        "exit": None if task_running else (1 if task_failed else 0),
                        "at_ms": start_ms,
                        "memory_bytes": trace["memory_bytes"],
                        "peak_rss_bytes": trace["peak_rss_bytes"],
                        "cpus": trace["cpus"],
                        "pct_cpu": trace["pct_cpu"],
                        "read_bytes": trace["read_bytes"],
                        "write_bytes": trace["write_bytes"],
                        "realtime_ms": trace["realtime_ms"],
                        "start_ms": start_ms,
                        "complete_ms": None if task_running else complete_ms,
                    }
                ]
            ).replace("'", "''")
            labels = json.dumps(
                [
                    {
                        "n": 1,
                        "tag": trace["tag"],
                        "name": trace["name"],
                        "hash": trace["hash"],
                        "workdir": f"/demo/{run_id}/{task_id}",
                    }
                ]
            ).replace("'", "''")
            tasks.append(
                (
                    task_id,
                    {
                        "process": process,
                        "status": status,
                        "exit": "NULL" if task_running else (1 if task_failed else 0),
                        "last": complete_ms,
                        "peak": trace["peak_rss_bytes"],
                        "real": "NULL" if task_running else trace["realtime_ms"],
                        "cpu": trace["pct_cpu"],
                        "attempts": attempts,
                        "labels": labels,
                    },
                    status,
                )
            )
        if not running:
            event_rows.append(
                {
                    "kind": "completed",
                    "trace": None,
                    "manifest": {
                        "success": not failed,
                        "exit_status": 1 if failed else 0,
                    "succeeded": task_total - int(failed),
                        "failed": int(failed),
                        "cached": 0,
                        "ignored": 0,
                        "report": "demo failure" if failed else None,
                    },
                }
            )
        for seq, event in enumerate(event_rows):
            event_payload = {
                "kind": event["kind"],
                "run_id": run_id,
                "at_ms": base_ms + seq * 1000,
                "seq": seq,
                "trace": event.get("trace"),
                "manifest": event.get("manifest"),
            }
            payload = json.dumps(event_payload).replace("'", "''")
            statements.append(
                "INSERT INTO run_event (run_id, lab_id, seq, kind, at_ms, payload, received_at) "
                f"VALUES ('{run_id}', 'local', {seq}, '{event['kind']}', "
                f"{base_ms + seq * 1000}, '{payload}', '{sql_time}') "
                "ON CONFLICT DO NOTHING;"
            )
        for task_id, task, _ in tasks:
            statements.append(
                "INSERT INTO run_task (run_id, lab_id, task_id, process, status, attempts, "
                "latest_exit, last_change_ms, peak_rss_bytes, realtime_ms, pct_cpu, labels, tag) "
                f"VALUES ('{run_id}', 'local', {task_id}, '{task['process']}', "
                f"'{task['status']}', '{task['attempts']}', {task['exit']}, {task['last']}, "
                f"{task['peak']}, {task['real']}, {task['cpu']}, '{task['labels']}', "
                f"'sample_{task_id:02d}') ON CONFLICT DO NOTHING;"
            )

    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "wiener-postgres",
            "psql",
            "-U",
            "wiener",
            "-d",
            "wiener",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input="\n".join(statements).encode(),
        check=False,
    )
    if result.returncode:
        raise RuntimeError("could not seed fake Wiener runs")
    numbers = (5,) if running else range(1, 5)
    return [
        hashlib.sha256(f"comeni-demo:{draft_id}:{n}".encode()).hexdigest()[:32] for n in numbers
    ]


def seed(args: argparse.Namespace) -> dict[str, str | None]:
    api = Api(args.api, args.timeout)
    goal = load_goal(args.goal)
    built = api.request("POST", "/pipeline", goal)
    graph = graph_of(built, goal)
    body = {"graph": graph, "name": args.name}

    draft_id = None if args.fresh else existing_draft(api, args.name)
    if draft_id is None:
        created = api.request("POST", "/pipeline/drafts", body)
        draft_id = created["id"]
        action = "created"
    else:
        api.request("PUT", f"/pipeline/drafts/{draft_id}", body)
        action = "refreshed"

    kept = None
    if args.keep:
        kept = api.request("POST", f"/pipeline/drafts/{draft_id}/keep", {})

    fake_runs = (
        seed_fake_runs(
            Api(args.wiener, args.timeout),
            draft_id,
            args.running_name if args.fake_running else args.name,
            built.get("steps", []),
            running=args.fake_running,
        )
        if getattr(args, "fake_runs", False) or getattr(args, "fake_running", False)
        else []
    )

    query = urlencode({"draft": draft_id})
    return {
        "action": action,
        "draft_id": draft_id,
        "builder_url": f"{args.web.rstrip('/')}/build?{query}",
        "home_url": f"{args.web.rstrip('/')}/",
        "artifact": kept["path"] if kept else None,
        "fake_runs": fake_runs,
    }


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://localhost:8000/api", help="Mendel API base URL")
    ap.add_argument("--wiener", default="http://localhost/api", help="Wiener API base URL")
    ap.add_argument("--web", default="http://localhost:5173", help="website base URL")
    ap.add_argument("--goal", type=Path, default=DEFAULT_GOAL, help="goal YAML to seed")
    ap.add_argument("--name", default="RNA-seq demo", help="pipeline name shown on the home page")
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="create a new draft even when a draft with --name already exists",
    )
    ap.add_argument(
        "--no-keep",
        dest="keep",
        action="store_false",
        help="only create the editable draft; do not write pipeline.yml",
    )
    ap.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    ap.add_argument("--fake-runs", action="store_true", help="also seed four completed demo runs")
    ap.add_argument("--fake-running", action="store_true", help="also seed one running demo run")
    ap.add_argument(
        "--running-name", default="RNA-seq demo (running)", help="name for the live demo run"
    )
    ap.set_defaults(keep=True)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = seed(args)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 2

    print(f"{result['action']} demo draft {result['draft_id']}")
    if result["artifact"]:
        print(f"kept artifact: {result['artifact']}")
    if result["fake_runs"]:
        print(f"fake runs: {len(result['fake_runs'])} (open /runs to browse them)")
    print(f"home:    {result['home_url']}")
    print(f"builder: {result['builder_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
