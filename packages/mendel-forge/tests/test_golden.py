import json
import os
from pathlib import Path

from mendel_forge.assemble import scaffold_for
from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = Path(__file__).parent / "golden" / "nf-core-fastqc.scaffold.json"


def _scaffold():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), ROOT / "registry")
    return scaffold_for(
        obs, layers.load(ROOT / "registry"), ident="nf-core/fastqc", version="0.12.1"
    )


def test_the_scaffold_matches_the_golden_file():
    """A change in what the forge derives shows up as a reviewable diff, the same way a
    change in generated Nextflow does. Regenerate with FORGE_GOLDEN=update, and READ the
    diff before committing it — reading the golden file is what caught the Jinja
    `{%- endfor %}` collision that put every loop iteration on one line."""
    produced = _scaffold().model_dump_json(indent=2) + "\n"
    if os.environ.get("FORGE_GOLDEN") == "update":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(produced)
    assert produced == GOLDEN.read_text()


def test_the_same_source_twice_is_byte_identical():
    """Determinism is a test here too. A dict serialises in insertion order, which is parse
    order, which moves under a refactor that changed nothing anybody asked to change."""
    assert _scaffold().model_dump_json(indent=2) == _scaffold().model_dump_json(indent=2)


def test_hole_order_does_not_depend_on_construction_order():
    """`Scaffold` sorts holes on serialisation. Build one with the holes reversed and the
    output must not move — otherwise the golden file records an accident of parse order."""
    scaffold = _scaffold()
    shuffled = scaffold.model_copy(update={"holes": list(reversed(scaffold.holes))})
    assert shuffled.model_dump_json(indent=2) == scaffold.model_dump_json(indent=2)


def test_the_golden_file_is_not_empty():
    """A golden test comparing two empty strings passes and asserts nothing."""
    assert len(json.loads(GOLDEN.read_text())["holes"]) > 0


def test_no_locator_is_an_absolute_path():
    """The bug the first golden file caught, held so it cannot return.

    The initial run wrote `/home/<user>/.../worktrees/forge-phase-1/vendor/modules/...`
    into every fact's evidence, which makes the golden file machine-dependent and puts the
    author's checkout path in every draft. Same defect as issue #46's `digest_of_directory`
    walking `.git`, and caught the same way — by reading a generated artifact rather than
    by a test that was already green.
    """
    scaffold = _scaffold()
    locators = [f.evidence.locator for f in scaffold.observation.facts.values()]
    locators += [e.locator for e in scaffold.observation.prose]
    locators += [e.locator for hole in scaffold.holes for e in hole.evidence]
    absolute = [loc for loc in locators if loc.startswith("/")]
    assert absolute == [], f"locators must be relative to the source root: {absolute}"
    assert locators, "no locators at all; this test is asserting nothing"
