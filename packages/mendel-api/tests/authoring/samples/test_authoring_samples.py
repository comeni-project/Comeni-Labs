"""An uploaded sample answers a gap: every decided fact recorded as measured, the person's word
standing where it disagrees, nothing guessed (14.7.6.4).

Driven through the service against the throwaway database, with inspections built by hand: the
inspection itself is `test_inspect.py`'s."""

import pytest
from mendel_api.services import inspect
from mendel_api.services import session as facade
from mendel_api.stages import gathering
from mendel_api_tests.database import reachable
from mendel_api_tests.samples import (
    _facts,
    _gathering,
    _measured,
    _payload,
    _pending_for,
    _version,
)
from mendel_api_tests.samples import (
    clean as clean,
)
from mendel_authoring import commands
from mendel_authoring import state as st

pytestmark = pytest.mark.skipif(not reachable(), reason="no database — run `make test-db`")


def test_a_measurement_gap_offers_upload_in_place_of_not_sure(clean):
    sid = _gathering(["counts.matrix"])
    options = _payload(_pending_for(sid, "read_length"))["options"]
    assert "upload" in options and "not_sure" not in options and "cant_share" in options


def test_an_input_an_inspector_reads_offers_upload(clean):
    sid = _gathering(["counts.matrix"])
    options = _payload(_pending_for(sid, "fastq.reads"))["options"]
    assert "upload" in options and "have_it" in options


def test_a_measurement_no_inspector_measures_and_no_rule_reads_is_not_asked(clean):
    """#338: strandedness was the measurement no inspector measures, asked with *Not sure* and
    no upload. Only a tool reads it, so it is not asked at all: each step that reads it stops."""
    sid = _gathering(["counts.matrix"])
    asked = []
    while (pid := facade.pending_id(sid)) and (subject := _payload(pid).get("subject")):
        asked.append(subject)
        options = [o for o in _payload(pid)["options"]
                   if o not in ("dont_have", "value", "not_sure", "upload")]
        facade.perform(commands.AnswerGap(pid, options[0] if options else "value",
                                          150 if not options else None, "ana"))
    assert asked and "strandedness" not in asked


