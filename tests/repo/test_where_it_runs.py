"""The where-it-runs table covers every place a declared measurer can run (spec §2).

Review focus 1 of 14.7.6.7: a reader must not come away thinking nothing leaves their machine at
level 0. The table has to say the sample's head reaches this server.
"""

from mendel_resolver import layers
from support.paths import ROOT

WORDS = {"server": "this server", "lab": "the lab's machine", "browser": "the browser"}


def _table() -> str:
    page = (ROOT / "docs/design/authoring-protocol.md").read_text()
    assert "## Where each measurer runs" in page, "the protocol page has no where-it-runs table"
    return page.split("## Where each measurer runs", 1)[1].split("\n## ", 1)[0]


def _runs_on() -> list[str]:
    """The *Runs on* cell of every row, so a place named only in the prose around it is missed."""
    rows = [line for line in _table().splitlines() if line.startswith("| **")]
    assert rows, "the where-it-runs table has no rows"
    return [row.split("|")[3] for row in rows]


def test_the_table_names_every_place_a_piece_runs():
    loaded = layers.load(ROOT / "registry")
    places = {f.runs for f in loaded.inspection.formats.values()} | {"lab"}
    assert places, "no measurer declares where it runs"
    cells = _runs_on()
    for place in sorted(places):
        assert any(WORDS[place] in cell for cell in cells), (
            f"no row says what runs on {WORDS[place]}"
        )


def test_the_table_says_a_samples_head_reaches_this_server_at_level_0():
    table = _table()
    assert "level 0" in table and "head reaches this server" in table
