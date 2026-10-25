"""Keep the server layout and browser canvas geometry synchronized.

The server computes canonical positions while the browser also needs the same dimensions for
interactive placement. These tests guard that deliberate duplication in
``frontend/src/build/geometry.ts``.
"""

import re
from pathlib import Path

import pytest
from dag_core import layout

GEOMETRY = Path(__file__).resolve().parents[3] / "frontend" / "src" / "build" / "geometry.ts"

# Keep the mapping explicit so a rename cannot silently remove a constant from this guard.
SHARED = {
    "NODE_W": "NODE_W",
    "NODE_H": "NODE_H",
    "HEAD_H": "HEAD_H",
    "PORT_ROW": "PORT_ROW",
    "PORT_GAP": "PORT_GAP",
    "SPINE": "SPINE",
    "SECOND": "SECOND",
    "RANK_PITCH": "RANK_PITCH",
    "SIBLING_PITCH": "SIBLING_PITCH",
    "CORNER": "CORNER",
}


def _declared() -> dict[str, int]:
    """Every `export const NAME = <int>;` in `geometry.ts`."""
    text = GEOMETRY.read_text()
    return {
        name: int(value)
        for name, value in re.findall(r"^export const (\w+)\s*=\s*(-?\d+);", text, re.M)
    }


def test_the_canvas_and_the_layout_agree_on_geometry():
    """The browser and server use the same value for every shared constant."""
    canvas = _declared()
    assert canvas, "geometry.ts parsed to nothing — the regex, not the geometry, is wrong"
    for py_name, ts_name in SHARED.items():
        want = getattr(layout, py_name)
        assert ts_name in canvas, f"geometry.ts declares no {ts_name} (layout.{py_name} = {want})"
        assert canvas[ts_name] == want, (
            f"geometry.ts {ts_name} = {canvas[ts_name]}, layout.{py_name} = {want}"
        )


def test_the_canvas_declares_nothing_the_layout_does_not_have():
    """The browser does not retain a shared constant removed from the server."""
    canvas = _declared()
    strays = sorted(
        name for name in canvas
        if name in SHARED.values() and not hasattr(layout, name)
    )
    assert strays == [], f"geometry.ts keeps constants the layout no longer has: {strays}"


@pytest.mark.parametrize("gone", ["MIN_H", "COL_PITCH", "ROW_PITCH"])
def test_the_names_the_flip_retired_are_gone(gone: str):
    """Retired variable-height and axis-specific constants stay removed."""
    assert not hasattr(layout, gone), f"layout still exports {gone}"
    assert gone not in _declared(), f"geometry.ts still exports {gone}"
