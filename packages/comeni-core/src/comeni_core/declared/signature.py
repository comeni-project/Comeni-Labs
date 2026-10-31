"""`qc.report::assembly`: how a type and its states are written.

The states narrow the type: a reader of `qc.report` accepts `qc.report::assembly`, and a reader
of `qc.report::assembly` accepts nothing plainer. States are a set, so `join` sorts them and one
set has one spelling. Matching works on the parsed parts, so it never sees this notation.
"""

SEPARATOR = "::"


def split(signature: str) -> tuple[str, frozenset[str]]:
    """`alignment.bam::coordinate_sorted` to its type and states."""
    type_id, *states = signature.split(SEPARATOR)
    if not type_id or not all(states):
        raise ValueError(f"{signature!r} has an empty part: write `type::state`")
    return type_id, frozenset(states)


def join(type_id: str, states: frozenset[str]) -> str:
    """The one spelling of a type and states."""
    return SEPARATOR.join([type_id, *sorted(states)])


def states_in_type(data: object, field: str) -> object:
    """A model's input with `type_id: alignment.bam::indexed` parted into the type and `field`."""
    if not isinstance(data, dict) or SEPARATOR not in str(data.get("type_id", "")):
        return data
    if data.get(field):
        raise ValueError(f"{data['type_id']!r} writes states both in the type and in `{field}`")
    type_id, states = split(data["type_id"])
    return {**data, "type_id": type_id, field: sorted(states)}
