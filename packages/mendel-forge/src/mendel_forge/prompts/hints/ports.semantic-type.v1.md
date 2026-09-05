The semantic type of a port: what the data *is*, independent of how it is stored and of what this
module's author called the channel.

`fastq.reads` is sequencing reads. `alignment.bam` is aligned reads. `annotation.gtf` is a feature
annotation. The channel carrying it may be called `reads`, `ch_in`, `bam` or `input`, and none of
those is the answer.

Ask what a downstream tool would need to know before consuming this. That is the type.
