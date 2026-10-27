# 2026-10-27 — One builder, plan 5: the pipeline file, file first

[The plan](../../superpowers/plans/2026-10-27-one-builder-5-the-pipeline-file.md), on
`one-builder-5` (stacked on `one-builder-4`, on `one-builder-3`, PR #405), for #394. The operator
chose option A: the reason opens beside the file (`.design/one-builder-5/pipeline-file.html`).

## Where things stand

- The page is the file: each setting's first line is marked (`markOf`, served tier words,
  evidence-named per #397); any line of a setting opens its reason beside the file; the counts
  filter the file; *Compile it* calls `GET /pipeline/drafts/{id}/emitted` (`MI0219` when there
  is no pipeline yet) and shows `main.nf` and `nextflow.config`.
- **Which setting a line is** comes from the file's own layout (`fileLines`): `- id:` opens a
  step, `  - name:` under `  settings:` a setting. A change to `pipeline_file.dump`'s layout must
  keep `fileLines.test.ts` honest.
- **One builder is complete** apart from the browser check and model walk of plans 3–5 (#404),
  deferred: the GPU is generating a dataset; the operator will say when.
- **Not merged; `one-builder-4` and `one-builder-5` are not pushed.**
