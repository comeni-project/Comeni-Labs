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


def test_every_configured_root_is_absolute_in_the_compose_file():
    """**The defect checkpoint 1 found, turned into a test.**

    `EXAMPLE` was `Path("examples/rnaseq-goal.yml")` — a bare relative path, resolved against the
    process's working directory. That is the repository root under pytest and `/app` in a
    container, so every test here passed and the endpoint answered 500 the first time the stack
    came up.

    The general form is not *did somebody remember to configure this one*: it is that a service
    reading a path from settings must be handed an absolute one, and the compose file is where
    that is decided. A new `MENDEL_*_ROOT` default that nothing overrides will fail here.
    """
    import re
    from pathlib import Path

    from mendel_api.settings import Settings

    compose = (Path(__file__).resolve().parents[3] / "docker-compose.yml").read_text()
    declared = {
        f"MENDEL_{name.upper()}"
        for name, field in Settings.model_fields.items()
        if field.annotation is Path
    }
    for key in sorted(declared):
        found = re.search(rf"{key}: *(\S+)", compose)
        assert found, f"{key} is a path setting that docker-compose.yml never sets"
        assert found.group(1).startswith("/"), f"{key} is relative in the container"
