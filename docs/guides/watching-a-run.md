# Watching a run

Mendel builds a pipeline. **Wiener runs it and tells you what happened.** This page takes a
pipeline you have built and follows it to a finished run.

You need the stack up — see [running the stack](running-the-stack.md).

## Send a pipeline to Wiener

Open the builder at `http://localhost:5173/build`, build or open a pipeline, and press **Keep**.
That stores it and gives it an id. Then open the **run** tab and upload it.

It is deliberately two steps rather than one. **Uploading is what discovers the parameters**:
the pipeline declares its own holes — `params.input`, `params.gtf`, wherever your data goes —
and Wiener reads them out of the artifact and asks you to fill them. It cannot show you a form
for a pipeline it has not seen.

**Your browser is what carries the pipeline across.** It fetches the artifact from the Mendel
API and posts it to Wiener; neither service learns the other exists. That is not an accident of
implementation — [the execution boundary](../design/execution-boundary.md) is the argument, and
it is what keeps Mendel a pure build tool with no idea that anything ever runs.

## Read the run

`/runs` lists them. `/runs/{id}` is one run, and it is **one scrolling page**, not a set of
tabs — summary at the top, trend in the middle, detail at the bottom, in that order.

| band | answers |
|---|---|
| the envelope | is this fine? phase, elapsed, how many processes are done |
| the timeline | when did each process run, and what overlapped |
| the tasks | every attempt, sortable — by memory, duration, exit code |

Clicking a timeline lane filters the tasks table **below it**, on the same page. There is never
a second screen for the same run.

The **console** is the one exception and opens as its own view, from the tasks band's header.
It is a stream rather than a summary, so it gets the full height. On a five-task run it is
noise; on a four-hundred-task run it is the last place you should look, not the first.

## One row per process, before the run reaches it

The overview has a row for every process **the pipeline declares**, not every process that has
reported. So the table is its full length from the first second, and a process that has not
started yet is visibly waiting rather than absent.

That matters more than it sounds: *absent* and *not started* look identical in a log, and
telling them apart is most of what you want at minute three of a long run.

## Stopping one

A run can be cancelled from its page. Cancellation is a **declared verb** with a closed
vocabulary rather than a command Wiener passes along — the surface that can stop somebody
else's process is the one that deserves the hardest audit, and a reviewer should be able to
read a list of verbs instead of a sanitiser.

## Across runs

Grafana on `http://localhost:3001` carries the boards that compare runs rather than describe
one: what is wrong now, what breaks often, where time goes, and what capacity was asked for
against what was used. They live in the backend rather than the SPA, so they are not a second
dashboard competing with the run page.

## Next

- [`pipeline.yml`](../reference/pipeline-schema.md) — what you uploaded, field by field
- [Wiener's design](../design/wiener.md) — the run model, the event fold, and why the core is pure
