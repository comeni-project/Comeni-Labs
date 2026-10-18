# A version-6 pipeline, as `main` wrote it

Built by `mendel build --goal examples/rnaseq-goal.yml` at `a8425c4d`, the last commit before
version 7 (Part I.0 Plan B), and committed with the `main.nf` that build emitted. Never
regenerate it with today's code: a file written by the code under test cannot show anything about
reading what a laboratory already has. The same goal must still emit this `main.nf`, byte for
byte, and this file must load, upgrade in memory, and re-emit it.
