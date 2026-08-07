"""One loader, and a declared file reads exactly one way.

A31: `yaml.safe_load` takes the **last** value for a repeated key, silently. A contract
with two `priority:` lines loads at the second one, and the digest pins what survived
parsing rather than what the file says — which is A10's argument, one level down: a key
that is quietly dropped is a key that can be misspelled, or *added*, in silence.

The registry is data a stranger distributes and a lockfile pins by digest. A reviewer
reading `priority: 0` at the top of a file and a build routing on `priority: 999` from the
bottom is the whole of what a signed layer is supposed to prevent.

`yaml.safe_load` stays the mechanism — this narrows it rather than replacing it. Every
loader in the pure packages goes through here, so "which files are read strictly" has one
answer instead of seven.
"""

from pathlib import Path
from typing import Any

import yaml


class DuplicateKeyError(ValueError):
    """A mapping declares the same key twice, so the file reads two ways."""


class _StrictLoader(yaml.SafeLoader):
    """`SafeLoader`, refusing a repeated key rather than taking the last one."""


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
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load(path: Path) -> Any:
    """Parse one declared file. Raises `DuplicateKeyError` naming the file and both lines."""
    try:
        return yaml.load(path.read_text(), Loader=_StrictLoader)  # noqa: S506 — strict subclass
    except DuplicateKeyError as error:
        raise DuplicateKeyError(f"{path}: {error}") from None
