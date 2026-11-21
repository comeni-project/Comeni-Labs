# Plan: STAR's memory, sized from the genome

Spec: `docs/superpowers/specs/2026-11-20-star-memory-from-genome.md`. Branch: `fix/cleanup-600`
here; a branch off `main` in `../comeni-registry` for the registry change.

- [x] **1. Measure the Nextflow behaviour.** A throwaway pipeline: a config `withName` directive
      closure `memory = { meta.x ... }`. Confirm the task sees `meta`. If it does not, stop and
      bring the operator options.
- [x] **2. Registry (writable checkout).** `memory` setting on `star/genomegenerate`'s contract;
      the derivation and decision in `rules/star_index.yml`, cited. Point the submodule at it
      for development.
- [x] **3. Resolver, test first.** A test that a run-time `directive` setting is found by
      `needed()`; widen the route check.
- [x] **4. Emitter, test first.** Tests for the closure, the label fallback and a build-time
      value with its unit; narrow MD0330; update the golden files the change touches.
- [x] **5. Slow gate.** Extend `test_star_index_at_run_gate.py`: STAR_GENOMEGENERATE's
      `.command.run` asks for the ruled memory; the decided record holds it. Show it fails on
      `main`; ledger it.
- [x] **6. Docs and changelog.** Contract and rule reference where they list routes; CHANGELOG.
- [x] **7. File the STAR_ALIGN follow-up** as a sub-issue of #600.
- [x] **8. `make check`, `make guards`, `make verify`.** Then a PR here and in the registry.

## Ledger
- Step 1 (2026-11-20, Nextflow 25.10.4): a config `withName` closure `memory = { meta.x == null ? 72.GB * task.attempt : MemoryUnit.of("N GB") * task.attempt }` reads the task's `meta`: a sample with the fact asked 2 GB, one without fell back and was clamped by `resourceLimits`. A clamp equal to the host's rounded memory is refused (`req: 47 GB; avail: 47 GB`); Wiener's clamp is the same rounding and has run, so not pursued.
- Deviation (step 2/4): a directive takes one typed value, and a bare number is bytes to Nextflow, so `memory` declares a unit template (`{value} GB`); `UNIT_TEMPLATES` in `comeni_core/spell/directives.py` is the closed set, every other directive still refuses a template (`MD0204`). The emitted value grows with `task.attempt` as the labels do.
- Step 4: the run-time fallback reads the label table already emitted (`_label_memory()`, derived from `RESOURCE_LABELS`) by `task.label`, which Nextflow 25.10.4 exposes as a list in a config closure (probed). Only a sized directive is decided in the run (`at_run.per_task`); a plain directive over a measured fact stays a question, as before.
- Step 4: the pre-pass `deferrable` also tested `Via.EXT` only; caught by `test_upgrade_says_how_many_decisions_replayed` ("1 newly asked"). Both checks now share `per_task`.
- Golden `tests/golden/example/main.nf` and `tests/fixtures/pipeline-v10/pipeline.yml` regenerated with `support.pipeline._build`; regenerate again once the registry commit exists (the layer is `dirty: true` until then).
- Step 8: `make verify` passed (4103, 51 slow, 84 guards) with `LITELLM_MODE=PRODUCTION`. Without it, a full run on a machine with a `.env` fails 91 Wiener and 2 forge tests: litellm loads `.env` at import (#602, filed, not part of this plan).
