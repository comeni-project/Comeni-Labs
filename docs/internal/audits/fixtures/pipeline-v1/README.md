# A `pipeline.yml` written before Plan 1.13

**Do not regenerate this, and do not edit it.** Its entire value is that no current code produced
it. A fixture built by the code under test proves nothing about compatibility, and a current build
with the version field edited by hand proves less than nothing — it looks like evidence.

Built during the 2026-08-14 design audit (stream 1's baseline probe) against `main` at `346eeac`,
from `examples/rnaseq-goal.yml` and the shipped `registry/` — one layer, no overlay, `gate: null`.
`main.nf` and `nextflow.config` are the files it emitted, kept beside it because the
distinction this fixture exists to test is *the artifact's self-digest moved* versus *the
generated files moved*.

## What it is for

Plan 1.13 added one field to the artifact schema (`CallArg.join`). `emitted.from_digest` hashes
the model dump, so **every archived pipeline's self-digest moved** and `MD0213` reported the file
as edited by a human. It was not. Measured against this fixture:

```
recorded from_digest : sha256:2a68a4ac…
recomputed           : sha256:7d443b62…
main.nf          on disk == recorded: True
nextflow.config  on disk == recorded: True
```

The pipeline had not changed. The *reader* had. That asymmetry — self-digest drifts, emitted
files hold — is the whole test, and it is why the emitted files are committed alongside.

Plan 1.14 Task 0 fixes it by stamping `schema_version` beside `from_digest`, so `MD0213` can tell
"you edited this" from "the schema moved; re-emit to restamp, your Nextflow is unaffected".

## When this fixture stops being useful

When `SCHEMA_VERSION` has moved so far that the file no longer parses at all. At that point it
becomes a *migration* test rather than a diagnostic test, and it should be kept for that — the
question "can we still read what a laboratory archived" does not expire. Add a newer fixture
beside it rather than replacing this one.
