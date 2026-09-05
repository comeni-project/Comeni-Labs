Nextflow DSL2. The process name is uppercase with underscores and matches the tool and its
subcommand — `CLUSTALW_ALIGN`, `SAMTOOLS_SORT`.

Flags come from `task.ext.args`, never hard-coded. Output filenames use `task.ext.prefix` where
the tool produces one file per sample. Named emits match the contract's output port names exactly
— that name is what the compiler reads as `PROCESS.out.<name>`.

The stub block must create every file shape the process declares. It is how the whole pipeline is
validated in seconds, and one that omits an output breaks the process downstream of it in a way
that reads as an infrastructure fault.
