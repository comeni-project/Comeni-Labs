"""What a run published — `GET /api/runs/{id}/results`.

The endpoint that ends the loop. Until 2026-08-30 a finished run left its outputs in
`work/<hash>/` under names nobody can read, and that had blocked three separate screens.
"""

from wiener_api.services import launcher


def _publish(run_id: str, files: dict[str, str]) -> None:
    """Put files where a real run's `publishDir` would have put them."""
    root = launcher.results_dir(run_id)
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def test_a_run_lists_what_it_published(client, a_run):
    _publish(a_run.id, {
        "trimgalore/sample_1_trimmed.fq.gz": "x",
        "subread_featurecounts/counts.txt": "gene\tcount\n",
    })

    body = client.get(f"/api/runs/{a_run.id}/results").json()

    assert body["published"] is True
    assert body["total"] == 2
    assert {(f["process"], f["name"]) for f in body["files"]} == {
        ("trimgalore", "sample_1_trimmed.fq.gz"),
        ("subread_featurecounts", "counts.txt"),
    }
    assert all(f["size_bytes"] > 0 for f in body["files"])


def test_a_run_that_published_nothing_is_not_a_run_that_cannot_publish(client, a_run):
    """**Three absences, and they are different facts** — `rn-absence`'s rule.

    An empty list would say *this run produced no output* about a run that has not started, a
    run whose pipeline predates publishing entirely, and a run that genuinely made nothing. The
    first two are `published: false`; only the third is an empty list with `published: true`.

    Getting this wrong is the `ProcessRow.reported_resources` mistake in a new place: a dash
    never means zero, and here an empty list must never mean *we cannot tell*.
    """
    before = client.get(f"/api/runs/{a_run.id}/results").json()
    assert before["published"] is False, "nothing has been launched, so nothing can be said"
    assert before["files"] == []

    launcher.results_dir(a_run.id).mkdir(parents=True, exist_ok=True)

    after = client.get(f"/api/runs/{a_run.id}/results").json()
    assert after["published"] is True, "the run reached launch and published nothing"
    assert after["files"] == []
    assert after["total"] == 0


def test_results_are_scoped_to_a_lab(client, a_run, session):
    """`repository.py`'s header: a filter you can forget is a leak — and this hands back
    filenames, which is the shape a leak takes here."""
    from wiener_api.models import Run

    session.query(Run).filter(Run.id == a_run.id).update({"lab_id": "somebody-else"})
    session.commit()
    _publish(a_run.id, {"trimgalore/secret.txt": "x"})

    assert client.get(f"/api/runs/{a_run.id}/results").status_code == 404


def test_an_unknown_run_is_a_404_and_not_an_empty_list(client):
    assert client.get("/api/runs/deadbeef/results").status_code == 404


def test_the_listing_pages(client, a_run):
    """A 5,000-task run publishes more than a page.

    W2 shipped a console that fetched once at 200 and subscribed, and it was invisible on every
    run anybody had because the largest was five tasks. Same file, one endpoint along.
    """
    _publish(a_run.id, {f"trimgalore/f{n:03}.txt": "x" for n in range(250)})

    first = client.get(f"/api/runs/{a_run.id}/results?limit=100").json()
    assert len(first["files"]) == 100
    assert first["total"] == 250, "total counts what matched, never what is on the page"

    last = client.get(f"/api/runs/{a_run.id}/results?after=200&limit=100").json()
    assert len(last["files"]) == 50
    assert last["total"] == 250

    names = {f["name"] for f in first["files"]} | {f["name"] for f in last["files"]}
    assert len(names) == 150, "pages must not overlap"


def test_a_name_is_relative_and_never_a_path_on_this_machine(client, a_run):
    """The endpoint hands out names, not locations. An absolute path here would tell whoever
    asks where the server keeps its runs — and `work_dir` exists precisely so no client ever
    learns or supplies one."""
    _publish(a_run.id, {"star_align/deep/nested.bam": "x"})

    body = client.get(f"/api/runs/{a_run.id}/results").json()
    for entry in body["files"]:
        assert not entry["name"].startswith("/")
        assert str(launcher.results_dir(a_run.id)) not in entry["name"]
