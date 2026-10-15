# 2026-10-12 — 14.7.8.3d Part H: before real users

Part H is implemented locally on `stage-four-the-consultant-build`, `750a81bb` through
`2c3503dc`, following the approved
[spec](../../../superpowers/specs/archive/2026-10-12-part-h-before-real-users-design.md). The
operator's choices are commented on #276.

- **Every JSON column is JSONB and every table holding JSON records its shape.** A row stamped
  with an older `shape_version` is refused on load (`MI0400`, `MW0100`), never misread. A golden
  JSON Schema per column fails `make check` when a model changes without a version bump.
  JSONB reorders object keys; nothing a person sees reads that order (cards draw lists, the API
  sorts option ids), and two tests that picked "the first option" by key order now read the
  card's list.
- **A queued run's parameters wait in its own directory** (`params.json`, written before the row
  commits); the job carries only the run id, and the worker queues every `queued` run again when
  it starts. No table holds them (invariant 15).
- **Delete by hand.** A draft goes with its conversations, decisions and gate results; its model
  calls keep their record with the text cleared, and a fork of it keeps its own history, current
  decisions and the evidence it reads. A finished run goes with its rows, directory and stream;
  its pipeline goes with its last run. Both ask first and link to the retention settings.
- **A daily sweep** on each service: a succeeded run's working files when it ends, a failed or
  stopped run's after 7 days, the builder's model replies after 30; drafts and runs kept unless
  a limit is set. Every pass is recorded, zeros included.
- **Every limit is on Settings**: *Data retention* (Mendel) and *Data retention: runs* (Wiener,
  stored by Wiener and written there), each with the last pass's line.
- The browser walk found one defect, "1 replies" (#305), fixed test-first.
- **The fresh review's three Important findings are fixed.** Working files go within five
  minutes of a run ending, not at the next 04:00 pass. A model reply that lands after its draft
  was deleted is stored without its text. A run whose parameters are missing is failed
  (`MW0102`) rather than launched empty, and a job queued under the old signature keeps its
  parameters.

Open: seven review minors, deferred.
- A sweep that races a manual delete aborts its pass.
- A clear is stamped even when `rmtree` failed.
- The gap prompt reads stored key order.
- The exact-boundary day differs between the two services.
- The Settings ledes name Wiener.
- The stamp is a column default rather than a listener.
- `params.json` and `.nextflow.log` stay until the run is deleted.

Also open: the baked images are not rebuilt, and the Python 3.14 gzip cases (#303).
