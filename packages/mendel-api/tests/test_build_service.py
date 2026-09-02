"""A resolved pipeline, laid out, over HTTP.

**The canvas opens on a goal, not on a stored pipeline.** Nothing persists one, and 3C is not the
phase to add a table — `pipeline.yml` is already the save file, and inventing a second home for
it to make a screen easier is the sort of decision that should be made when something needs it.
So: a goal goes in, a resolved and laid-out pipeline comes back, and nothing is written.
"""

import pathlib

from mendel_api.services import build


def test_the_example_goal_builds_a_spine():
    got = build.example()
    assert got.steps, "the spine has steps"
    assert got.layout.nodes, "and the steps are placed"
    assert len(got.layout.nodes) == len(got.steps)


def test_every_wire_joins_two_placed_steps():
    got = build.example()
    placed = {node.id for node in got.layout.nodes}
    assert got.layout.wires, "a graph with no wires joins nothing; this asserts over air"
    for wire in got.layout.wires:
        assert wire.from_node in placed and wire.to_node in placed


def test_the_provenance_counts_every_decision_once():
    """**The product thesis compressed into one element** — `dashboard.md` §4. If the segments do
    not sum to the number of steps, the bar is showing a share of something other than the
    pipeline, which is the one thing it must never do."""
    got = build.example()
    # **Every decision, not every step.** A setting exits at its own tier and can be the tier-4
    # one —  is, on this registry — so a bar counting steps reported
    # zero needing a decision while one plainly did.
    assert sum(got.provenance.values()) == len(got.steps) + sum(
        len(step.settings) for step in got.steps
    )


def test_a_tier_three_choice_is_not_counted_as_settled():
    """`star_align` exits at tier 3 in this registry — a rule matched measured data. The headline
    is *settled without judgement*, and tier 3 is not that: `CLAUDE.md` says yellow means the
    machinery worked, check the premise."""
    got = build.example()
    assert got.provenance.get("3", 0) >= 1
    assert got.settled_share < 1.0


def test_a_step_is_flagged_when_one_of_its_settings_needs_a_decision():
    """**Invariant 6, and the bug it caught.**

    `star_align` exits at tier 3 and its `seq_platform` exits at tier 4. Flagging by the step's
    own tier reported nothing to review on a pipeline that says, in its own artifact,
    *selected the first of 1 candidates without judgement — please review*.
    """
    got = build.example()
    assert "star_align" in got.needs_review
    flagged = next(s for s in got.steps if s.id == "star_align")
    assert any(setting.tier == 4 for setting in flagged.settings)


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


# ═══ CHANNELS — spec §12.3, the seam neither spec covered ═════════════════════════════════
#
# §0's finding was that the canvas derives its own answer and disagrees with the artifact:
# `Sources.entryChannels()` returned one entry per unwired input PORT — five on the spine,
# three of them `annotation.gtf` — while the resolver deduplicated by type and the emitted
# workflow had one `params.gtf`. The run sheet listed three things to bind where the pipeline
# had one hole, and two of the three answers went nowhere.


def test_the_spine_reports_one_channel_per_hole_and_not_one_per_port():
    """**The number is the whole point.** Five unwired input ports, three channels.

    Asserted as an inequality against the ports rather than as a literal `3`, because a literal
    would pass just as happily against a derivation that had gone back to counting ports on a
    registry where the two numbers happened to agree.
    """
    got = build.example()
    fed = {f"{w.to_node}.{w.to_port}" for w in got.layout.wires}
    unwired = [
        f"{step.id}.{port.name}"
        for step in got.steps
        for port in step.ports
        if port.side == "in" and port.met and f"{step.id}.{port.name}" not in fed
    ]
    assert len(got.channels) < len(unwired), (
        f"{len(unwired)} unwired ports collapse to {len(got.channels)} channels; "
        "one socket per port is the defect spec section 0 is about"
    )
    assert sum(len(c.ports) for c in got.channels) == len(unwired)


def test_a_channel_names_every_port_it_feeds():
    """This is what the canvas draws against: a socket is placed relative to a consumer, so a
    channel with no ports has nowhere to go and a channel with three is drawn once with three
    stubs rather than three times."""
    got = build.example()
    for channel in got.channels:
        assert channel.ports, f"channel {channel.name} feeds nothing"
    gtf = next(c for c in got.channels if c.type_id == "annotation.gtf")
    assert len(gtf.ports) > 1, "the spine's GTF feeds both the aligner and featureCounts"


def test_a_channel_carries_the_param_a_laboratory_fills_and_it_is_not_always_the_name():
    """`fastq.reads` is named `reads` and reads `params.input`.

    The run sheet asks for a channel's `param`, so collapsing the two fields would have it ask
    for `params.reads` on a pipeline whose workflow reads `params.input` — the interface and the
    artifact disagreeing again, in a new place.
    """
    got = build.example()
    reads = next(c for c in got.channels if c.type_id == "fastq.reads")
    assert reads.name == "reads"
    assert reads.param == "input"


def test_the_browser_derives_no_channel_of_its_own():
    """`Sources.entryChannels()` is deleted, not left beside `BuiltPipeline.channels`.

    Two derivations of one fact is the defect this whole plan started from, and keeping the old
    one "for now" is how it survives. Checked from the Python side because the TypeScript half
    cannot see whether the function it calls is reading or computing — the honest assertion is
    that the browser's copy of the rule is gone, and this is where the rule now lives.
    """
    source = (
        pathlib.Path(__file__).parents[3] / "frontend" / "src" / "build" / "Sources.tsx"
    ).read_text()
    body = source[source.index("export function entryChannels") :]
    body = body[: body.index("\n}")]
    assert "data.channels" in body, "entryChannels must read the server's answer"
    assert "port.side" not in body, "entryChannels must not walk the ports again"
