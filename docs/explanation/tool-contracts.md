# Tool contracts and semantic states

## Executable modules and declared meaning

A Nextflow module is executable code. A contract is the meaning Comeni needs before it can place
that module in a pipeline.

For example, nf-core metadata can say a process emits a `*.bam` file. That is not enough for a
builder. The next step may need a coordinate-sorted BAM, an unsorted BAM, or a BAM plus an
index. A contract makes the implicit sentence explicit:

```text
SAMTOOLS_SORT consumes alignment.bam
SAMTOOLS_SORT produces alignment.bam::coordinate_sorted
```

Once that sentence is true and checked, Comeni can reuse it anywhere a future analysis needs a
coordinate-sorted BAM.

## Before and after

Before the contract exists, the builder has no reliable way to place the tool. It may know the
tool exists as source code, but it cannot safely answer the routing questions:

| Question | Without a contract | With a contract |
|---|---|---|
| Can this tool consume my upstream output? | unknown | checked against input ports |
| Can this tool produce what the next step needs? | unknown | checked against output types and states |
| How should Nextflow call it? | unknown | declared by process name, include path, and inputs |
| Why is a default parameter acceptable? | hidden or manual | recorded beside the parameter |

After the contract lands, the tool becomes a candidate. It still does not appear everywhere; it
appears only where its declared inputs and outputs fit the pipeline being built.

## Semantic states

`state` is the semantic overlay, and it is what `nf-core`'s `meta.yml` does not give you.
Upstream, `samtools/sort`'s output and `star/align`'s `bam_unsorted` are both
`type: file, pattern: "*.bam"` — identical. "Sorted" exists only in an English
description, so a router reading `meta.yml` cannot tell them apart.

Declaring `state: [coordinate_sorted]` supplies the semantic information routing needs.
Derivable module details still need to agree with source; states and roles require
scientific judgment.

States are **closed**: every one must be declared in that type's vocabulary file, or the
contract fails to load. A typo is an error at load time rather than a module that
mysteriously never gets picked.

```yaml
# <layer>/types/alignment.bam.yml
declares: vocabulary
id: alignment.bam
states: [coordinate_sorted, name_sorted, deduplicated, filtered, indexed]
```

For instructions, see [Add a tool](../how-to/registry/add-tool.md).
