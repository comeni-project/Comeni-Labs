# mendel-authoring

The conversation that turns a plain-language description into a goal, declared as one diagram
of sections, steps and arrows, and the interpreter that runs it: a session's legal moves are
read off the diagram, so changing the flow means changing the diagram.

It is pure: it depends on `comeni-core` and `pydantic` only, and reaches no network, database or
model. The design is in `docs/superpowers/specs/2026-10-04-the-consultant-build-design.md`.
