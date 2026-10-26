"""Equivalent strict-YAML behavior across the C and pure-Python parser bases."""

from pathlib import Path

import pytest
import yaml
from comeni_core import yaml_strict
from comeni_core.yaml_strict import DuplicateKeyError

DUPLICATE = "declares: contract\npriority: 0\npriority: 999\n"


def _loader(base):
    """The strict loader, rebuilt on a chosen base, so both can be compared."""

    class Rebuilt(base):
        pass

    Rebuilt.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, yaml_strict._construct_mapping
    )
    return Rebuilt


def test_the_fast_parser_is_used_when_libyaml_is_available():
    """Use the faster base when installed, while allowing the supported fallback."""
    if not hasattr(yaml, "CSafeLoader"):
        pytest.skip("PyYAML built without libyaml; the pure-Python fallback is what runs")
    assert issubclass(yaml_strict._StrictLoader, yaml.CSafeLoader)


def test_a_repeated_key_is_still_refused(tmp_path):
    """The whole point of the module, under whichever base is active."""
    path = tmp_path / "thing.yml"
    path.write_text(DUPLICATE)
    with pytest.raises(DuplicateKeyError) as raised:
        yaml_strict.load(path)
    assert "priority" in str(raised.value)


def test_the_refusal_still_names_both_lines(tmp_path):
    """The line numbers come from `start_mark`, which is the C parser's on the fast path. A
    swap that kept the refusal and lost the lines would pass the test above and still leave
    the message useless — so the lines are asserted separately."""
    path = tmp_path / "thing.yml"
    path.write_text(DUPLICATE)
    with pytest.raises(DuplicateKeyError) as raised:
        yaml_strict.load(path)
    assert "line 2" in str(raised.value)
    assert "line 3" in str(raised.value)


def test_both_bases_parse_the_shipped_declared_data_identically():
    """The optimization must not change the meaning of shipped declared data."""
    if not hasattr(yaml, "CSafeLoader"):
        pytest.skip("only one parser is available")

    root = Path(__file__).resolve().parents[3]
    files = sorted(root.joinpath("registry").rglob("*.yml"))
    files.append(root / "packages/comeni-core/src/comeni_core/diagnostics.yml")
    assert len(files) > 30, f"the scan found {len(files)} files — it is not scanning"

    slow, fast = _loader(yaml.SafeLoader), _loader(yaml.CSafeLoader)
    for path in files:
        text = path.read_text()
        assert yaml.load(text, Loader=slow) == yaml.load(text, Loader=fast), path
