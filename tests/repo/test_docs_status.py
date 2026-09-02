"""`tools/docs_status.py` is what makes the vision register honest.

Plan B writes pages in the present tense for features that do not exist, marked with
`!!! warning "Not built yet"`. A marker naming no plan cannot be scheduled or retired, and a
marker that only reports an absence strands the reader — so both are build failures.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docs_status  # noqa: E402

GOOD = '''# A page

!!! warning "Not built yet"
    The agent does not exist. Today you assemble the pipeline on the canvas by hand.
    Tracked in Plan 3.

Body text.
'''

NO_PLAN = '''# A page

!!! warning "Not built yet"
    The agent does not exist. Today you assemble the pipeline on the canvas by hand.
'''

NO_TODAY = '''# A page

!!! warning "Not built yet"
    Tracked in Plan 3.
'''


def _write(tmp_path: pathlib.Path, name: str, text: str) -> pathlib.Path:
    d = tmp_path / "docs" / "start"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(text, encoding="utf-8")
    return tmp_path / "docs"


def test_a_well_formed_marker_is_found_and_carries_its_plan(tmp_path):
    docs = _write(tmp_path, "a.md", GOOD)
    markers = docs_status.scan(docs)
    assert len(markers) == 1
    assert markers[0].plan == "Plan 3"
    assert markers[0].page == "start/a.md"


def test_a_marker_naming_no_plan_is_a_problem(tmp_path):
    docs = _write(tmp_path, "b.md", NO_PLAN)
    problems = docs_status.problems(docs_status.scan(docs))
    assert any("names no plan" in p for p in problems)


def test_a_marker_that_does_not_say_what_happens_today_is_a_problem(tmp_path):
    """Spec §3.3 rule 2 — a marker reporting only an absence strands the reader."""
    docs = _write(tmp_path, "c.md", NO_TODAY)
    problems = docs_status.problems(docs_status.scan(docs))
    assert any("what happens today" in p for p in problems)


def test_a_clean_set_of_markers_has_no_problems(tmp_path):
    docs = _write(tmp_path, "d.md", GOOD)
    assert docs_status.problems(docs_status.scan(docs)) == []


def test_the_status_page_lists_every_marker(tmp_path):
    docs = _write(tmp_path, "e.md", GOOD)
    page = docs_status.render(docs_status.scan(docs))
    assert "start/e.md" in page
    assert "Plan 3" in page


def test_an_internals_page_without_a_serves_line_is_a_problem(tmp_path):
    """Spec §3.2 — accuracy was never the problem with the old docs; orphaning was."""
    d = tmp_path / "docs" / "internals"
    d.mkdir(parents=True)
    (d / "f.md").write_text("# Some internals page\n\nBody.\n", encoding="utf-8")
    problems = docs_status.problems(docs_status.scan(tmp_path / "docs"),
                                    root=tmp_path / "docs")
    assert any("Serves:" in p for p in problems)
