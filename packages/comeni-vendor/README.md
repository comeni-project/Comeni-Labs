# comeni-vendor

Put a tool's source into a registry layer, and tell you when it stops matching its pin.

```bash
comeni-vendor add nf-core:star/align \
  --sha 6d46786420b4d7bc88eba026eb389c0c5535d120 \
  --licence MIT \
  --registry ../comeni-registry

comeni-vendor check --registry ../comeni-registry              # offline: was it hand-edited?
comeni-vendor check --registry ../comeni-registry --upstream   # online: does it match the pin?
```

`add` writes two things beside each other:

```
tools/nf-core/star/align/
    module.yml     where the code came from, at which commit, under which licence
    module/        upstream's tree. Never hand-edited — comeni-vendor replaces it wholesale
```

## Why this is not `mendel vendor`

`mendel` is `mendel_compiler.cli:main`, and `mendel-compiler` is one of the four packages
invariant 1 keeps off the network — `tests/test_purity.py` rejects the imports outright. A
subcommand that fetches from GitHub could not live there, and it should not *look* as though it
could: this tool is not part of the deterministic build path, and a verb spelled `mendel …`
reads as though it is.

**Nothing else fetches.** A build reads a layer that is already on disk, which is what keeps
`make check` offline and an air-gapped site a first-class customer (invariant 13).

## The two checks are different questions

- `check` is **offline**. It recomputes each `module/`'s digest and compares it to the one
  `module.yml` records — the question about a **hand-edit**. It runs in `comeni-registry`'s CI,
  which is what makes *do not hand-edit this* enforceable rather than a comment somebody reads
  after they have already edited it.
- `check --upstream` re-fetches at the pin and compares — the question about a bad `add`.

A module declaring `upstream: null` is a laboratory's own process. It reports `unpinned` rather
than `ok`: there is nothing to compare it against, and reporting a pass would be claiming a
check that never ran — the same reason `MD0100` marks a contract `unverified` rather than
trusting it.
