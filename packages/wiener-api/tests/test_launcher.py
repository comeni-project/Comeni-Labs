# packages/wiener-api/tests/test_launcher.py
def test_site_config_turns_on_the_two_things_wiener_needs(a_run):
    """§4.3 finding 6: without `trace.enabled` the resource fields are absent entirely, and
    everything the dashboard draws depends on this one line."""
    from wiener_api.services.launcher import site_config

    text = site_config(a_run)
    assert "weblog {" in text and "enabled = true" in text
    assert "trace {" in text and "trace.enabled" not in text  # a block, not a dotted key
    assert a_run.ingest_secret in text


def test_the_executor_is_a_profile_and_never_an_emission(a_run):
    """`docs/design/execution-boundary.md` §6 — the executor reaches a run through -profile
    and -c site.config, never through what Mendel emitted."""
    from wiener_api.services.launcher import command

    argv = command(a_run, workdir="/tmp/x")
    assert "-c" in argv
    profiles = argv[argv.index("-profile") + 1].split(",")
    assert profiles[0] == "local"
    assert "docker" in profiles, (
        "a run needs the executor AND a container runtime: the emitted config separates them "
        "and its own k8s profile says `-profile k8s,docker -c site.config`. With one profile "
        f"every process runs uncontained. Got {profiles}."
    )


def test_a_launch_writes_no_client_supplied_path(a_run):
    """Invariant 15's shape, one level out: the directory is derived from an opaque run id."""
    from wiener_api.services.launcher import work_dir

    assert str(work_dir(a_run.id)).endswith(a_run.id)


def test_launch_copies_the_artifact_and_starts_nextflow_there(a_run, session, tmp_path,
                                                              monkeypatch):
    """The one function in this module that touches the world, exercised through its seam.

    Without this, `launch()` is first executed at Checkpoint 2 against real Nextflow — and the
    three tests above cover the strings it assembles, not the thing it does with them.
    """
    from wiener_api import repository
    from wiener_api.models import RunArtifact
    from wiener_api.services import launcher
    from wiener_api.settings import settings

    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")
    monkeypatch.setattr(settings, "work_root", tmp_path / "work")
    stored = settings.artifact_root / a_run.artifact_id
    (stored / "modules").mkdir(parents=True)
    (stored / "main.nf").write_text("workflow {}\n")

    repository.add(session, a_run.lab_id, RunArtifact(
        id=a_run.artifact_id, uploaded_by="test",
        uploaded_at=a_run.submitted_at, digest="sha256:" + "0" * 64, size_bytes=1,
    ))
    session.commit()

    spawned: list[tuple[list[str], str]] = []
    monkeypatch.setattr(launcher, "_spawn", lambda argv, cwd: spawned.append((argv, str(cwd))))

    launcher.launch(a_run.id)

    workdir = launcher.work_dir(a_run.id)
    assert (workdir / "main.nf").read_text() == "workflow {}\n", "the artifact was not copied"
    assert (workdir / "site.config").exists(), "nothing told the head process where to report"
    assert a_run.ingest_secret in (workdir / "site.config").read_text()
    assert spawned and spawned[0][1] == str(workdir), "Nextflow was not started in the copy"
    assert repository.run(session, a_run.lab_id, a_run.id).phase == "launching"
