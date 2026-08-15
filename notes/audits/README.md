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
