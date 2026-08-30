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
    assert not (workdir / "params.json").exists(), "no params were supplied, so none are written"
    assert a_run.ingest_secret in (workdir / "site.config").read_text()
    assert spawned and spawned[0][1] == str(workdir), "Nextflow was not started in the copy"
    assert repository.run(session, a_run.lab_id, a_run.id).phase == "launching"
    assert launcher.results_dir(a_run.id).is_dir(), (
        "a run that publishes nothing must have an empty results directory rather than none — "
        "otherwise /results cannot tell 'produced no output' from 'no such run'"
    )


def test_the_launcher_says_where_outputs_go(a_run):
    """A run publishes into its own directory, and the artifact never named one.

    `emit.py`'s `PUBLISH_DIR` emits `params.outdir = null` because where results go is a SITE
    fact — the same argument `process.resourceLimits` makes about how big the machine is. This
    is the other half: Wiener supplies the value, derived from the opaque run id exactly as
    `work_dir` is, so no path is ever accepted from a client.
    """
    from wiener_api.services.launcher import command, results_dir, work_dir

    argv = command(a_run, workdir=str(work_dir(a_run.id)))
    assert "--outdir" in argv, "nothing would be published at all"
    given = argv[argv.index("--outdir") + 1]
    assert given == str(results_dir(a_run.id))
    assert given.startswith(str(work_dir(a_run.id))), (
        f"outputs must land inside the run's own directory, not beside it: {given}"
    )
    assert a_run.id in given, "derived from the opaque id, never from anything a client sent"


def test_the_destination_is_a_command_line_param_and_not_the_site_config(a_run):
    """**Not a style choice, and the reason is Nextflow's evaluation order.**

    `publishDir`'s `enabled:` is an expression evaluated while the `process {` scope is read.
    A `-c` file layers on top and a `profiles {` block is read afterwards, so neither can turn
    publishing on; a command-line param can, because those are injected before parsing.

    Measured on 2026-08-30 against a real stub run: a profile-set `outdir` published **nothing**
    with all five processes green, and the same config with `--outdir` published 41 files. This
    test exists because that failure is completely silent — no error, no warning, no log line.
    """
    from wiener_api.services.launcher import command, site_config, work_dir

    assert "outdir" not in site_config(a_run), (
        "in site.config this is read too late to enable publishing, and it fails silently"
    )
    assert "--outdir" in command(a_run, workdir=str(work_dir(a_run.id)))


def test_wiener_never_asks_a_person_for_an_output_directory(tmp_path, monkeypatch):
    """`outdir` is a null in the artifact, and a null is how Wiener discovers what to ask for.

    Left alone, the run sheet would have offered a field for it — turning a server's own
    business into a client-supplied filesystem path, which is what `work_dir`'s docstring
    refuses on this side and what invariant 15 refuses on Mendel's.
    """
    from wiener_api.services import artifacts
    from wiener_api.settings import settings

    root = tmp_path / "artifacts" / "abc"
    root.mkdir(parents=True)
    (root / "nextflow.config").write_text(
        "params {\n    input = null\n    gtf = null\n    outdir = null\n}\n"
    )
    monkeypatch.setattr(settings, "artifact_root", tmp_path / "artifacts")

    assert artifacts.declared_holes("abc") == {"input", "gtf"}
    assert "outdir" in artifacts.SUPPLIED_BY_WIENER
