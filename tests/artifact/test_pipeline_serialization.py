"""Saved-pipeline serialization: observable CLI and artifact behavior."""

import shutil

from mendel_compiler.emit import emit
from support.pipeline import (
    _answer,
    _build,
    _declared,
    _emit,
    _load,
)


def test_build_writes_pipeline_yml_and_not_the_two_it_replaces(tmp_path):
    out = _build(tmp_path)
    assert (out / "pipeline.yml").exists()
    assert not (out / "pipeline.ir.json").exists()
    assert not (out / "mendel.lock.yml").exists()


def test_build_emits_from_the_round_tripped_file(tmp_path):
    """The round trip is load-bearing on every build, not a property asserted once here.

    `emit` is handed the reparsed object, so a field that does not survive YAML makes the
    generated Nextflow wrong immediately rather than the next time somebody reads the file.
    """
    out = _build(tmp_path)
    assert emit(_load(out)) == (out / "main.nf").read_text()


def test_emit_reproduces_both_generated_files_byte_for_byte(tmp_path, capsys):
    """A pipeline regenerates from its own file, with no registry and no vocabulary.

    This is what the whole materialisation was for: a laboratory archives a validated
    pipeline and rebuilds its Nextflow years later without the registry it was built
    against — the part that resolves differently as it changes.
    """
    out = _build(tmp_path)
    before = {name: (out / name).read_text() for name in ("main.nf", "nextflow.config")}
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert {name: (out / name).read_text() for name in before} == before


def test_a_stale_pipeline_file_is_reported_and_then_cured(tmp_path, capsys):
    """Nextflow runs `main.nf`, not `pipeline.yml`.

    Edit the file you were told to edit, forget to re-emit, and the pipeline that runs is not
    the pipeline that is documented — with every file digest matching, because the bytes on
    disk are exactly the bytes that were written. `from_digest` is what notices, and `emit`
    restamps it, so the same command twice is silent the second time.
    """
    out = _build(tmp_path)
    _answer(out, "seq_platform", "nanopore")
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" in err
    code, err = _emit(out, capsys)
    assert code == 0 and "MD0213" not in err, "re-emitting must restamp from_digest"


def test_hand_editing_main_nf_is_refused_and_the_fix_names_the_other_file(tmp_path, capsys):
    """Regenerating would destroy the edit silently, so this one really does refuse.

    And the fix says **edit `pipeline.yml`** rather than "revert your change": a person who
    hand-edited `main.nf` was trying to change the pipeline, and the file that does that is
    the other one. A diagnostic that only forbids is half a diagnostic.
    """
    out = _build(tmp_path)
    (out / "main.nf").write_text(
        _declared(out / "main.nf", (out / "main.nf").read_text() + "\n// touched\n")
    )
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0214" in err
    assert "pipeline.yml" in err, "the fix must say where to make the change"


def test_a_deleted_generated_file_is_rewritten_rather_than_refused(tmp_path, capsys):
    """The escape hatch `MD0214`'s fix names, and it has to work.

    Nothing is destroyed by regenerating a file that is not there, so refusing would leave a
    person with a hand-edited `main.nf` and no way forward except editing the digest by hand —
    which is teaching them to defeat the guard.
    """
    out = _build(tmp_path)
    (out / "main.nf").unlink()
    code, err = _emit(out, capsys)
    assert code == 0, err
    assert (out / "main.nf").exists()


def test_emit_refuses_when_modules_are_absent(tmp_path, capsys):
    """`include` paths would point at nothing. Never emit a `main.nf` that cannot run."""
    out = _build(tmp_path)
    shutil.rmtree(out / "modules")
    code, err = _emit(out, capsys)
    assert code != 0 and "MD0210" in err


def test_from_digest_is_computed_with_emitted_excluded(tmp_path):
    """The exclusion is load-bearing, exactly as `ResolvedValue._drop_computed`'s is: a
    derived field inside the thing it describes does not round-trip."""
    out = _build(tmp_path)
    pipeline = _load(out)
    assert pipeline.emitted is not None
    assert pipeline.emitted.from_digest == pipeline.content_digest()
    without = pipeline.model_copy(update={"emitted": None})
    assert pipeline.content_digest() == without.content_digest()
