# Design records

Why the system is shaped the way it is. Longer and more opinionated than
[`../concepts/`](../concepts/), and written to be argued with rather than followed.

These are living documents: where one disagrees with the code, the code is right and the
document needs a patch. [`ARCHITECTURE.md`](../../ARCHITECTURE.md) describes what the code
actually does.

| Document | Covers | Built? |
|---|---|---|
| [mendel.md](mendel.md) | the whole architecture — contracts, the four tiers, routing, the compiler, where AI is allowed | yes, for the deterministic core |
| [rule-tables-and-port-logic.md](rule-tables-and-port-logic.md) | the tier-3 decision-table format, declared measurements, module pinning, ports in disjunctive normal form | yes |
| [profiling.md](profiling.md) | where measurements come from, and why profiling is an ordinary build | yes |
| [conformance.md](conformance.md) | whether "if it compiles, it runs" is reachable here, and what it implies for the forge | no — Plan 1.6 |
| [clinical-data-protection.md](clinical-data-protection.md) | the egress boundary, the three protection profiles, why "anonymised" is the wrong word | partly — the boundary exists, `ProfilePolicy` does not |
| [federation.md](federation.md) | registry stacking, provider access, pipeline publication, licensing | partly — stacking exists, publication does not |
| [declared-data.md](declared-data.md) | why declared data is files and not a database, and where a derived index would be legitimate | yes — this is what the code already does |
| [dashboard.md](dashboard.md) + [dashboard.html](dashboard.html) | **the Mendel builder**, with a self-contained mockup. §2 carries the token, type and spacing system that governs **both halves** | no |
| [forge-review.md](forge-review.md) | **the forge interface**, redesigned 2026-08-18 — one queue, three destinations, ten screens. Its mockups are a design canvas rather than a committed page | no |

The two `.html` files open in a browser with no build step and no network access.

## Reading order

If you read one, read [mendel.md](mendel.md). If you read two, add
[clinical-data-protection.md](clinical-data-protection.md) — it is the document that
explains the constraints every other decision is bent around.
