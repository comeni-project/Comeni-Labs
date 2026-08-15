# Root I — every guard is watched failing

**Spec, 2026-08-07.** Closes A14. Root I in
[`../audits/2026-08-07-root-causes.md`](../audits/2026-08-07-root-causes.md).

**This is not a design. It is a working rule and a ledger**, and it is the only root already in
force — it has governed every spec from root A onward.

---

## The finding

> A guard that has never been watched failing may be inert, not merely weak.

Nine instances across two days, every one found by *reverting code and watching*, none by
reading:

| | instance | how it was inert |
|---|---|---|
| 1 | `test_two_layers_sharing_a_basename_do_not_collapse` | asserted something both the broken and fixed code satisfy |
| 2 | Task 6's resolver fixture | one fixture for two sites that defaulted opposite ways |
| 3 | the same edge test | asserted over an empty loop |
| 4 | `make check` for Tasks 7, 9, 10 | the check was never run |
| 5 | `test_no_payload_carries_an_untyped_container` (A20) | the predicate is `False` for every annotation that exists |
| 6 | `test_a_filename_cannot_forge_an_entry_boundary` (A21) | the test re-implements a hash format that moved |
| 7 | `test_construction.py` (A18) | matches a spelling, not a type |
| 8 | the A15 fixture (A22) | asserts over the one of two decision kinds that works |
| 9 | the egress shape rules (A19, A30) | classify by enumeration, so an unnamed shape is silence |

**Instances 5–9 are all in code written to close earlier findings.** The sharpest defect has been
in the freshest code in all three audits.

---

## The rule, already in force

**Every guard a spec adds is reverted and watched failing before its task is called done**, and
the observed failure message is recorded in the plan. A guard whose message would not lead a
reader to the defect is a finding, not a pass.

Each of the eight preceding specs carries a verification table written to this rule. Root A has
nine probes, one of which — `Annotated[str, "invented-marker"]` — passes today and must not
after. Root F's *entire* deliverable is the sweep this rule implies.

---

## The ledger

A14 closes when **every guard in `tests/` has a recorded revert that was watched failing.** Not
when someone reads them and judges them sound; that is how they were written.

Round two covered roughly 40% and said so. The remainder, from reviewer 1's own gap list:

**Untouched entirely** — `test_emit`, `test_runnable`, `test_gates`, `test_publish`,
`test_upgrade`, `test_registry_drift`, `test_resolve`, `test_profile`, `test_pinning`,
`test_replay`, `test_ports`, `test_port_alternatives`, `test_registry`, `test_vocabulary`,
`test_registry_layer`, `test_alternatives`, `test_goal_location`, `test_ir`, `test_ir_profile`,
`test_ir_provenance`, `test_measurement`, `test_measurement_types`, `test_conformance_cli`,
`test_end_to_end`, `test_modulespec`, `test_profiling`, `test_spine_contracts`, `test_counts`.

**Partially covered** — conformance M0102–M0107 (only M0101 reverted), ~29 of 44
`test_audit_regressions` tests, 10 of 13 `test_lockfile`, 10 of 12 `test_digest`.

The ledger lives in `notes/audits/guard-ledger.md`: one row per guard — what was
reverted, what happened, the message quality, and the date. It is append-only, like the journal,
for the same reason.

**Most of the ledger fills itself.** Roots A–H rewrite or touch a large share of these guards,
and each rewrite comes with its own revert under the rule above. The residue is what needs a
dedicated pass.

---

## Two things this rule is not

**Not "write more tests".** Every guard in the list above already exists and already passes. The
question is only whether it *can* fail.

**Not a substitute for design.** Instances 5, 7 and 9 were inert because they classified by
enumeration — roots A, E and F fix that structurally. A ledger would have *found* them; it would
not have prevented them. The rule and the roots do different jobs, and A14 stayed critical
precisely because a protocol alone does not close it.

---

## Verification

The rule verifies itself: a spec's task is not done until its probe's failure message is written
in the plan. Two additional checks:

- **`make verify` after each root**, not `make check` — A14's own fourth instance.
- **A guard rewritten by a root is re-reverted after the rewrite**, not only before. A21 exists
  because a *fix* disarmed a guard; the same could happen to any guard these specs touch.

---

## Sequencing

**No sequencing.** This is in force now and applies to every task in every plan, including the
plans that close it. Scheduling it as a spec to be executed ninth was the original mistake — it
would have produced eight roots' worth of guards nobody watched fail, while a plan to fix that
sat in the queue.
