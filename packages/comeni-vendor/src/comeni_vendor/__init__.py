"""Put a tool's source into a registry layer, and tell you when it stops matching its pin.

**This is not `mendel vendor`, and the name is the point.** `mendel` is
`mendel_compiler.cli:main`, and `mendel-compiler` is one of the four packages invariant 1
keeps off the network — `tests/test_purity.py` rejects the imports outright. A subcommand that
fetches from GitHub could not live there, and it should not *look* as though it could: this
tool is not part of the deterministic build path, and a verb spelled `mendel …` reads as
though it is.

**Nothing else fetches.** A build reads a layer that is already on disk, which is what keeps
`make check` offline and an air-gapped site a first-class customer (invariant 13). Vendoring is
something a maintainer does, once, before the layer is committed — the same shape as
`uvx nf-core modules install`, which is what this replaces.

Two verbs:

- `comeni-vendor add nf-core:star/align --sha <sha> --registry ../comeni-registry` fetches the
  module at that commit, writes `module/` and the `module.yml` beside it, and applies
  `excluded:` so the copy is only what we said we would take.
- `comeni-vendor check --registry ../comeni-registry` asks whether every `module/` still
  matches its `upstream:` pin. This is what makes *do not hand-edit this* enforceable rather
  than a comment somebody reads after they have already edited it (spec §8.4).

A module declaring `upstream: null` is a laboratory's own process. `check` **skips it and says
so**: there is nothing to compare it against, and reporting that as a pass would be claiming a
check that never ran.
"""

from comeni_vendor.ops import CheckResult, add, check

__all__ = ["CheckResult", "add", "check"]
