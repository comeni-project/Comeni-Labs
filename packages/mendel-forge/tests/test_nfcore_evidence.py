"""Evidence a reader can read — including a reader that cannot open the file.

Before this, every fact in an Observation carried `locator="…/main.nf"` and
`text="FASTQC in main.nf"`. Every fact, one citation, no line.
"""

from pathlib import Path

import pytest
from mendel_forge.sources import ToolRef, nfcore

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor"
REF = ToolRef(source="nf-core", ident="fastqc")


@pytest.fixture(scope="module")
def observation():
    return nfcore.NfCoreSource().ingest(REF, VENDOR)


def test_facts_do_not_all_share_one_locator(observation) -> None:
    locators = {fact.evidence.locator for fact in observation.facts.values()}
    assert len(locators) > 1, f"every fact still cites {locators}"


def test_a_source_read_locator_names_a_line(observation) -> None:
    assert ":" in observation.facts["process"].evidence.locator
    path, _, line = observation.facts["process"].evidence.locator.rpartition(":")
    assert path.endswith("main.nf")
    assert line.isdigit()


def _span(locator: str) -> tuple[Path, int, int]:
    """`path:12` or `path:12-16`."""
    path, _, where = locator.rpartition(":")
    first, _, last = where.partition("-")
    return VENDOR / path, int(first), int(last or first)


def test_the_text_is_the_lines_the_locator_names(observation) -> None:
    """The whole point: the citation quotes the evidence, rather than describing it."""
    for key in ("process", "emits", "container", "input_arity"):
        evidence = observation.facts[key].evidence
        path, first, last = _span(evidence.locator)
        actual = path.read_text().splitlines()[first - 1 : last]
        assert evidence.text == "\n".join(line.strip() for line in actual)


def test_a_block_fact_quotes_the_block_and_not_just_its_header(observation) -> None:
    """`text: "output:"` names a real line and teaches a reader nothing — the defect this
    field exists to fix, arriving one level down. A block's declarations are the evidence."""
    for key, declaration in (("emits", "emit: html"), ("input_arity", "path(reads")):
        text = observation.facts[key].evidence.text
        assert declaration in text, f"{key} cites only {text!r}"
        assert "-" in observation.facts[key].evidence.locator, "a span must say it is a span"


def test_no_locator_is_an_absolute_path(observation) -> None:
    """Held already for the old locators; a line suffix must not reintroduce it."""
    for fact in observation.facts.values():
        assert not fact.evidence.locator.startswith("/")
    for excerpt in observation.prose:
        assert not excerpt.locator.startswith("/")


def test_a_derived_fact_says_so_rather_than_citing_a_line(observation) -> None:
    """`nf_include` is computed from the ref, not read from the module. Citing a line for it
    would be a false citation, which is worse than a vague one."""
    assert ":" not in observation.facts["nf_include"].evidence.locator


def test_no_evidence_text_is_empty(observation) -> None:
    """An excerpt whose text is blank is a citation to nothing, and reads as one that worked."""
    for key, fact in observation.facts.items():
        assert fact.evidence.text.strip(), f"{key} cites an empty line"


def test_the_same_module_twice_is_identical(observation) -> None:
    """These reach a golden file, so they must not depend on scan order."""
    again = nfcore.NfCoreSource().ingest(REF, VENDOR)
    assert again.model_dump_json() == observation.model_dump_json()
