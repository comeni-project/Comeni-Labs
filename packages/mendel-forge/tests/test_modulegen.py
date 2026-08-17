from mendel_forge.modulegen import needs_module, skeleton
from mendel_forge.observe import Excerpt, Fact, Observation


def _obs_without_a_module() -> Observation:
    return Observation(
        source="opaque",
        ref_id="opaque:widget",
        facts={
            "container": Fact(
                value="docker.io/example/widget:1.4.0",
                evidence=Excerpt(locator="tool.yml:container", text="x"),
            )
        },
    )


def test_a_source_with_no_include_needs_a_module():
    assert needs_module(_obs_without_a_module()) is True


def test_a_source_that_ships_one_does_not():
    obs = _obs_without_a_module().model_copy(
        update={
            "facts": {
                "nf_include": Fact(
                    value="modules/nf-core/fastqc/main",
                    evidence=Excerpt(locator="m:1", text="t"),
                )
            }
        }
    )
    assert needs_module(obs) is False


def test_the_skeleton_declares_the_process_the_contract_names(widget_scaffold):
    assert "process WIDGET {" in skeleton(widget_scaffold)


def test_the_skeleton_has_a_stub_block(widget_scaffold):
    """-stub-run is the fast validation tier, and a module with no stub cannot use it.
    nf-core modules all define one, which is why the whole DAG executes in seconds."""
    text = skeleton(widget_scaffold)
    assert "\n    stub:\n" in text
    assert "touch " in text.split("stub:")[1]


def test_the_script_body_is_a_marked_hole_not_a_guess(widget_scaffold):
    """The one field that is honestly not derivable. A plausible command line here would be
    the exact failure mode this project exists to be an alternative to."""
    from mendel_forge.modulegen import SCRIPT_HOLE

    text = skeleton(widget_scaffold)
    assert SCRIPT_HOLE in text
    assert "MF0005" in SCRIPT_HOLE
    script = text.split("script:")[1].split("stub:")[0]
    assert "--" not in script, "the skeleton must not invent flags for a tool it cannot read"


def test_the_skeleton_declares_the_container_it_was_given(widget_scaffold):
    assert 'container "docker.io/example/widget:1.4.0"' in skeleton(widget_scaffold)


def test_the_skeleton_parses_back_through_ModuleSpec(tmp_path, widget_scaffold):
    """The generated module must be readable by the parser conformance uses, or rung 4
    cannot run against it at all. If this raises, the skeleton is wrong, not the parser:
    ModuleSpec reads four shapes and raises rather than guessing on a fifth."""
    from mendel_compiler.modulespec import ModuleSpec

    path = tmp_path / "main.nf"
    path.write_text(skeleton(widget_scaffold))
    spec = ModuleSpec.parse(path)
    assert spec.process == "WIDGET"
    assert spec.container == "docker.io/example/widget:1.4.0"
    assert "out" in spec.emits
    assert spec.reads_ext_args is True
