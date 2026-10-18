# What the example builds

`main.nf` as `mendel build` emitted it for the example analysis at `a8425c4d`, before
`pipeline.yml` version 7 (Part I.0 Plan B). Version 7 changed how the file says what was wanted
and known, not what runs: building `examples/rnaseq.yml` must still emit this, byte for byte
(invariant 10). Regenerate it only when emission is meant to change, and say why in the commit.
