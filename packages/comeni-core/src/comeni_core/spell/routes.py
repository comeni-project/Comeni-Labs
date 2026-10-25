"""Closed routes from resolved values to generated Nextflow emission sites."""

from enum import StrEnum


class Via(StrEnum):
    """The emission site. Closed because each one needs its own code in the emitter."""

    EXT = "ext"
    """`process { withName: X { ext.<key> = … } }` — where nf-core modules read arguments."""
    META = "meta"
    """`channel.map { meta + [k: v], files }` — where a module reads a fact about the sample."""
    DIRECTIVE = "directive"
    """`process { withName: X { cpus = 12 } }` — resources and execution."""
    POSITIONAL = "positional"
    """A bare `val` in the module's input block — a value with **no name** at the call site.

    Used by modules whose call has an unnamed scalar slot. The slot is declared by
    `NfInput.param`; this enum identifies only the emission route.
    """


OMITTABLE: frozenset[Via] = frozenset({Via.EXT, Via.DIRECTIVE})
"""Routes on which an unanswered setting is optional and the tool default applies.

`POSITIONAL` is not here because an empty call slot reads `null` and Nextflow fails at launch.
Nor is `META`, although the emitter omits it too: a module reading `meta.<name>` gets `null`, and
what it does then is the module's business, not a default anyone documented.
"""


class ExtKey(StrEnum):
    """Which key inside the `ext` scope.

    `args` is read by all 10 vendored modules and `prefix` by 8. `args2` and `args3` are here on
    **nf-core convention with no evidence in this repository** — no vendored module reads them.
    Kept because an unused enum value costs nothing while adding one later costs a `version:`
    bump for every archived `pipeline.yml`, and `MD0108` refuses a contract naming a key its
    module does not read, so a wrong inclusion fails loudly at build rather than silently at run.

    **`when` is deliberately absent.** It is a boolean that skips a process entirely, so a
    setting could switch off a step while `steps:` and `inputs:` still describe it running —
    a second routing mechanism competing with resolution. Whether a step exists is decided by
    resolving the goal, not by a setting.
    """

    ARGS = "args"
    ARGS2 = "args2"
    ARGS3 = "args3"
    PREFIX = "prefix"


TEMPLATED: frozenset[ExtKey] = frozenset({ExtKey.ARGS, ExtKey.ARGS2, ExtKey.ARGS3})
"""The keys whose value composes into an argument string, and so take a `template`.

`prefix` names output files and takes one typed value; a directive likewise. `cpus =
"--cpus 12"` is not a thing, which is why a template on those routes is refused rather than
ignored.
"""


class Join(StrEnum):
    """How two channels filling one process input are matched.

    Closed for the same reason `Via` is: each member needs its own line in the emitter.

    There is no default because broadcast and per-sample pairing have different cardinality.
    `.combine()` is a Cartesian product, while `.join()` pairs matching sample metadata.
    """

    BROADCAST = "broadcast"
    """`.combine()` — the later ports are one thing every sample is paired against."""
    BY_SAMPLE = "by_sample"
    """`.join()` — the later ports are per-sample and match on the meta map."""
