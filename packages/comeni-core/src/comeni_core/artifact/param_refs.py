"""Extract parameter references from channel expressions.

Used when building and validating a channel's parameter list, and when
checking vocabulary templates for hardcoded parameter names.
"""

_IDENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "_"
)


def extract_param_refs(expression: str) -> list[str]:
    """Return sorted, unique names found after literal ``params.`` occurrences.

    Names consist of ASCII letters, digits, and underscores. This scans text;
    it does not parse Groovy syntax or distinguish code from strings and comments.
    """
    found: set[str] = set()
    marker = "params."
    start = expression.find(marker)
    while start != -1:
        cursor = start + len(marker)
        end = cursor
        while end < len(expression) and expression[end] in _IDENT_CHARS:
            end += 1
        if end > cursor:
            found.add(expression[cursor:end])
        start = expression.find(marker, end)
    return sorted(found)
