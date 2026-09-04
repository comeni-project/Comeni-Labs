# comeni-ai

Model access for Comeni Labs. One primitive — `generate(instruction, shape, evidence)` — which
validates model output against a declared Pydantic shape before returning it. `choose_one` and
`choose_many` are helpers over it for closed choices, `converse` is the same validation over a
multi-turn exchange, and `PromptTemplate` is how a caller's committed prompt files are loaded,
rendered and identified by version.

There is no free-text generation call, and that is a design position rather than an omission:
what a model returns is checked against a declaration before any caller sees it. See
[the spec](../../docs/notes/specs/2026-08-17-forge-phase-2.md) §4, and §4.3.1 for what that guard is
and is not — it is cost-raising, not a proof.

**This package holds no domain types.** It speaks in strings and shapes its caller declares.
Mendel contracts, roles and Nextflow instructions belong to the caller that owns them; a
shared transport that accumulates every agent's prompts is a shared pile, not a boundary.
It was `mendel-ai` until 2026-09-04, and was renamed when a second consumer appeared — the
Forge, the builder and Wiener's agents would otherwise have grown three clients.

Impure by design: this is where the network lives. `comeni-core`, `mendel-resolver`,
`mendel-compiler` and `wiener-core` do not reach it, and `tests/guards/test_purity.py` holds
that direction.
