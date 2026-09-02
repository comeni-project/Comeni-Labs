# mendel-ai

Model access for Mendel. One primitive — `generate(instruction, shape, evidence)` — which
validates model output against a declared Pydantic shape before returning it. `choose_one` and
`choose_many` are helpers over it for closed choices.

There is no free-text generation call, and that is a design position rather than an omission:
what a model returns is checked against a declaration before any caller sees it. See
[the spec](../../docs/notes/specs/2026-08-17-forge-phase-2.md) §4, and §4.3.1 for what that guard is
and is not — it is cost-raising, not a proof.

Impure by design: this is where the network lives. `comeni-core`, `mendel-resolver` and
`mendel-compiler` do not reach it, and `tests/test_purity.py` holds that direction.
