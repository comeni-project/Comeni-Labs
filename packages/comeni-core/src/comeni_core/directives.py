"""The process directives Nextflow accepts, and the version they were read against.

**An unknown directive in a `withName` block is silently ignored.** Measured, not assumed: a
config containing `process { withName: FOO { cpuz = 4 } }` runs to exit 0 with no error and no
warning on Nextflow 25.10.4. So this list is the only thing standing between a typo and a
resource setting that does nothing — which is the exact failure `via: directive` would otherwise
install, in a design whose whole purpose is removing settings that reach nothing.

**Code rather than registry data.** `Vocabulary` is strictly per-type and a directive list is not
a type; putting it in a layer would mean a fifth member beside `contracts/`, `rules/`,
`vocabularies/` and `measurements/`, which is exactly what root B narrowed. And the invariant-7
analogy does not hold: vocabularies are closed because a contract using an undeclared *biological*
state must fail, and new states arrive through the forge as reviewed domain knowledge. Nextflow's
directive set is a fact about the toolchain — it moves on Nextflow's release cycle, and no
laboratory should be able to approve `cpuz` into it. `modulespec.py` encodes toolchain facts the
same way.
"""

NEXTFLOW_VERSION = "25.10.4"
"""The Nextflow this list was read against — the version pinned in `CLAUDE.md`'s toolchain.

A newer Nextflow may accept more. Adding one is a release of this package, which is the price of
the check and is why the version is recorded rather than implied.
"""

LEGAL_DIRECTIVES: frozenset[str] = frozenset(
    {
        "accelerator",
        "afterScript",
        "arch",
        "array",
        "beforeScript",
        "cache",
        "clusterOptions",
        "conda",
        "container",
        "containerOptions",
        "cpus",
        "debug",
        "disk",
        "errorStrategy",
        "executor",
        "fair",
        "label",
        "machineType",
        "maxErrors",
        "maxForks",
        "maxRetries",
        "maxSubmitAwait",
        "memory",
        "module",
        "penv",
        "pod",
        "publishDir",
        "queue",
        "resourceLabels",
        "resourceLimits",
        "scratch",
        "secret",
        "shell",
        "spack",
        "stageInMode",
        "stageOutMode",
        "storeDir",
        "tag",
        "time",
    }
)
"""Process directives, from the Nextflow documentation for `NEXTFLOW_VERSION`.

**`ext` is deliberately absent.** `via: ext` owns that scope, and a setting must not be able to
reach it by two routes — two writers for one destination, forbidden at the source rather than
caught downstream.

Deprecated directives (`echo`, `validExitStatus`) are absent too: a check that permits what
Nextflow itself warns about is not doing its job.
"""
