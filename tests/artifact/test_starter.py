"""One file to start from: a version-8 `pipeline.yml` with only `intent` and `facts` (Part I.0
Plan B, spec §8.5). `mendel build <file>` resolves it and writes the whole file."""

import pytest
import yaml
from mendel_compiler import pipeline_file
from mendel_compiler.cli import main
from support.paths import ROOT

STARTER = ROOT / "examples" / "rnaseq.yml"
EXAMPLE_NF = ROOT / "tests" / "golden" / "example" / "main.nf"


def test_the_example_starter_is_intent_and_facts_only():
    assert set(yaml.safe_load(STARTER.read_text())) == {"version", "intent", "facts"}


def test_a_starter_builds_the_example_byte_for_byte(tmp_path):
    out = tmp_path / "out"
    assert main(["build", str(STARTER), "--out", str(out), "--root", str(ROOT)]) == 0
    assert yaml.safe_load((out / "pipeline.yml").read_text())["version"] == 8
    assert (out / "main.nf").read_text() == EXAMPLE_NF.read_text()


def test_a_starter_with_steps_is_not_a_starter():
    with pytest.raises(ValueError, match="mendel upgrade"):
        pipeline_file.goal_from(ROOT / "tests" / "fixtures" / "pipeline-v8" / "pipeline.yml")


def test_build_needs_a_starter(capsys):
    with pytest.raises(SystemExit):
        main(["build", "--out", "x"])
    assert "needs a starter file" in capsys.readouterr().err


@pytest.mark.parametrize("verb", ["emit", "publish"])
def test_a_starter_is_not_emitted_or_published(tmp_path, capsys, verb):
    """Review #2: a starter is a valid `Pipeline` with no steps, and `emit` wrote `workflow {}`
    at exit 0. A file with nothing resolved is built, never emitted."""
    target = tmp_path / "starter"
    target.mkdir()
    (target / "modules").mkdir()
    (target / "pipeline.yml").write_text(STARTER.read_text())
    args = ["emit", str(target / "pipeline.yml"), "--out", str(target)] if verb == "emit" \
        else ["publish", str(target / "pipeline.yml")]
    assert main(args) == 2
    assert "mendel build" in capsys.readouterr().err
    assert not (target / "main.nf").exists()
