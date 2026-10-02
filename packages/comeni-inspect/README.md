# comeni-inspect

**Measure the first few megabytes of a sequencing file and get back facts you can check**: the
read length, whether the reads are paired, how the qualities are encoded. Each fact comes with
what it was measured on (how many reads, what share agreed), or with the reason it could not be
decided, never with a guess.

An inspection is composed from small pieces kept in the registry: a codec opens the bytes
(`gzip`), a format reads records (`fastq`), and each measure folds those records into one fact.
This package is what every piece is written against: the record shape, the accumulator a measure
implements, the runner that feeds one streamed pass to every measure, and the harness that holds
a piece to its golden reports.

One inspection runs per process: a request goes in on stdin, one JSON report comes out on
stdout. [`PROTOCOL.md`](PROTOCOL.md) describes both, so a faster implementation in another
language can take a piece's place and be checked against the same reports.
