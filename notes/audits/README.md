# Audits

Independent reviews, and the ledger that records whether the guards they produced actually work.

**[`guard-ledger.md`](guard-ledger.md) is the one to read.** It is append-only, one row per
guard reverted and watched failing, with the message it printed. It exists because of finding
A14 — *a guard never watched failing may be inert rather than merely weak* — which is critical,
open, and closes only when every guard in `tests/` has a recorded revert. `make residue` counts
how far along that is.

Four rounds used revert-and-watch against the code; the 2026-08-14 design audit asked a different
question — does the *design* deliver the product claim — and its four stream reports are its
evidence. `fixtures/` holds frozen inputs an audit refused, kept as the record of what broke.

Round briefs (`*-brief.md`) are the method; round audits (`*-audit.md`) are the findings. Each
finding has an `A`-number, and the numbers never restart.

**[`2026-08-19-performance-audit.md`](2026-08-19-performance-audit.md) asks a third question** —
is the tool *fast enough to use* — against a budget the operator stated in a sentence: half a
second for anything done in a browser, because this is a tool and not a server. Its method is
measurement rather than revert-and-watch, and its most useful result is a **negative** one:
the codebase is not full of inefficiency, it has one slow function that everything calls.
A132–A145, of which A141, A144 and A145 are negative or supporting results and are
recorded on purpose.

**[`2026-08-24-wiener-spec-review.md`](2026-08-24-wiener-spec-review.md) asks a fourth question**
— does a *specification* agree with itself and with the code it claims to build on — against
`docs/design/wiener.md` before Task 1 of its plan. It ran because that document's own journal
entry says *"the spec was reviewed" — it was not*, and it found nine things (A175–A183), three of
them critical: a heartbeat the fold is told it will see and `EventKind` cannot express, an
idempotence claim attributed to the wrong mechanism with a phantom retry waiting behind it, and
a tenancy guard that checks a weaker sentence than the spec states. It has the same limitation the
design audit had — revert-and-watch cannot be run against something with no code — and A180 is the
one finding that could have been caught by a command nobody ran.
