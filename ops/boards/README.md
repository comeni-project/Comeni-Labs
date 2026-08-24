# The boards

Four, and each answers one question. They live here as JSON rather than in a backend's database,
so a board is something you can read in a diff.

| board | answers |
|---|---|
| `wrong-now.json` | runs in flight, what failed, how every run ended |
| `time.json` | per-process duration — p50, p95, worst — and queue wait |
| `capacity.json` | asked against used, worst case kept |
| `breaks.json` | exit codes per process, and what needed a second try |

**Provisioned automatically** by `make telemetry`, from `ops/grafana/dashboards/wiener.yml`.
Nothing has to be imported by hand.

## Two rules they are built to

**Keep the maximum, never the mean** — `docs/design/wiener.md` §9.3. The maximum is what kills a
run and the mean is what hides it, so every aggregate here is `max` or a high quantile, and the
one place a mean appears it sits beside the worst case rather than instead of it.

**An empty panel says why it is empty.** Silence and breakage look identical otherwise, and a
reader cannot tell which they are looking at. Every panel carries a `noValue` sentence —
*"Nothing has needed a second try"* is good news, and *"No queue wait recorded. It reads zero on
the local executor"* is an explanation rather than a gap.

## What they read

The CI/CD semantic conventions plus six `wiener.*` attributes, all of which are documented in
[`../../notes/specs/2026-08-24-telemetry-for-a-run.md`](../../notes/specs/2026-08-24-telemetry-for-a-run.md).
**Nothing here reads a lab string**, because §8 forbids one becoming a span attribute — so a
board cannot show a sample name even by accident.

## What is honestly thin until W5

**Queue wait reads zero on the local executor**, because there is no queue. The panel is built
now and says so; it becomes the most useful number on these boards the day something runs on a
cluster.

**Memory asked reads the same for every process on one machine**, because Nextflow reports the
value after `process.resourceLimits` has clamped it — and a laptop clamps everything to the same
ceiling. On a cluster the labels' real 36 GB and 72 GB come through.
