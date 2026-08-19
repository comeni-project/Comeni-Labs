"""Which parser reads declared data, and what must stay true whichever one it is.

A31 is why `yaml_strict` exists: `yaml.safe_load` takes the LAST value for a repeated key, and
a contract that reads two ways is a contract whose digest pins what survived parsing rather
than what the file says. Swapping the tokeniser for libyaml is a performance change — measured
at 13.6× per file, and 244ms to 49ms over a whole registry load — and it must not touch that.
"""

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
    """13.6× per file on this machine. If PyYAML was built without libyaml the fallback is
    correct and this says so rather than failing — the point is that the fast path is taken
    when it exists, not that it must exist."""
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
    """Not a performance test — an equivalence one.

    53 files were compared while auditing (A134); this keeps it true rather than remembering
    it. If the two parsers ever disagreed about a declared file, the fast one would be
    changing what the registry says, which is a correctness bug wearing a performance costume.
    """
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
