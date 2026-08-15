"""What a `pipeline.yml` must satisfy to be read back. Helpers for the `MD0200` band.

These answer a different question from the models beside them: a `Step` says what a step *is*,
and this says what a step somebody hand-edited must still be. The pydantic validators stay on
their models — a validator cannot move off the class it validates — and everything they call
lives here, which is where the refusals a reader actually meets are written.

`_param_refs` is used by `Channel`'s validator **and** by materialisation, which is the reason
it is here rather than in `materialise.py`: the two must agree about what a parameter reference
is, and one function is how they cannot disagree. `MD0211` exists because `params:` and
`expression:` are stated twice in the artifact and had to be checked against each other on every
load rather than only where they were written together.
"""

_IDENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "_"
)


def _param_refs(expression: str) -> list[str]:
    """Every `params.<name>` an entry-channel expression references, sorted and deduplicated.

    Scanned by hand rather than with `re`, which is not on `comeni-core`'s purity allowlist —
    `_is_identifier` refused to widen it for a character class and this is the same trade.
    `mendel_compiler.emit.entry_params` does the same job with a regex because that package
    already allows one; the two must agree, which is what `MD0211` checks.

    Plural because one expression may reference several: `fastq.reads` names `params.input`
    three times today, and the shipped registry being 1:1 is not a schema guarantee.
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


