The scientific state of the data on this port — what has been done to it, not what format it is
in.

`coordinate_sorted`, `trimmed`, `deduplicated`, `filtered`. A state is a claim that some
processing step has happened, and routing depends on it: a tool declaring it requires
`[coordinate_sorted]` will not be handed the output of one that does not declare it.

A filename suffix does not establish a state. `.bam` says the container format; whether the
alignment inside it is sorted is a separate fact, and it is usually stated in the command line or
in the tool's own description of what it does.

Claim the smallest set that is true. An unclaimed state costs a rule later; a wrongly claimed one
silently produces wrong pipelines.
