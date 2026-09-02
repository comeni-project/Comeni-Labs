"""The canvas and the layout must agree on geometry, and **nothing was checking that they did.**

`frontend/src/build/geometry.ts` duplicates `dag_core.layout`'s constants, because the server
computes the canonical arrangement and the browser owns a node's position while you drag it.
That duplication is a deliberate cost, and `geometry.ts`'s own header said it was paid for:

    The constants below are `layout.py`'s, and that duplication is the cost of the split. It is
    bounded — six numbers — and `test_the_canvas_and_the_layout_agree_on_geometry` holds them
    together from the Python side rather than trusting the comment.

**There was no such test.** The name was written down, the guarantee was described, and a search
of the repository for it returns nothing. By the time Plan 4 phase 6 changed `NODE_W` from 232 to
172 the two files had been free to disagree for two plans — and they did, silently, which is
exactly what the sentence promised could not happen.

That is `Restored.test.tsx`'s lesson arriving a second time, and it is worth stating plainly:
**a comment claiming a guard exists is worse than no comment, because it stops the next person
looking.** This file is that guard, written under the name the comment used.
"""

import re
from pathlib import Path

import pytest
from dag_core import layout

GEOMETRY = Path(__file__).resolve().parents[3] / "frontend" / "src" / "build" / "geometry.ts"

# The Python name on the left, the TypeScript name on the right. Written out rather than derived,
# because a mapping that guesses would quietly stop covering a constant somebody renamed.
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
    """Every constant the two share, compared by value.

    A mismatch here is not a style defect: the server places a node and the browser draws it, so
    a browser that thinks a node is 232 wide draws its ports 60px past the box the layout routed
    a wire to. That is the 39-pixels-onto-nothing defect the operator found by dragging, with a
    different cause.
    """
    canvas = _declared()
    assert canvas, "geometry.ts parsed to nothing — the regex, not the geometry, is wrong"
    for py_name, ts_name in SHARED.items():
        want = getattr(layout, py_name)
        assert ts_name in canvas, f"geometry.ts declares no {ts_name} (layout.{py_name} = {want})"
        assert canvas[ts_name] == want, (
            f"geometry.ts {ts_name} = {canvas[ts_name]}, layout.{py_name} = {want}"
        )


def test_the_canvas_declares_nothing_the_layout_does_not_have():
    """The other direction, which is the one that rots.

    A constant left behind in `geometry.ts` after the Python name is deleted is a number the
    browser still lays out with and nothing computes any more — `MIN_H` and `COL_PITCH` were both
    in exactly that state when this test was written. The diagnostics guard has had this pair
    since Plan 1, and for the same reason: only one of the two directions catches rot.
    """
    canvas = _declared()
    strays = sorted(
        name for name in canvas
        if name in SHARED.values() and not hasattr(layout, name)
    )
    assert strays == [], f"geometry.ts keeps constants the layout no longer has: {strays}"


@pytest.mark.parametrize("gone", ["MIN_H", "COL_PITCH", "ROW_PITCH"])
def test_the_names_the_flip_retired_are_gone(gone: str):
    """`MIN_H` sized a node from its port count and `COL_PITCH`/`ROW_PITCH` named the axes the
    wrong way round. All three are meaningless after Plan 4 phase 6, and a number nothing
    computes is a number somebody will lay out with."""
    assert not hasattr(layout, gone), f"layout still exports {gone}"
    assert gone not in _declared(), f"geometry.ts still exports {gone}"