def test_clicking_upload_records_nothing(clean):
    """The option opens the upload; the click itself is not an answer."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    with pytest.raises(ValueError, match="MI0205"):
        facade.perform(commands.AnswerGap(pid, "upload", None, "ana"))


def test_an_upload_records_every_decided_fact_as_measured(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")  # gaps come inputs, paired, read_length, strandedness
    answer = facade.perform(
        commands.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    ).result
    facts = _facts(sid)
    rl = next(f for f in facts if f["subject"] == "read_length")
    assert rl["source"] == "measured" and rl["value"] == 150
    assert rl["pieces"] == ["fastq@1.0.0", "read_length@1.0.0"]
    assert set(answer.recorded) == {"read_length", "paired"}
    assert answer.kept == ["fastq.reads"], "the person already said they have reads"
    assert all(f.get("sample") is None for f in facts)
    assert all("shorter_file" not in (f.get("evidence") or {}) for f in facts)


def test_what_a_sample_measured_is_announced_in_the_conversation(clean):
    """One builder plan 3: a change made outside the chat is said in it, pointing at what it
    changed — one receipt per fact the sample settled, in the order recorded."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = len(facade.read(sid)["turns"])
    facade.perform(commands.SampleInspected(
        pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"))
    receipts = [b for t in facade.read(sid)["turns"][before:] for b in t["blocks"]
                if b["kind"] == "receipt" and b["id"].startswith("sample-")]
    assert receipts, "the sample's facts were not announced"
    assert {r["about"]["subject"] for r in receipts} == {"read_length", "paired"}
    assert all(r["by"] == "resolver" and r["summary"].startswith("Measured from your sample:")
               for r in receipts)


def test_what_the_person_said_is_kept_and_the_difference_reported(clean):
    """Review focus 4: the person said single-end; the file reads as a pair."""
    sid = _gathering(["counts.matrix"])
    facade.perform(commands.AnswerGap(_pending_for(sid, "paired"), "no", None, "ana"))
    pid = _pending_for(sid, "read_length")
    answer = facade.perform(
        commands.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    ).result
    assert answer.disagreed == ["paired"] and "read_length" in answer.recorded
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is False


def test_an_undetermined_answer_leaves_the_gap_open(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    undecided = _measured(paired=True)
    undecided.facts.append(
        inspect.InspectedFact(measurement="read_length", undetermined="lengths vary: 100–151")
    )
    facade.perform(commands.SampleInspected(pid, undecided.model_dump(mode="json"), "ana"))
    assert facade.pending_id(sid) == pid
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is True


def test_a_second_upload_to_an_answered_gap_is_refused(clean):
    """Review focus 3: two tabs. The second is refused like a duplicate click."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    facade.perform(
        commands.SampleInspected(pid, _measured(read_length=150).model_dump(mode="json"), "ana")
    )
    before = _facts(sid)
    with pytest.raises(ValueError, match="MI0203"):
        facade.perform(
            commands.SampleInspected(pid, _measured(read_length=150).model_dump(mode="json"), "ana")
        )
    assert _facts(sid) == before


def test_compose_goal_carries_the_pieces_and_only_declared_counts(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    facade.perform(
        commands.SampleInspected(pid, _measured(read_length=150).model_dump(mode="json"), "ana")
    )
    goal = gathering.compose_goal(sid)
    m = next(m for m in goal.profile.measurements if m.measurement == "read_length")
    assert m.source.value == "measured" and m.pieces == ["fastq@1.0.0", "read_length@1.0.0"]
    assert m.evidence.model_dump(mode="json") == {"records": 2000, "rows": 1000}


def test_a_model_reading_cannot_prefill_upload(clean):
    """Review of #134: a model's reading of typed words picked `upload`, and the person's
    confirming click was then refused. A reading is a value or an answer, never an upload."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    with pytest.raises(ValueError, match="MI0205"):
        facade.perform(commands.PrefillGap(pid, "upload", None, gathering.READ_NOTE))


def test_a_sample_measures_what_the_person_could_not_share(clean):
    """Review of #134: *can't share* is a fact nobody knows. The person's own sample then
    measures it, and that is recorded, never reported as a disagreement with a value nobody gave."""
    sid = _gathering(["counts.matrix"])
    facade.perform(commands.AnswerGap(_pending_for(sid, "paired"), "cant_share", None, "ana"))
    pid = _pending_for(sid, "read_length")
    answer = facade.perform(
        commands.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    ).result
    assert answer.disagreed == [] and "paired" in answer.recorded
    paired = [f for f in _facts(sid) if f["subject"] == "paired"]
    assert len(paired) == 1 and paired[0]["source"] == "measured" and paired[0]["value"] is True


def test_upload_is_offered_only_when_the_person_has_an_input_an_inspector_reads():
    """Issue 227 (decided A): with no FASTQ said, *not sure* stays, since an upload of what the
    person has would end in *nothing reads this type yet*."""
    from mendel_api.authoring.types import Fact, FactKind, FactSource
    from mendel_api.services import gaps, registry

    stack = registry.stack()
    gap = gaps.Gap(kind=FactKind.MEASUREMENT, subject="read_length", why="w")
    without = gathering._gap_options(gap, stack, [])
    assert "not_sure" in without and "upload" not in without
    bam = Fact(kind=FactKind.INPUT, subject="alignment.bam", source=FactSource.PERSON_SAID)
    assert "upload" not in gathering._gap_options(gap, stack, [bam])
    reads = Fact(kind=FactKind.INPUT, subject="fastq.reads", source=FactSource.PERSON_SAID)
    with_reads = gathering._gap_options(gap, stack, [reads])
    assert "upload" in with_reads and "not_sure" not in with_reads


def test_the_log_says_what_a_sample_measured_not_the_options_label(clean):
    """Found screenshotting 14.7.6.6: the history read *Not sure: upload a sample and I'll
    measure it* for a question the sample had answered with 150."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    facade.perform(
        commands.SampleInspected(pid, _measured(read_length=150).model_dump(mode="json"), "ana")
    )
    history = {d["id"]: d for d in facade.read(sid)["history"]}
    assert history[pid]["chosen_option"] == "upload" and history[pid]["answer"] == "150"


def test_an_input_answered_by_upload_logs_i_have_it(clean):
    """Issue 232: the log read *Yes — I'll upload a sample* beside *measured from your
    sample*; the long label squeezed out the question and overflowed the conversation."""
    sid = _gathering(["counts.matrix"])
    pid = facade.pending_id(sid)
    assert _payload(pid)["subject"] == "fastq.reads"
    facade.perform(
        commands.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    )
    history = {d["id"]: d for d in facade.read(sid)["history"]}
    assert history[pid]["chosen_option"] == "upload" and history[pid]["answer"] == "I have it"


def test_an_upload_that_records_nothing_leaves_the_session_where_it_was(clean):
    """Issue 226: an all-undetermined sample still bumped `row_version`, so a click the person
    had already made on the card failed with MI0201."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    before = _version(sid)
    nothing = inspect.Inspection(outcome="unreadable", reason="does not start like fastq", steps=[])
    assert (
        facade.perform(
            commands.SampleInspected(pid, nothing.model_dump(mode="json"), "ana")
        ).result.recorded
        == []
    )
    assert _version(sid) == before


def test_two_uploads_at_once_are_refused_like_a_duplicate_click(clean, monkeypatch):
    """Issue 226: the second of two truly concurrent uploads got MI0201 from the version swap;
    it is a second answer to a settled question, MI0203."""
    import contextlib
    import threading

    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    real = st.settle
    meet = threading.Barrier(2, timeout=1.0)

    def settle_together(**kwargs):
        # Both read the proposal open, unless one waits on the other's lock.
        with contextlib.suppress(threading.BrokenBarrierError):
            meet.wait()
        return real(**kwargs)

    monkeypatch.setattr(st, "settle", settle_together)
    errors: list[str] = []

    def upload():
        try:
            facade.perform(
                commands.SampleInspected(
                    pid, _measured(read_length=150).model_dump(mode="json"), "ana"
                )
            )
        except ValueError as refused:
            errors.append(str(refused))

    threads = [threading.Thread(target=upload) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert len(errors) == 1 and "MI0203" in errors[0], errors
