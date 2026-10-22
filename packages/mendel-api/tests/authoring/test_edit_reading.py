"""A hand edit is read, not saved (one builder, #395): at any phase the engine reads what the edit
means, offers the reading in the chat in its own words, and nothing changes until the person
confirms it. Confirmed, it is the person's change, re-planned as a correction is."""

from mendel_api_tests.http import _building, _session, needs_db
from mendel_api_tests.http import clean as clean
from mendel_api_tests.http import client as client
from mendel_api_tests.http import queue as queue

FASTQC = "nf-core/fastqc@0.12.1"


def _walked(client, building, until):
    """The walk settled step by step until `until` is drawn: mid-walk, with a card pending."""
    from mendel_api.services import session as facade
    from mendel_authoring import commands

    for _ in range(8):
        picture = facade.read(building["id"])
        if until in {n["id"] for n in picture["graph"]["nodes"]}:
            return _session(client, building["id"])
        pending = picture["pending_proposal"]
        facade.perform(commands.SettleStep(pending["id"], picture["revision"], "ana"))
    raise AssertionError(f"{until} was never drawn")


def _edit(client, session, graph, revision=None):
    return client.post(
        f"/api/pipeline/authoring/{session['id']}/edits",
        json={"graph": graph,
              "expected_revision": session["revision"] if revision is None else revision},
    )


def _without(graph, node):
    return {"nodes": [n for n in graph["nodes"] if n["id"] != node],
            "edges": [e for e in graph["edges"] if node not in (e["from_node"], e["to_node"])]}


def _with_fastqc(graph):
    return {**graph, "nodes": [*graph["nodes"],
                               {"id": "fastqc_1", "contract_id": FASTQC, "params": []}]}


def _decide(client, session, suggestion, decision):
    return client.post(
        f"/api/pipeline/authoring/{session['id']}/suggestions/{suggestion}",
        json={"decision": decision})


@needs_db
def test_removing_trimgalore_mid_walk_offers_the_role_reading_and_changes_nothing(
        client, clean, queue, monkeypatch):
    building = _walked(client, _building(client, queue, monkeypatch)[0], "star_align")
    assert building["phase"] == "building"
    assert "trimgalore" in {n["id"] for n in building["graph"]["nodes"]}

    response = _edit(client, building, _without(building["graph"], "trimgalore"))
    assert response.status_code == 200, response.text
    after = _session(client, building["id"])
    assert after["graph"] == building["graph"]
    assert after["decision_revision"] == building["decision_revision"]
    [reading] = after["suggestions"]
    assert reading["says"] == "So you never want trimming here — right?"
    assert reading["edit"] and response.json()["offered"] == [reading["id"]]


@needs_db
def test_adding_a_step_offers_one_group_of_two(client, clean, queue, monkeypatch):
    building, _ = _building(client, queue, monkeypatch)
    _edit(client, building, _with_fastqc(building["graph"]))
    readings = _session(client, building["id"])["suggestions"]
    assert [r["kind"] for r in readings] == ["want", "pin"]
    assert len({r["edit"] for r in readings}) == 1


@needs_db
def test_applying_one_of_a_group_applies_the_group_in_order(client, clean, queue, monkeypatch):
    building, _ = _building(client, queue, monkeypatch)
    _edit(client, building, _with_fastqc(building["graph"]))
    first = _session(client, building["id"])["suggestions"][1]
    assert _decide(client, building, first["id"], "apply").status_code == 200
    from mendel_api.services import decisions

    goal = decisions.goal(building["draft_id"])
    assert "qc.report" in goal.want
    assert any(p.contract == FASTQC for p in goal.constraints.producers)
    assert _session(client, building["id"])["suggestions"] == []


@needs_db
def test_dismissing_one_of_a_group_dismisses_the_group(client, clean, queue, monkeypatch):
    building, _ = _building(client, queue, monkeypatch)
    _edit(client, building, _with_fastqc(building["graph"]))
    first = _session(client, building["id"])["suggestions"][0]
    assert _decide(client, building, first["id"], "dismiss").status_code == 200
    assert _session(client, building["id"])["suggestions"] == []


@needs_db
def test_a_second_reading_on_the_same_subject_stales_the_first(client, clean, queue, monkeypatch):
    """Review Focus 1: remove STAR (exclude at the alignment site), then swap the aligner (a pin
    at the same site) — only the later reading waits."""
    building = _walked(client, _building(client, queue, monkeypatch)[0], "star_align")
    graph = building["graph"]
    assert "star_align" in {n["id"] for n in graph["nodes"]}
    _edit(client, building, _without(graph, "star_align"))
    swapped = {**graph, "nodes": [
        {**n, "contract_id": "nf-core/hisat2/align@2.2.2"} if n["id"] == "star_align" else n
        for n in graph["nodes"]]}
    _edit(client, building, swapped)
    [waiting] = _session(client, building["id"])["suggestions"]
    assert waiting["kind"] == "pin"


@needs_db
def test_an_edit_on_an_old_revision_is_refused_and_offers_nothing(
        client, clean, queue, monkeypatch):
    """Review Focus 3: two tabs."""
    building, _ = _building(client, queue, monkeypatch)
    response = _edit(client, building, _with_fastqc(building["graph"]),
                     revision=building["revision"] - 1)
    assert response.status_code == 422
    assert response.json()["detail"].startswith("MI0201")
    assert _session(client, building["id"])["suggestions"] == []


@needs_db
def test_a_drag_offers_nothing_and_writes_no_receipt(client, clean, queue, monkeypatch):
    """Review Focus 4: a move is layout; `DraftGraph` has no coordinates, so the same graph."""
    building, _ = _building(client, queue, monkeypatch)
    response = _edit(client, building, building["graph"])
    assert response.json() == {"revision": building["revision"], "offered": []}
    after = _session(client, building["id"])
    assert after["suggestions"] == [] and len(after["turns"]) == len(building["turns"])


@needs_db
def test_a_typed_value_is_applied_at_once_as_the_persons(client, clean, queue, monkeypatch):
    building = _walked(client, _building(client, queue, monkeypatch)[0], "star_align")
    graph = building["graph"]
    node = next(n for n in graph["nodes"] if n["id"] == "star_align")
    typed = {**graph, "nodes": [
        {**n, "params": [*n["params"], {"name": "seq_platform", "value": "ILLUMINA"}]}
        if n is node else n for n in graph["nodes"]]}
    response = _edit(client, building, typed)
    assert response.status_code == 200, response.text
    from mendel_api.services import decisions

    [value] = [p for p in decisions.read(building["draft_id"]).parameters
               if p.name == "seq_platform"]
    assert value.value == "ILLUMINA"
    assert _session(client, building["id"])["suggestions"] == []
