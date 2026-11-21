# STAR's memory, sized from the genome

Issue: #509, #535 (tracked in #600). Operator's choice, 2026-11-20: a rule plus run-time sizing.

## The defect

Both STAR modules carry nf-core's `label 'process_high'`. The emitted config maps that label to
`72.GB * task.attempt` (`RESOURCE_LABELS`, `packages/mendel-compiler/src/mendel_compiler/emit.py`),
and Wiener's `process.resourceLimits` clamps it to the host (`wiener_api/services/launcher.py`).
So every STAR task asks for nearly the whole machine: 46 GB for a 230 kb genome that peaked at
7.2 MB. STAR_GENOMEGENERATE then also passes `--limitGenomeGenerateRAM` from `task.memory`.

## What changes

1. **Registry:** `nf-core/star/genomegenerate` declares a `memory` setting, `via: directive`,
   an integer number of gigabytes. A new derivation in `registry/rules/star_index.yml` gives it
   from `genome_length`: about 10 bytes per base (STAR's manual: ~32 GB for a human genome),
   at least 2 GB, rounded up. It is cited. It is a rule, so the build shows the value and why.
2. **Resolver:** `at_run.needed()` accepts the `directive` route as well as `ext`
   (`packages/mendel-resolver/src/mendel_resolver/at_run.py`, the `Via.EXT` check). The lookup and
   its facts are the same as for `sa_index_nbases`.
3. **Emitter:** `_directive_scope` emits a run-time directive as a closure over the task's
   `meta`, `withName: X { memory = { <lookup> == null ? <label default> : <lookup>.GB * task.attempt } }`.
   When the lookup gives nothing (an undetermined fact), the task keeps its label's request, so
   nothing gets worse than today. `_ext_scope`'s MD0330 refusal of non-`ext` run-time settings
   narrows to the routes that still cannot read `meta`. A setting known at build time (a person
   stated the genome length) renders as a plain value with the unit, as directives do now.
4. **The decided record** (`_decided`) already writes every run-time value; a directive setting
   joins it unchanged.

## Out of scope, and why

- **STAR_ALIGN.** Its first input is the reads; `genome_length` travels on the reference's
  `meta2`, and the run-time lookup reads only the first input's `meta`. Sizing align means teaching
  the lookup a second `meta`, a larger change. It keeps its label for now; filed as a follow-up.
- **Other tools and labels.** The label table stays nf-core's convention.

## Verification

- Unit: resolver finds the directive setting at run time; emitter renders the closure and the
  fallback; MD0330 still refuses a run-time `meta`/`publish` route.
- Slow gate (`tests/emit/test_star_index_at_run_gate.py`, extended): a real Nextflow run on
  nf-core's test genome asks STAR_GENOMEGENERATE for the ruled memory, not 72 GB, and records it
  in `decided/`. `make verify` at the end. Guard evidence in `tests/fixtures/guard-ledger.md`.
- Unproven until run: that Nextflow evaluates a config directive closure with the task's input
  `meta` in scope, as it does for `ext.args`. The plan's first task measures it.
