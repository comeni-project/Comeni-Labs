The **channel name** for this port — the label the compiler reads as `PROCESS.out.<name>`.

This is not the semantic type, and it is not a description. It is the identifier the emitted
Nextflow will use, and it must match the module's own named emit exactly. Take it from the
process source when there is one; a mismatch is a pipeline that fails at include time with an
error naming neither the contract nor the tool.

Where the module names nothing — a single unnamed output — use the short, lowercase form of what
the port carries: `bam`, `reads`, `html`, `versions`. Keep it stable: this name is what a
pipeline refers to, so changing it later breaks every pipeline that used it.
