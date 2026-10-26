import pathlib

import pytest
from comeni_core.declared.measurement import (
    BadMeasurementValueError,
    MeasurementKind,
    MeasurementRegistry,
    UnknownMeasurementError,
)

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Add an explicit declaration kind and ID to a fixture body, if absent."""
    path = pathlib.Path(path)
    # Fixtures may nest files below their kind directory, so inspect every ancestor.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def _layer(root, name, files):
    """Create and return a layer root containing measurement fixtures."""
    d = root / name / "measurements"
    d.mkdir(parents=True)
    for filename, body in files.items():
        (d / filename).write_text(_declared(d / filename, body))
    return root / name


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


def test_a_number_respects_its_maximum(tmp_path):
    layer = _layer(
        tmp_path,
        "bounded",
        {"gc.yml": "kind: number\nminimum: 0\nmaximum: 1\ndescription: GC fraction\n"},
    )
    registry = MeasurementRegistry.load(layer)

    registry.check("gc", 1)
    with pytest.raises(BadMeasurementValueError, match="maximum"):
        registry.check("gc", 1.01)


def test_a_wrong_type_is_refused(base):
    registry = MeasurementRegistry.load(base)
    with pytest.raises(BadMeasurementValueError):
        registry.check("read_length", "one hundred and fifty")


@pytest.fixture
def every_kind(tmp_path):
    return _layer(
        tmp_path,
        "kinds",
        {
            "read_length.yml": READ_LENGTH,
            "strandedness.yml": STRANDEDNESS,
            "paired.yml": "kind: boolean\ndescription: Paired-end\n",
            "gc.yml": "kind: number\ndescription: GC fraction\n",
        },
    )


@pytest.mark.parametrize(
    ("measurement", "text", "value"),
    [
        ("read_length", "50", 50),
        ("read_length", " 150 ", 150),
        ("gc", "0.42", 0.42),
        ("gc", "1", 1),
        ("paired", "true", True),
        ("paired", "False", False),
        ("strandedness", "reverse", "reverse"),
    ],
)
def test_text_is_read_by_the_declared_kind(every_kind, measurement, text, value):
    """Text from a model is coerced only when it matches the declared kind."""
    registry = MeasurementRegistry.load(every_kind)
    got = registry.coerce(measurement, text)
    assert got == value and type(got) is type(value)
    registry.check(measurement, got)


@pytest.mark.parametrize(
    ("measurement", "text"),
    [("read_length", "fifty"), ("read_length", "50.5"), ("read_length", "50 bp"),
     ("paired", "yes please"), ("gc", ""), ("read_length", "²"), ("gc", "1.2.3")],
)
def test_text_that_is_not_the_kind_is_left_for_check_to_refuse(every_kind, measurement, text):
    registry = MeasurementRegistry.load(every_kind)
    assert registry.coerce(measurement, text) == text
    with pytest.raises(BadMeasurementValueError):
        registry.check(measurement, registry.coerce(measurement, text))


def test_a_value_already_of_its_kind_and_a_list_are_read_element_by_element(every_kind):
    registry = MeasurementRegistry.load(every_kind)
    assert registry.coerce("read_length", 100) == 100
    assert registry.coerce("read_length", ["50", 75]) == [50, 75]


def test_only_a_per_sample_measurement_accepts_a_list(tmp_path):
    layer = _layer(
        tmp_path,
        "cardinality",
        {
            "read_length.yml": "kind: integer\nminimum: 1\nper_sample: true\n",
            "n_samples.yml": "kind: integer\nminimum: 1\n",
        },
    )
    registry = MeasurementRegistry.load(layer)

    registry.check("read_length", [100, 150])
    with pytest.raises(BadMeasurementValueError, match="per_sample"):
        registry.check("n_samples", [2, 3])


@pytest.mark.parametrize(
    "body",
    [
        "kind: boolean\nassertion_only: true\n",
        "kind: boolean\nassertion_only_because: no profiler is available\n",
    ],
)
def test_assertion_only_and_its_reason_must_be_declared_together(tmp_path, body):
    layer = _layer(tmp_path, "asserted", {"paired.yml": body})

    with pytest.raises(ValueError, match="MD0315"):
        MeasurementRegistry.load(layer)


def test_an_undeclared_measurement_says_what_exists(base):
    registry = MeasurementRegistry.load(base)
    with pytest.raises(UnknownMeasurementError) as exc:
        registry.check("organsim", "homo_sapiens")
    message = str(exc.value)
    assert "organsim" in message
    assert "read_length" in message and "strandedness" in message


def test_there_is_no_string_kind(tmp_path):
    """Free text is not a supported measurement kind."""
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


def test_profile_of_keeps_each_entrys_own_source(base):
    """Facts from different sources retain independent provenance."""
    from comeni_core.review.answer import ValueSource

    registry = MeasurementRegistry.load(base)
    profile = registry.profile_of(
        [
            ("strandedness", "reverse", ValueSource.MODEL, None),
            ("read_length", 150, ValueSource.SAID, None),
        ]
    )
    assert [(m.measurement, m.source) for m in profile.measurements] == [
        ("read_length", ValueSource.SAID),
        ("strandedness", ValueSource.MODEL),
    ]


def test_profile_of_validates_like_profile(base):
    from comeni_core.review.answer import ValueSource

    registry = MeasurementRegistry.load(base)
    with pytest.raises(BadMeasurementValueError, match="minimum"):
        registry.profile_of([("read_length", -5, ValueSource.SAID, None)])
