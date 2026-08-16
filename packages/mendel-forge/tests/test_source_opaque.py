from pathlib import Path

from mendel_forge.sources import ToolRef

from .opaque_source import OpaqueSource

FIXTURES = Path(__file__).parent / "fixtures" / "opaque"


def test_it_discovers_the_fake_tool():
    assert [str(r) for r in OpaqueSource().discover(FIXTURES)] == ["opaque:widget"]


def test_it_derives_a_container_and_a_name_and_nothing_else():
    obs = OpaqueSource().ingest(ToolRef.parse("opaque:widget"), FIXTURES)
    assert obs.fact("container") == "docker.io/example/widget:1.4.0"
    assert obs.fact("process") is None, "a source with no module cannot know a process name"
    assert obs.fact("emits") is None
    assert obs.fact("nf_include") is None


def test_it_carries_the_documentation_as_prose():
    obs = OpaqueSource().ingest(ToolRef.parse("opaque:widget"), FIXTURES)
    assert any("counts things" in e.text for e in obs.prose)


def test_it_satisfies_the_same_protocol_as_nf_core():
    """The whole reason this file exists. If `Source` grows a member only nf-core can
    supply, this stops type-checking and the seam has quietly closed."""
    from mendel_forge.sources import Source

    def takes_any_source(source: Source) -> str:
        return source.name

    assert takes_any_source(OpaqueSource()) == "opaque"
