# mendel-forge

Scaffolding and verification for the registry. A pluggable source ingests a tool into an
`Observation`; a `Scaffold` pairs that with a typed `Hole` for every field the source could not
prove; a `ModuleContract` is constructed only once the last hole is filled.

**`notes/specs/2026-08-16-the-forge.md` is the design.** Read it before changing anything here.

This package is **impure** — it reads tool sources and, from Phase 2, calls a model. The
dependency arrow points `mendel-forge → comeni-core / mendel-resolver / mendel-compiler`, never
the reverse; invariant 1 names those three and this is not one of them.
