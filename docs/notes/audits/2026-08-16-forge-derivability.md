# What the forge can derive, measured

**Method:** `packages/mendel-compiler/tests/test_derivability_survey.py`, run against every
contract in `registry/` whose module is vendored. Re-run it; do not trust this page alone.

**Coverage:** 12 contracts, 12 with a vendored module, 0 unpaired. Every shipped contract is in
the survey, which is better coverage than the plan assumed and means no verdict below rests on a
sample.

| Contract field | Module source of truth | Verdict |
|---|---|---|
| `id` | directory path + version | **partial** — path gives the module key, version does not appear in `main.nf` at all |
| `nf_process` | `ModuleSpec.process` | **derived** — 12/12 exact |
| `nf_include` | path under `vendor/modules/` | **derived** — it *is* the path, minus `.nf` |
| `consumes[].name` | `InputSlot.names` / `DocumentedInput.name` | **hole, candidates derived** — 4/12 rename; see below |
| `consumes[].type_id` | nothing | **hole** |
| `consumes[].state_required` | nothing | **hole** |
| `consumes[].state_required_conventional` | nothing | **hole** |
| `produces[].name` | `ModuleSpec.emits` | **hole, candidates derived** — every contract names 1 of up to 19 |
| `produces[].type_id` | nothing | **hole** |
| `produces[].state` | nothing | **hole** |
| `params[].name` | nothing (a flag is a string in the script body) | **split** — `via: positional` is derived, `via: ext` is a hole |
| `params[].via` / `key` / `template` | `reads_ext_args`, `reads_ext_prefix`, `meta_reads` | **partial** — the module says which routes *exist*, not which a param takes |
| `params[].default` / `because` / `domain` | nothing | **hole** |
| `roles` | nothing | **hole** |
| `priority` / `priority_because` | nothing | **hole** |
| `container` | `ModuleSpec.container` | **derived** — 12/12 exact |
| `nf_inputs[].ports` | nothing (semantic grouping) | **hole** |
| `nf_inputs` arity | `len(ModuleSpec.inputs)` | **derived** — 12/12 exact |
| `nf_inputs[].empty` / `because` / `join` | nothing | **hole** — `empty` is derivable *as a count* once ports are assigned, but not before |
| `ext_args` | nothing | **hole** — 1/12 contracts has one, and its `because` is four sentences of judgement |
| `provenance.source` / `drafted_by` | the ingestion itself | **derived** — the forge knows what it read |
| `provenance.approved_by` / `approved_at` | the human, at land time | **hole by design** — invariant 2 |

## What this changes about the plan

**Three rows the plan guessed, and the measurement moved two of them.**

**`consumes[].name` was listed as derivable from `InputSlot.names` / `DocumentedInput.name`. It
is not.** Four of twelve shipped contracts give a port a name the module never uses:

| Contract | Port | The module's channel |
|---|---|---|
| `nf-core/samtools/index@1.21.0` | `bam` | `input` |
| `nf-core/subread/featurecounts@2.0.6` | `bam` | `bams` |
| `nf-core/multiqc@1.35` | `reports` | `multiqc_files` |
| `comeni/profile/collect@0.1.0` | `measurements` | `multiqc_files` |

The pattern is not arbitrary: in each case the contract name says *what the channel carries*
where the module's says *what the process calls it*. `input` is a slot; `bam` is a thing. That
is exactly the semantic overlay `CLAUDE.md` calls the missing 40%, appearing in a field nobody
had counted. `test_input_port_names_are_a_choice_and_not_a_reading` holds the list, so it fails
in either direction — if it shrinks, naming has become mechanical and the hole can narrow.

**`produces[].name` is derivable only as a candidate set.** Every one of the twelve contracts
declares exactly one output, and the modules offer between 2 and **19** emit channels —
`STAR_ALIGN` alone has nineteen. The set is readable off `main.nf`; which member of it the
pipeline wants is a judgement about what the tool is *for*, and that is nowhere in the module.
So the forge's job here is to present nineteen legal values and refuse to pick, which is the
`Candidate` list of spec §3.3 doing real work rather than decoration.

**`params[].name` splits cleanly in two, and the split is mechanical.** A `via: positional`
param *is* an input channel — `save_unaligned`, `index_format`, `star_ignore_sjdbgtf` all name
slots — so its name is read off the module. A `via: ext` param is a flag the author invented a
name for: `min_mqs` appears nowhere in featureCounts' `main.nf`, because the module only knows
`task.ext.args`. 3 positional, 3 ext, and the rule held for all six.
`test_positional_params_are_named_by_the_module_and_ext_params_are_not` asserts both halves.

**Nothing turned out to be wrong with a shipped contract.** Every derivable field agreed with its
module on all twelve — which is what `tests/test_spine_contracts.py` and `MD0104` already
enforce, so the survey confirms those guards rather than adding to them.

## One weak assertion, recorded rather than relied on

`test_semantic_fields_are_not_in_the_module_at_all` asserts that no `type_id` appears as a
substring of `main.nf`. It passes, and it is the weakest test in the file: `alignment.bam` and
`qc.report` are Mendel vocabulary and were never going to appear in a Nextflow process. It is
kept because it is a real tripwire for the *opposite* discovery — a source that does embed
semantic annotations (pegi3s ships structured tool descriptions) would fail it, and that failure
is the signal that the hole list should shrink for that source. It is not evidence for the
current verdicts; the field-by-field rows above are.
