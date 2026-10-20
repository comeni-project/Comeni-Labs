# Redesign 5 — Home and its first run

**Issue:** #378 (parent #370). **Status:** built without a question round at the operator's
request (2026-10-20); the calls are the builder's. Branch `redesign-home`, stacked on part 4.
**Boards:** #378 names *Home — what needs you, then your pipelines* and *Home — first run* on the
claude.ai redesign canvas, which is not in the repository. The local `.design/hybrid/Main.dc.html`
(*Home — the lab's work*) is the same identity with a lab, owners and compute; this part follows
#378's text for the content and `Main` for the drawing, minus what the MVP has not got.

## Why

Home stacks a large *Running now*, a *Waiting on a person* list, a describe line and a square
*Work* table, in the pre-redesign drawing. #378 orders it around the person: say what to analyse,
then what needs you, then your pipelines, then what came out.

## What changes (`home/Home.tsx`, `Now.tsx`, `Work.tsx`, `Describe.tsx`, `First.tsx`)

1. **A header:** *Your work* (title) and a line — *N pipelines · N running · N values need you*,
   each part only when nonzero beyond the first — with **New analysis** (the main button, to
   `/build`). No lab name; no *Import pipeline.yml* (opening a saved file is #357).
2. **The describe box leads:** a panel with the prompt field and *Start*, as today
   (`useBegin`), drawn in the new identity. Absent without a model, as today.
3. **Cards, each drawn only when it has something** (absence is absence), in one row that wraps:
   - **Running now:** each running run — its pipeline's name (by digest, as today), the task bar,
     *N of M tasks · elapsed*. No *started by*.
   - **Needs you:** from the drafts' `open_values` — each pipeline with the settings that wait,
     and *Answer* to `/build?draft=<id>` — then *No rule could settle these, so nothing runs
     until someone answers.* A pipeline with only unnamed open values says *N values*.
   - **Went wrong:** failed runs (phase `failed`), most recent first, at most three, each with
     *Open the run*.
4. **Your pipelines:** the *By pipeline / By run* control and the table in a panel, with the
   columns *Pipeline* (name, then what it makes and its steps), *How it was decided* (the
   existing bar plus *N settled · N measured · N open*), *Runs*, *Last outcome*, and delete. No
   *Owner* column.
5. **Results ready:** succeeded runs, most recent three, each the pipeline's name and when it
   finished, linking to the run. Wiener reports no file counts, so none are drawn.
6. **First run** (`First.tsx`, nothing built yet) keeps its composition and takes the same
   header, panel and button styling.

**Not drawn:** *Changed in the registry* — nothing reports a registry release since the old forge
went (the forge, #360, brings releases); compute; owners; *Learn in Code*.

## Testing

Vitest with stubbed responses (`Home.test.tsx`'s pattern): the header line; each card present
only with data and absent without; *Answer* links; failed runs capped at three; results capped
at three and only succeeded; the table without *Owner* and with the decided words; Wiener down
still says so and the pipelines still draw. Browser: Vite with the API answered from fixtures by
the DevTools script (the dev stack is not started on this branch, because part 0's migration would
drop the old forge tables from the development database), 1440 and 390, light and dark.
