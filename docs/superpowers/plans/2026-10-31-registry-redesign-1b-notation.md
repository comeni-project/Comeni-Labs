# Registry redesign, slice 1b: `::` and `format`

**Spec:** [D1](../specs/2026-10-31-registry-redesign-design.md). **Branch:**
`registry-redesign-1b-notation`, on slice 1.

Sized at S, and that was wrong: the files live in two repositories, and the registry's CI runs
against Comeni's `main`, so neither can move first. Three steps, operator's choice (2026-10-31).

## Step 1: Comeni reads and writes both

- [x] `declared/signature.py`: `split`, `join`, `states_in_type`.
- [x] Ports, alternatives and goals accept `type_id: a.b::state`; states written both ways are refused.
- [x] `signature()` and every sentence naming a type and states use `join`, in the API and the page.
- [x] `OutputPort.format`, left out when empty so a contract that says nothing keeps its digest.
- [x] `ModuleSpec.emit_formats` from `path(...)`, and `MD0109` when a contract disagrees.
- [x] The forge writes contracts in the new form, with formats from the module.

## Step 2: the registry moves over (comeni-registry)

- [x] Contracts written with `::`, and `format` on every tool output (#24, v0.6.0).
- [x] The submodule pinned to the release.
- [x] Reverted: `qc.report::reads` on fastqc (#25, v0.6.1). With no plain producer, every plain
  request for a report stopped to ask a person, breaking a rule an existing test states.

## Step 3: Comeni drops the old form

- [x] A contract file writing `state`, `state_required` or `states` is refused (`MD0110`).
- [x] Fixtures, inline test contracts and the reference.

## Deviations

- **Saved pipelines and goals keep `{type_id, states}`.** They are structured data written by the
  engine and read by the API and the page, not notation a person writes. A starter may still write
  `type_id: counts.matrix::gene_level`.
- The model fields stay, so code can build a port directly; only files are held to one spelling.
- `format` changes the digest of every contract that gains it, so the saved pipeline fixture moved.
  `main.nf` stayed byte-identical.
