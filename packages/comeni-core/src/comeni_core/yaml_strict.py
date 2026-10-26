"""Parse declared YAML with safe constructors and duplicate-key rejection.

PyYAML normally keeps the last occurrence of a repeated mapping key. Declared and digested data
must have one unambiguous reading, so this loader rejects duplicates with both source lines. It
uses ``CSafeLoader`` when available and the behaviorally equivalent Python ``SafeLoader``
otherwise.
"""

from pathlib import Path
from typing import Any

import yaml

try:  # libyaml, when PyYAML was built against it
    from yaml import CSafeLoader as _Base
except ImportError:  # pure Python — identical behaviour, and the only difference is speed
    from yaml import SafeLoader as _Base


class DuplicateKeyError(ValueError):
    """A mapping declares the same key twice, so the file reads two ways."""


class _StrictLoader(_Base):  # type: ignore[misc,valid-type]
    """`SafeLoader`'s behaviour, refusing a repeated key rather than taking the last one.

    The duplicate-key check is `_construct_mapping` below, which is Python on both paths, and
    the line numbers it quotes come from `start_mark`, which both parsers set. That is why the
    faster base changes nothing a reader of this file cares about.
    """


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False):
    seen: dict[Any, int] = {}
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        first = seen.get(key)
        if first is not None:
            raise DuplicateKeyError(
                f"{key!r} is declared twice, at line {first} and line "
                f"{key_node.start_mark.line + 1}. A declared file reads one way: "
                f"`yaml.safe_load` would take the second silently, and the digest that "
                f"pins this file would pin what survived parsing rather than what it says."
            )
        seen[key] = key_node.start_mark.line + 1
    return _Base.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load(path: Path) -> Any:
    """Parse one declared file. Raises `DuplicateKeyError` naming the file and both lines."""
    try:
        return loads(path.read_text())
    except DuplicateKeyError as error:
        raise DuplicateKeyError(f"{path}: {error}") from None


def loads(text: str) -> Any:
    """Strictly parse YAML text supplied by a caller; I/O remains outside this module."""
    return yaml.load(text, Loader=_StrictLoader)  # noqa: S506 — strict subclass
