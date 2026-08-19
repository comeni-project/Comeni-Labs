"""One loader, and a declared file reads exactly one way.

A31: `yaml.safe_load` takes the **last** value for a repeated key, silently. A contract
with two `priority:` lines loads at the second one, and the digest pins what survived
parsing rather than what the file says — which is A10's argument, one level down: a key
that is quietly dropped is a key that can be misspelled, or *added*, in silence.

The registry is data a stranger distributes and a lockfile pins by digest. A reviewer
reading `priority: 0` at the top of a file and a build routing on `priority: 999` from the
bottom is the whole of what a signed layer is supposed to prevent.

`SafeLoader`'s **constructor set** stays the mechanism — this narrows it rather than replacing
it. Every loader in the pure packages goes through here, so "which files are read strictly"
has one answer instead of seven.

**The tokeniser is libyaml's where PyYAML was built against it**, which is a performance change
and not a semantic one: what makes `SafeLoader` safe is which constructors it will run, and
that set is identical on both paths. Measured at **13.6× per file**, taking a whole registry
load from 244ms to 49ms (audit A134), and 53 declared files were compared under the two
parsers before the swap.
"""

from pathlib import Path
from typing import Any

import yaml

try:  # libyaml, when PyYAML was built against it
    from yaml import CSafeLoader as _Base
except ImportError:  # pure Python — identical behaviour, and the only difference is speed
    from yaml import SafeLoader as _Base

    # **The fallback is not decoration.** PyYAML installs without libyaml, and a module that
    # raised `ImportError` there would trade a performance problem for an availability one.


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
        return yaml.load(path.read_text(), Loader=_StrictLoader)  # noqa: S506 — strict subclass
    except DuplicateKeyError as error:
        raise DuplicateKeyError(f"{path}: {error}") from None
