"""A191. The Tasks tab is a query over a projection, never a fold per request."""

import json
from pathlib import Path

from wiener_api import repository
from wiener_api.services import projection
from wiener_api.settings import settings
from wiener_core.events import RunEvent

SPINE = Path(__file__).parents[3] / "tests/fixtures/weblog/spine-run.events.jsonl"


def _replay_into(session, run_id: str) -> None:
    """The capture, through `append()` — so what is asserted is what the projection writes.

    The spine fixture is already *admitted* events rather than raw weblog bodies, so it goes in
    past `admit()`; only its `run_id` is restamped, because the fixture carries the id of the
    run that really produced it.
    """
    for line in SPINE.read_text().splitlines():
        if not line.strip():
            continue
        event = RunEvent.model_validate({**json.loads(line), "run_id": run_id})
        projection.append(session, settings.lab_id, run_id, event)


def test_tasks_sort_by_memory_without_reading_every_attempt(session, a_run):
    """A191. `attempts` is a JSON blob, so ordering by peak memory means loading every
    document — unless the projection writes the number into a column as it goes."""
    _replay_into(session, a_run.id)

    page = repository.tasks_page(session, settings.lab_id, a_run.id,
                                 sort="-peak_rss_bytes", limit=3)
    peaks = [row.peak_rss_bytes for row in page]
    assert len(peaks) == 3 and all(peak is not None for peak in peaks)
    assert peaks == sorted(peaks, reverse=True)


def test_a_task_that_reported_nothing_sorts_last_and_not_first(session, a_run):
    """Absence is not a small number. A task with no peak is not the one that used the least,
    and *biggest first* must not put it at the top either."""
    _replay_into(session, a_run.id)
    orphan = repository.task(session, settings.lab_id, a_run.id, 1)
    orphan.peak_rss_bytes = None
    session.flush()

    page = repository.tasks_page(session, settings.lab_id, a_run.id, sort="-peak_rss_bytes")
    assert page[-1].task_id == 1, "the unreported task is last on a descending sort"

    page = repository.tasks_page(session, settings.lab_id, a_run.id, sort="peak_rss_bytes")
    assert page[0].task_id == 1, "and first on an ascending one — same fact, other end"


def test_an_unknown_sort_falls_back_rather_than_reaching_the_database(session, a_run):
    """The vocabulary is closed. A client-supplied column name is not interpolated anywhere,
    so `sort=; DROP TABLE` is a fallback to `task_id` and not a query."""
    _replay_into(session, a_run.id)
    page = repository.tasks_page(session, settings.lab_id, a_run.id, sort="peak_rss_bytes; --")
    assert [row.task_id for row in page] == sorted(row.task_id for row in page)


def test_filters_narrow_the_page_and_the_total_agrees(session, a_run):
    _replay_into(session, a_run.id)
    page = repository.tasks_page(session, settings.lab_id, a_run.id, process="STAR_ALIGN")
    assert page and all(row.process == "STAR_ALIGN" for row in page)
    assert repository.tasks_total(session, settings.lab_id, a_run.id,
                                  process="STAR_ALIGN") == len(page)
    assert repository.tasks_total(session, settings.lab_id, a_run.id) > len(page)


def test_the_labels_column_is_the_only_place_the_labs_own_words_land(session, a_run):
    """A200. `fold()` keeps none of `tag`, `name`, `hash` or `workdir` — the projection writes
    them from the admitted event, in `wiener-api`, which is impure. This test is the record
    that they arrive; `test_the_fold_is_where_the_lab_strings_stop` is the record that they
    arrive nowhere else."""
    _replay_into(session, a_run.id)
    row = repository.task(session, settings.lab_id, a_run.id, 1)

    assert row.labels and row.labels[0]["name"] == "TRIMGALORE (test)"
    assert row.labels[0]["hash"] and row.labels[0]["workdir"]
    assert [entry["n"] for entry in row.labels] == [1], "one entry per attempt, keyed and merged"

    state = projection.state_of(session, settings.lab_id, a_run.id)
    folded = state.tasks[1].model_dump_json()
    assert "TRIMGALORE (test)" not in folded, "the fold is still where the lab strings stop"


