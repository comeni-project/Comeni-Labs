import pytest
from comeni_core.measurement import (
    BadMeasurementValueError,
    MeasurementKind,
    MeasurementRegistry,
    UnknownMeasurementError,
)


def _layer(root, name, files):
    d = root / name
    d.mkdir(parents=True)
    for filename, body in files.items():
        (d / filename).write_text(body)
    return d


READ_LENGTH = """
kind: integer
minimum: 1
unit: bp
description: "Sequenced read length"
"""

STRANDEDNESS = """
kind: enum
values: [forward, reverse, unstranded]
description: "Library strandedness"
cite: "Signal et al. 2022, doi:10.1186/s12859-022-04572-7"
"""

ORGANISM = """
kind: enum
extensible: true
values: [homo_sapiens, mus_musculus]
description: "Source organism"
"""


@pytest.fixture
def base(tmp_path):
    return _layer(
        tmp_path,
        "base",
        {
            "read_length.yml": READ_LENGTH,
            "strandedness.yml": STRANDEDNESS,
            "organism.yml": ORGANISM,
        },
    )


def test_a_declaration_is_loaded_by_filename(base):
    registry = MeasurementRegistry.load(base)
    assert registry.get("read_length").kind is MeasurementKind.INTEGER
    assert registry.get("read_length").unit == "bp"


def test_an_enum_accepts_only_its_declared_values(base):
    registry = MeasurementRegistry.load(base)
    registry.check("strandedness", "reverse")
    with pytest.raises(BadMeasurementValueError, match="sideways"):
        registry.check("strandedness", "sideways")


def test_an_integer_respects_its_bounds(base):
    registry = MeasurementRegistry.load(base)
    registry.check("read_length", 150)
    with pytest.raises(BadMeasurementValueError, match="minimum"):
        registry.check("read_length", 0)


def test_a_wrong_type_is_refused(base):
    registry = MeasurementRegistry.load(base)
    with pytest.raises(BadMeasurementValueError):
        registry.check("read_length", "one hundred and fifty")


def test_an_undeclared_measurement_says_what_exists(base):
    registry = MeasurementRegistry.load(base)
    with pytest.raises(UnknownMeasurementError) as exc:
        registry.check("organsim", "homo_sapiens")
    message = str(exc.value)
    assert "organsim" in message
    assert "read_length" in message and "strandedness" in message


def test_there_is_no_string_kind(tmp_path):
    """A free-text measurement is the hole the egress guard exists to close."""
    layer = _layer(tmp_path, "bad", {"note.yml": "kind: string\ndescription: x\n"})
    with pytest.raises(ValueError, match="string"):
        MeasurementRegistry.load(layer)


def test_a_closed_enum_refuses_added_values(tmp_path, base):
    overlay = _layer(tmp_path, "lab", {"strandedness.yml": "add_values: [sideways]\n"})
    with pytest.raises(ValueError, match="not extensible"):
        MeasurementRegistry.load([base, overlay])


def test_an_extensible_enum_takes_the_union(tmp_path, base):
    overlay = _layer(tmp_path, "lab", {"organism.yml": "add_values: [ambystoma_mexicanum]\n"})
    registry = MeasurementRegistry.load([base, overlay])
    registry.check("organism", "ambystoma_mexicanum")
    registry.check("organism", "homo_sapiens")


def test_a_deprecated_measurement_names_its_replacement(tmp_path):
    layer = _layer(
        tmp_path,
        "d",
        {
            "read_length.yml": "kind: integer\ndeprecated: true\n"
            "replaced_by: read_length_median\ndescription: ambiguous\n",
            "read_length_median.yml": "kind: integer\ndescription: median\n",
        },
    )
    registry = MeasurementRegistry.load(layer)
    assert registry.get("read_length").deprecated is True
    assert registry.get("read_length").replaced_by == "read_length_median"
