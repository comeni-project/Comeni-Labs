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

- [ ] Contracts written with `::`, and `format` on every output.
- [ ] `state: [reads]` on fastqc's report, declared on `qc.report`.
- [ ] A registry release, and the submodule pinned to it.

## Step 3: Comeni drops the old form

- [ ] Remove `state`, `state_required` and `states` as written keys; `pipeline.yml` and goals follow.
- [ ] Reference docs and guides.