def test_the_route_pages_and_reports_a_total_beyond_the_page(client, session, a_run):
    """A table that says *404 more* has to know, so the total is over the filters and not
    over the page."""
    _replay_into(session, a_run.id)

    body = client.get(f"/api/runs/{a_run.id}/tasks?limit=2&sort=-realtime_ms").json()
    assert len(body["tasks"]) == 2
    assert body["total"] == 5
    times = [task["realtime_ms"] for task in body["tasks"]]
    assert times == sorted(times, reverse=True)


def test_the_route_carries_the_tag_and_no_other_lab_string(client, session, a_run):
    """A200's residual, stated in a test: `tag` crosses and `workdir`, `name` and `script`
    do not. The menu copies a work directory through a different route, never this one."""
    _replay_into(session, a_run.id)

    body = client.get(f"/api/runs/{a_run.id}/tasks").text
    assert "workdir" not in body and "script" not in body
    assert "TRIMGALORE (test)" not in body, "the task name is a lab string too"


def test_retried_only_is_a_query_over_the_blob_and_not_a_scan(session, a_run):
    """`json_array_length` runs against the real `json` column — checked by the audit, and
    checked here, because SQLite and Postgres do not have to agree about JSON functions.

    Nothing in this capture retried, so the honest assertion is that the filter is *empty* and
    does not raise: an unsupported function fails loudly here rather than in production."""
    _replay_into(session, a_run.id)
    assert repository.tasks_page(session, settings.lab_id, a_run.id, retried_only=True) == []
    assert repository.tasks_total(session, settings.lab_id, a_run.id, retried_only=True) == 0


def test_attempt_one_finds_the_tasks_that_never_retried(session, a_run):
    """**The NULL trap, held by a test.**

    A task that never retried can carry a NULL `attempts`, and `json_array_length(NULL)` is
    NULL — so a bare `= 1` matches nothing and *attempt 1* silently returns an empty table
    while the run plainly has tasks. The filter coalesces to 1; this is what watches it.
    """
    _replay_into(session, a_run.id)
    quiet = repository.task(session, settings.lab_id, a_run.id, 1)
    quiet.attempts = None            # SQLAlchemy writes the JSON value `null`
    session.flush()

    first = repository.tasks_page(session, settings.lab_id, a_run.id, attempt=1, limit=50)
    assert any(row.task_id == 1 for row in first), "a NULL attempts is one attempt, not none"
    assert repository.tasks_total(session, settings.lab_id, a_run.id, attempt=1) == len(first)


def test_attempt_three_means_three_or_more(session, a_run):
    """`3+` is the last option the artboard offers, so it is a floor rather than an equality —
    a task on its fifth attempt is exactly what somebody picking it wants to see."""
    _replay_into(session, a_run.id)
    stubborn = repository.task(session, settings.lab_id, a_run.id, 2)
    stubborn.attempts = [{"n": 1}, {"n": 2}, {"n": 3}, {"n": 4}]
    session.flush()

    assert [row.task_id for row in repository.tasks_page(
        session, settings.lab_id, a_run.id, attempt=3, limit=50)] == [2]


def test_the_board_summary_is_not_swallowed_by_the_run_id_route(client, a_run):
    """**A literal path beside a parameterised one is an ORDERING, not a disambiguation.**

    `/runs/summary` and `/runs/{run_id}` both match `GET /api/runs/summary`, and FastAPI takes
    whichever is declared first. Declared after, `summary` is read as a run id and the board's
    tiles 404 on a run nobody asked for — with nothing in the logs to say why. Moving the
    decorator is a one-line change somebody will make while tidying, so this watches it.
    """
    answer = client.get("/api/runs/summary")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["window_days"] == 14
    assert len(body["days"]) == 14, "one bucket per day, including the days nothing ran"
    assert {"day", "succeeded", "failed"} == set(body["days"][0])


