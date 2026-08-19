"""How many times loading a registry reads each file.

**Counted, never timed.** A test asserting *"the load takes under 30ms"* fails on a busy CI
runner and teaches everyone to re-run rather than to look. The redundancy phase 7 removed is
exactly countable, so the guard counts.

The numbers the audit measured before the fix, for anyone reading a failure here: the layer was
walked **5 times** — once per `DeclaredKind` — each file was bucketed **5.6 times**, and the
shipped registry took **217 parses for 39 files** (A133, A143).

These reach `layered._files` and `MANIFEST`, which are private. That is the price of not
writing a timing assertion, and it is the cheaper of the two.
"""

from collections import Counter
from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.declared import layered
from mendel_resolver import layers

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry"


def _declared_files() -> list[Path]:
    return [p for p in layered._files(REGISTRY) if p != REGISTRY / layered.MANIFEST]


def test_the_scan_reaches_something():
    """Every count below is a ratio against this. If the registry ever stopped being found,
    `0 == 0` would make all three pass while measuring nothing."""
    assert len(_declared_files()) > 30


def test_the_layer_is_walked_once_per_load(monkeypatch):
    """Not once per `DeclaredKind`. Five kinds meant five walks, and the `pathlib` cost of the
    four extra ones dominated the profile once the parser was fixed (A143)."""
    walks: list[Path] = []
    real = layered._files
    monkeypatch.setattr(layered, "_files", lambda path: (walks.append(path), real(path))[1])

    layers.load(REGISTRY)

    assert len(walks) == 1, f"the layer was walked {len(walks)} times"


def test_declared_kind_is_asked_once_per_file(monkeypatch):
    """The bucketing question has one answer per file per load, and it used to be asked once
    per file **per kind**."""
    asked: list[Path] = []
    real = layered.declared_kind
    monkeypatch.setattr(
        layered, "declared_kind", lambda path: (asked.append(path), real(path))[1]
    )

    layers.load(REGISTRY)

    assert len(asked) == len(_declared_files())
    assert len(set(asked)) == len(asked), "a file was bucketed more than once"


def test_no_declared_file_is_parsed_more_than_twice(monkeypatch):
    """A **ceiling**, not a target — asserted so the refactor that would reach one parse stays
    visibly refused rather than quietly forgotten.

    Two: once to bucket the file, once by the `Kind` that claimed it. Getting to one means
    changing `Kind.parse` to accept pre-parsed data across five kinds, threading `(path, data)`
    through `ModuleContract.load` and its coded errors. Measured worth: about 6ms. Spec §3.3.

    **Per file rather than in total**, which is a correction this test made to itself: a total
    of `2 × files` looks equivalent and is not, because `registry.yml` is read once by
    `layer_name` and is not a declared file. Counting per file says what is meant and does not
    need the manifest as a fudge term.
    """
    parsed: list[Path] = []
    real = yaml_strict.load

    def counting(path):
        parsed.append(path)
        return real(path)

    monkeypatch.setattr(yaml_strict, "load", counting)
    monkeypatch.setattr(layered.yaml_strict, "load", counting)

    layers.load(REGISTRY)

    seen = Counter(parsed)
    assert seen, "nothing was parsed — the instrument is not attached"
    over = {str(path): n for path, n in seen.items() if n > 2}
    assert over == {}, f"parsed more than twice: {over}"


def test_the_manifest_is_read_once(monkeypatch):
    """`registry.yml` is the layer's account of itself, read by `layer_name` before any kind
    runs. It is not a declared file, and it is the reason the test above counts per file."""
    parsed: list[Path] = []
    real = yaml_strict.load

    def counting(path):
        parsed.append(path)
        return real(path)

    monkeypatch.setattr(yaml_strict, "load", counting)
    monkeypatch.setattr(layered.yaml_strict, "load", counting)

    layers.load(REGISTRY)

    assert Counter(parsed)[REGISTRY / layered.MANIFEST] == 1
