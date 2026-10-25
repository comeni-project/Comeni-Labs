"""Supported Nextflow process directives and their source toolchain version.

Nextflow silently ignores unknown directives in a ``withName`` block, so parameter validation
uses this allowlist to prevent misspelled resource settings from becoming no-ops. The set is a
toolchain fact, not registry-owned biological vocabulary, and changes with Nextflow releases.
"""

NEXTFLOW_VERSION = "25.10.4"
"""The Nextflow version against which :data:`LEGAL_DIRECTIVES` was checked."""

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