def test_the_board_counts_tasks_without_folding_events(session, client, a_run):
    """The tally beside a board row is a GROUP BY over `run_task`, so the page stays a page."""
    _replay_into(session, a_run.id)
    session.flush()

    row = next(r for r in client.get("/api/runs").json()["runs"] if r["id"] == a_run.id)
    assert row["tasks_seen"] > 0
    assert row["tasks_done"] <= row["tasks_seen"]


# ── filtering one run's tasks by tag ─────────────────────────────────────────────────


def test_a_tag_filter_returns_only_that_tag(session, a_run):
    """*How did sampleB do* — the question fan-out created and nothing answered.

    Before Plan 5B phase 4 a reference channel capped every run at one task per process, so a
    per-process row was the whole picture. With N samples a process has N tasks and the tag is
    the only axis that separates them.
    """
    _replay_into(session, a_run.id)

    page = repository.tasks_page(session, settings.lab_id, a_run.id, tag="genome.fasta")
    assert [row.process for row in page] == ["STAR_GENOMEGENERATE"]
    assert repository.tasks_total(session, settings.lab_id, a_run.id, tag="genome.fasta") == 1


def test_the_total_counts_the_filter_and_not_the_run(session, a_run):
    """`total` is what the footer says *404 more* from. A filter the count ignores makes the
    table claim there is more to see when the filter already showed all of it."""
    _replay_into(session, a_run.id)

    whole = repository.tasks_total(session, settings.lab_id, a_run.id)
    tagged = repository.tasks_total(session, settings.lab_id, a_run.id, tag="test")
    assert 0 < tagged < whole, f"{tagged} of {whole} — the filter reached the count or it did not"


def test_a_tag_is_not_a_sample_and_the_fixture_proves_it(session, a_run):
    """**Why the control says `tag` and not `sample`.** `meta.id` is the sample for a per-sample
    process and something else entirely for a reference one — this run tags
    `STAR_GENOMEGENERATE` with `genome.fasta`, and the fan-out stub run tags it `fasta.txt`.

    A control labelled *sample* would be lying on exactly the rows a person is least likely to
    have thought about.
    """
    _replay_into(session, a_run.id)

    tags = {row.tag for row in repository.tasks_page(session, settings.lab_id, a_run.id)}
    assert "genome.fasta" in tags, "the reference task carries a tag that names no sample"
    assert len(tags) > 1


def test_the_column_never_disagrees_with_the_json_it_indexes(session, a_run):
    """`labels` stays authoritative and `TaskOut.tag` still reads it, so the column is an index
    rather than a second source of truth. The moment they can differ, the filter and the cell
    it filtered describe different things and neither is wrong on its face."""
    _replay_into(session, a_run.id)

    rows = repository.tasks_page(session, settings.lab_id, a_run.id)
    assert rows, "the page is empty — the column and the JSON cannot be compared"
    for row in rows:
        assert row.tag == (row.labels or [{}])[-1].get("tag"), row.task_id


def test_an_untagged_run_matches_nothing_rather_than_everything(session, a_run):
    """**The un-back-filled case, and it is not hypothetical.** `labels` arrived on 2026-08-24
    and nothing back-fills it, so every run ingested before that has no tag at all.

    A filter that matched those rows would quietly widen to the whole run; the honest answer is
    an empty result, which is what the screen above has to explain rather than hide.
    """
    _replay_into(session, a_run.id)
    for row in repository.tasks_page(session, settings.lab_id, a_run.id):
        row.tag = None
    session.flush()

    assert repository.tasks_total(session, settings.lab_id, a_run.id, tag="test") == 0
    assert repository.tasks_total(session, settings.lab_id, a_run.id) > 0, "the run still has tasks"
