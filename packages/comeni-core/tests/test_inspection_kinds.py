"""Codecs, formats and measures as declared data; their code beside them in `piece/` (#134)."""

import pytest
from comeni_core.declared.inspection import InspectionCatalogue, MeasurePiece
from comeni_core.declared.layered import declared_entries
from pydantic import ValidationError


def _write(root, rel, text=""):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


FASTQ = (
    "declares: format\nid: fastq\nversion: 1.0.0\nreads: [fastq.reads]\n"
    "extensions: [.fastq, .fq]\nrecord: sequence\nentry: piece/fastq.py\n"
)
READ_LENGTH = (
    "declares: measure\nid: read_length\nversion: 1.0.0\nmeasures: read_length\n"
    "record: sequence\ndecided: {min_records: 1000, modal_share: 0.8}\n"
    "entry: piece/read_length.py\n"
)


def test_pieces_load_and_their_code_is_not_parsed(tmp_path):
    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    _write(tmp_path, "inspectors/formats/fastq/piece/fixtures/notes.yml", "not: declared\n")
    catalogue = InspectionCatalogue.load(tmp_path)
    assert list(catalogue.formats) == ["fastq"]


def test_piece_code_is_in_the_layer_digest(tmp_path):
    """The `module/` rule: code a layer carries is covered by what a pipeline pins."""
    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    code = _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    assert code in declared_entries(tmp_path)


def test_a_piece_naming_an_unknown_id_is_refused_and_the_rest_stay(tmp_path):
    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    _write(tmp_path, "inspectors/measures/read_length/measure.yml", READ_LENGTH)
    _write(tmp_path, "inspectors/measures/read_length/piece/read_length.py", "x = 1\n")
    _write(tmp_path, "inspectors/measures/gc/piece/read_length.py", "x = 1\n")
    _write(
        tmp_path,
        "inspectors/measures/gc/measure.yml",
        READ_LENGTH.replace("id: read_length", "id: gc").replace(
            "measures: read_length", "measures: gc_content"
        ),
    )
    usable, refused = InspectionCatalogue.load(tmp_path).check(
        type_ids={"fastq.reads"}, measurement_ids={"read_length"}
    )
    assert sorted(usable.measures) == ["read_length"]
    assert len(refused) == 1 and "MD0317" in refused[0] and "gc_content" in refused[0]


def test_an_entry_outside_piece_is_refused():
    with pytest.raises(ValidationError):
        MeasurePiece.model_validate(
            {"id": "x", "version": "1.0.0", "measures": "x", "record": "sequence",
             "decided": {}, "entry": "../elsewhere.py"}
        )


def test_bytecode_beside_piece_code_is_not_in_the_layer_digest(tmp_path):
    """Review of #134: running a piece writes `piece/__pycache__/*.pyc`, which embeds the
    source's mtime and the interpreter's version — the layer digest would move on every test
    run and differ between clones (issue #46 by another route)."""
    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    code = _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    pyc = _write(tmp_path, "inspectors/formats/fastq/piece/__pycache__/fastq.cpython-312.pyc")
    stray = _write(tmp_path, "inspectors/formats/fastq/piece/old.pyc")
    entries = declared_entries(tmp_path)
    assert code in entries, "the piece's own code must stay covered"
    assert pyc not in entries and stray not in entries


# ── a piece that could never run is refused, the others stay (issue 224) ──────────────────


def _check(root):
    return InspectionCatalogue.load(root).check(
        type_ids={"fastq.reads"}, measurement_ids={"read_length"}
    )


def _fastq_with_code(root):
    _write(root, "inspectors/formats/fastq/format.yml", FASTQ)
    _write(root, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")


def test_a_piece_whose_entry_is_missing_is_refused(tmp_path):
    _fastq_with_code(tmp_path)
    _write(tmp_path, "inspectors/measures/read_length/measure.yml", READ_LENGTH)
    usable, refused = _check(tmp_path)
    assert list(usable.formats) == ["fastq"] and usable.measures == {}
    assert len(refused) == 1 and "MD0318" in refused[0] and "piece/read_length.py" in refused[0]


def test_a_piece_whose_id_is_not_its_folder_is_refused(tmp_path):
    _fastq_with_code(tmp_path)
    _write(tmp_path, "inspectors/measures/length/measure.yml", READ_LENGTH)
    _write(tmp_path, "inspectors/measures/length/piece/read_length.py", "x = 1\n")
    usable, refused = _check(tmp_path)
    assert usable.measures == {}
    assert len(refused) == 1 and "MD0318" in refused[0] and "length" in refused[0]


def test_a_piece_needing_a_piece_no_layer_declares_is_refused(tmp_path):
    _fastq_with_code(tmp_path)
    _write(tmp_path, "inspectors/measures/read_length/measure.yml",
           READ_LENGTH + "needs: [pairs]\n")
    _write(tmp_path, "inspectors/measures/read_length/piece/read_length.py", "x = 1\n")
    usable, refused = _check(tmp_path)
    assert usable.measures == {}
    assert len(refused) == 1 and "MD0318" in refused[0] and "pairs" in refused[0]


def test_a_whole_piece_is_kept(tmp_path):
    """The other half: a piece with its code, its folder and what it needs, stays."""
    _fastq_with_code(tmp_path)
    _write(tmp_path, "inspectors/measures/read_length/measure.yml",
           READ_LENGTH + "needs: [fastq]\n")
    _write(tmp_path, "inspectors/measures/read_length/piece/read_length.py", "x = 1\n")
    usable, refused = _check(tmp_path)
    assert refused == [] and list(usable.measures) == ["read_length"]


def test_a_formats_file_count_is_a_range():
    from comeni_core.declared.inspection import FormatPiece

    base = {"id": "f", "version": "1.0.0", "reads": ["t"], "extensions": [".f"],
            "record": "sequence", "entry": "piece/f.py"}
    assert FormatPiece.model_validate({**base, "files": "1..2"}).file_counts == (1, 2)
    assert FormatPiece.model_validate(base).file_counts == (1, 2)
    for bad in ("one or two", "2..1", "0..2", "1..", "3"):
        with pytest.raises(ValidationError):
            FormatPiece.model_validate({**base, "files": bad})


def test_only_a_piece_folder_beside_a_piece_declaration_is_code(tmp_path):
    """Issue 224: any folder named `piece` was treated as code, so a tool's `piece/` (a word a
    tool may well use) would have stopped loading, silently."""
    from comeni_core.declared.layered import _in_source

    _write(tmp_path, "inspectors/formats/fastq/format.yml", FASTQ)
    code = _write(tmp_path, "inspectors/formats/fastq/piece/fastq.py", "x = 1\n")
    data = _write(tmp_path, "tools/acme/piece/types/acme.piece.yml", "declares: vocabulary\n")
    assert _in_source(code, tmp_path)
    assert not _in_source(data, tmp_path)
