# Plan: STAR_ALIGN's memory from the genome (#601)

Follow-up to `2026-11-20-star-memory-from-genome.md`; operator authorised proceeding without a
separate approval round (2026-11-20). Branch `fix/star-align-memory`, stacked on `fix/cleanup-600`.

- [x] **1. `AtRun.meta`** (comeni-core): which `meta` the facts travel on; `meta` unless said, not
      written when it is, so existing files stay byte-identical.
- [x] **2. Resolver**: `_other_slot` finds the one later tuple input whose root every fact
      describes (measured facts only, none folded); `needed` records it as `meta2`, `meta3`.
- [x] **3. Emitter**: the Groovy lookup, `_check_measuring` and `_decided` read `at_run.meta`;
      `_meta_root` takes a slot.
- [x] **4. Registry**: STAR_ALIGN's `memory`, decided by the index build's derived fact.
- [x] **5. Tests**: resolver (`meta2`, build-time value), emitter (closure and record), slow run.
- [x] **6. Docs, changelog, `make verify`.**

## Ledger
- nf-core names tuple inputs `meta`, `meta2`, `meta3` by position; the slot's `meta` name is that
  convention, not read from the module.
- The `decided/` row for a reference's value is per reference (`genome  2  genome_length=230218:measured`).
- Slow test `test_a_real_alignment_asks_for_what_its_genome_needs` failed on the base engine and
  registry (no `star_align.memory.tsv`); passes after, both STAR tasks asking 2 GB (`nextflow log`).
