from pathlib import Path

import pytest
from mendel_forge import sources
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.sources import ToolRef


class _Fake:
    name = "fake"

    def discover(self, root: Path) -> list[ToolRef]:
        return [ToolRef(source="fake", ident="tool-b"), ToolRef(source="fake", ident="tool-a")]

    def ingest(self, ref: ToolRef, root: Path) -> Observation:
        return Observation(
            source="fake",
            ref_id=ref.ident,
            facts={"n": Fact(value=1, evidence=Excerpt(locator="x:1", text="t"))},
        )


def test_a_ref_round_trips_through_its_text_form():
    assert ToolRef.parse("nf-core:fastqc") == ToolRef(source="nf-core", ident="fastqc")
    assert str(ToolRef(source="nf-core", ident="fastqc")) == "nf-core:fastqc"


def test_a_ref_without_a_source_is_refused():
    with pytest.raises(ValueError, match="MF0001"):
        ToolRef.parse("fastqc")


def test_a_registered_source_is_retrievable_by_name(monkeypatch):
    monkeypatch.setattr(sources, "_REGISTERED", {})
    sources.register(_Fake())
    assert sources.names() == ["fake"]
    assert sources.get("fake").ingest(ToolRef.parse("fake:x"), Path(".")).ref_id == "x"


def test_an_unknown_source_names_the_ones_that_exist(monkeypatch):
    monkeypatch.setattr(sources, "_REGISTERED", {})
    sources.register(_Fake())
    with pytest.raises(ValueError, match="MF0001") as caught:
        sources.get("pegi3s")
    assert "fake" in str(caught.value)


def test_discover_is_sorted(monkeypatch):
    """Two sources listing tools in filesystem order would make `forge discover` output
    depend on the machine. Determinism is not only about emitted files."""
    monkeypatch.setattr(sources, "_REGISTERED", {})
    sources.register(_Fake())
    found = sources.discover_all(Path("."))
    assert [r.ident for r in found] == ["tool-a", "tool-b"]
