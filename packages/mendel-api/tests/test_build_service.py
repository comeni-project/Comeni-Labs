"""A resolved pipeline, laid out, over HTTP.

**The canvas opens on a goal, not on a stored pipeline.** Nothing persists one, and 3C is not the
phase to add a table — `pipeline.yml` is already the save file, and inventing a second home for
it to make a screen easier is the sort of decision that should be made when something needs it.
So: a goal goes in, a resolved and laid-out pipeline comes back, and nothing is written.
"""

from mendel_api.services import build


def test_the_example_goal_builds_a_spine():
    got = build.example()
    assert got.steps, "the spine has steps"
    assert got.layout.nodes, "and the steps are placed"
    assert len(got.layout.nodes) == len(got.steps)


def test_every_wire_joins_two_placed_steps():
    got = build.example()
    placed = {node.id for node in got.layout.nodes}
    for wire in got.layout.wires:
        assert wire.from_node in placed and wire.to_node in placed


def test_the_provenance_counts_every_decision_once():
    """**The product thesis compressed into one element** — `dashboard.md` §4. If the segments do
    not sum to the number of steps, the bar is showing a share of something other than the
    pipeline, which is the one thing it must never do."""
    got = build.example()
    assert sum(got.provenance.values()) == len(got.steps)


def test_a_tier_three_choice_is_not_counted_as_settled():
    """`star_align` exits at tier 3 in this registry — a rule matched measured data. The headline
    is *settled without judgement*, and tier 3 is not that: `CLAUDE.md` says yellow means the
    machinery worked, check the premise."""
    got = build.example()
    assert got.provenance.get("3", 0) >= 1
    assert got.settled_share < 1.0


def test_building_twice_gives_the_same_coordinates():
    """Invariant 10's discipline, over the wire. A canvas that moved between two identical
    requests would make every screenshot a lie."""
    assert build.example().layout == build.example().layout


def test_the_example_is_served():
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    body = client.get("/api/pipeline/example").json()
    assert body["steps"], "the spine has steps"
    assert body["layout"]["nodes"], "and they are placed"
    assert body["layout"]["height"] > 0


def test_a_goal_that_names_a_path_is_refused():
    """**Invariant 15, at the door.** No input accepts a sample identifier, a filename or a path;
    `Goal` forbids extras, so a body carrying one is a 422 rather than a silently dropped field.
    """
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    sent = client.post("/api/pipeline", json={"have": ["fastq.reads"], "input": "/data/s1.fq"})
    assert sent.status_code == 422
