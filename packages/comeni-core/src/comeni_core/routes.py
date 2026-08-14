"""Where a resolved value can land in the generated Nextflow.

Three **emission sites**, because those are the three places the compiler writes into. An
earlier draft of the spec claimed three values were exhaustive over *Nextflow's* destinations,
which is false: `task.ext.prefix` appears in 8 of the 10 vendored modules and `task.ext.when` in
all 10. The `ext` scope is a keyspace, not a destination. A claim about our own emitter is
checkable; a claim about Nextflow's surface was a guess, and it was wrong.
"""

from enum import StrEnum


class Via(StrEnum):
    """The emission site. Closed because each one needs its own code in the emitter."""

    EXT = "ext"
    """`process { withName: X { ext.<key> = … } }` — where nf-core modules read arguments."""
    META = "meta"
    """`channel.map { meta + [k: v], files }` — where a module reads a fact about the sample."""
    DIRECTIVE = "directive"
    """`process { withName: X { cpus = 12 } }` — resources and execution."""


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

    **There is no default, and that absence is the finding.** `emit` combined
    unconditionally, which is correct only while the second channel carries one thing every
    sample is paired against — true of the shipped spine, where the second port is a single
    GTF, and false of BAM + BAI, tumour + matched normal, or reads plus a per-sample adapter
    file. `.combine()` is a Cartesian product: two samples in gave four processes, half of
    them pairing one sample's data with another's, and Nextflow exited 0. `--gate test` is
    structurally blind to it because the nf-core test dataset has one sample. Audit A92.
    """

    BROADCAST = "broadcast"
    """`.combine()` — the later ports are one thing every sample is paired against."""
    BY_SAMPLE = "by_sample"
    """`.join()` — the later ports are per-sample and match on the meta map."""
