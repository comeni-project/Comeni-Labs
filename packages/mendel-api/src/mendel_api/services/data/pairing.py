"""The default reading rule: files paired into samples by name (#466, #511).

Two files whose names differ only in a mate token (`_R1`/`_R2`, `_1`/`_2`, `.R1`/`.R2`, any
case, Illumina's `_001` after it, compression aside) are one sample named by their shared stem;
any other file is a sample of its own, named by its stem. A name met twice is numbered (`a#2`).
Unlike an upload, two files that do not look like mates are two samples: a folder of two
assemblies is two assemblies.
"""

import re

_MATE = re.compile(
    r"^(?P<stem>.+?)(?P<sep>[._])(?P<mate>[Rr]?[12])(?P<tail>_\d+)?(?P<rest>(\.[^.]+)*)$")
"""A mate's name: a stem, `_` or `.`, `R1`/`R2` or `1`/`2` (any case), Illumina's `_001` if
there, then any extension (bcl2fastq names, lowercase, none at all)."""

_COMPRESSED = (".gz", ".bz2", ".zst")


def _mate_key(name: str):
    """What two mates share: stem, separator, `R` or not, Illumina tail, and extension without
    its compression; `None` for a name with no mate token."""
    found = _MATE.match(name)
    if found is None:
        return None
    rest = found["rest"].lower()
    for suffix in _COMPRESSED:
        rest = rest.removesuffix(suffix)
    return (found["stem"], found["sep"], found["mate"][0] in "Rr", found["tail"] or "", rest)


def _mate(name: str) -> str:
    return _MATE.match(name)["mate"][-1]


def stem(name: str) -> str:
    return name.split(".", 1)[0] if "." in name else name


def unique(name: str, taken: set[str]) -> str:
    """`name`, or `name#2`, `name#3`… when it is taken; then taken."""
    found, n = name, 1
    while found in taken:
        n += 1
        found = f"{name}#{n}"
    taken.add(found)
    return found


def pair(names: list[str], taken: set[str] | None = None) -> list[tuple[str, list[int]]]:
    """`names` as samples, in the order they came: each sample's name and the indexes of its
    files, read 1 first. `taken` carries names already used (another folder's)."""
    taken = set() if taken is None else taken
    keyed: dict[tuple, list[int]] = {}
    order: list[tuple] = []
    for index, name in enumerate(names):
        key = _mate_key(name) or ("file", index)
        if key not in keyed:
            keyed[key] = []
            order.append(key)
        keyed[key].append(index)
    samples: list[tuple[str, list[int]]] = []
    for key in order:
        indexes = keyed[key]
        mates = (key[0] != "file" and len(indexes) == 2
                 and {_mate(names[i]) for i in indexes} == {"1", "2"})
        for group in ([sorted(indexes, key=lambda i: _mate(names[i]))] if mates
                      else [[i] for i in indexes]):
            name = key[0] if mates else stem(names[group[0]])
            samples.append((unique(name[:256], taken), group))
    return samples
