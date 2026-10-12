"""A queued run survives losing Redis: its parameters are on disk in its own directory (#273).

Part H spec §4. No table holds them (invariant 15); the job carries the run id only, and a run
still `queued` when the worker starts is queued again — `launch`'s claim makes that safe.
"""

import asyncio
import json

import wiener_rows
from wiener_api import repository
from wiener_api.services import launcher
from wiener_api.settings import settings

PARAMS = {"input": "/data/sheet.csv", "fasta": "/refs/g.fa"}


def _submit(client, a_bundle, params):
    stored = client.post("/api/artifacts", files={"bundle": ("p.zip", a_bundle)}).json()
    return client.post("/api/runs", json={"artifact_id": stored["artifact_id"],
                                          "params": params, "executor": "local"})


def test_submit_writes_the_parameters_beside_the_run_and_queues_only_its_id(client, a_bundle):
    answer = _submit(client, a_bundle, PARAMS)
    run_id = answer.json()["run_id"]
    assert json.loads(launcher.params_path(run_id).read_text()) == PARAMS
    assert client.queued == [("launch_job", (run_id,))]


def test_a_failed_write_leaves_no_queued_run(client, a_bundle, monkeypatch, session):
    def refuse(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(launcher, "write_params", refuse)
    answer = _submit(client, a_bundle, PARAMS)
    assert answer.status_code == 507
    assert "MW0101" in answer.json()["detail"]
    assert repository.runs(session, settings.lab_id) == []
    assert client.queued == []


def test_a_run_whose_job_was_lost_is_queued_again(session, monkeypatch, tmp_path):
    from wiener_api import worker

    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    queued = wiener_rows.a_run(session, phase="queued")
    wiener_rows.a_run(session, phase="running")
    launcher.write_params(queued.id, {"input": "/d"})
    sent = []

    class Redis:
        async def enqueue_job(self, name, *args):
            sent.append((name, args))

    assert asyncio.run(worker.requeue_queued({"redis": Redis()})) == 1
    assert sent == [("launch_job", (queued.id,))]


def test_launch_reads_the_parameters_from_the_run_s_directory(a_run, session, tmp_path,
                                                             monkeypatch):
    """The other half: what submit wrote is what Nextflow is handed."""
    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    (settings.artifact_root / a_run.artifact_id).mkdir(parents=True)
    launcher.write_params(a_run.id, {"fasta": "/refs/g.fa"})
    spawned = []
    monkeypatch.setattr(launcher, "_spawn",
                        lambda argv, cwd: spawned.append(argv) or type("P", (), {"pid": 1})())
    monkeypatch.setattr(launcher, "process_started_at", lambda pid: None)
    assert launcher.launch(a_run.id)
    argv = spawned[0]
    assert argv[argv.index("-params-file") + 1].endswith(f"{a_run.id}/params.json")
    assert json.loads(launcher.params_path(a_run.id).read_text())["fasta"] == "/refs/g.fa"


def test_the_worker_queues_lost_runs_again_when_it_starts(session, monkeypatch, tmp_path):
    """The hook arq runs, not the function alone: a requeue nothing calls recovers nothing."""
    from wiener_api import worker

    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    queued = wiener_rows.a_run(session, phase="queued")

    async def quiet(ctx):
        return None

    monkeypatch.setattr(worker, "warn_about_the_pairing", quiet)
    sent = []

    class Redis:
        async def enqueue_job(self, name, *args):
            sent.append((name, args))

    asyncio.run(worker.WorkerSettings.on_startup({"redis": Redis()}))
    assert sent == [("launch_job", (queued.id,))]
