import type { OverviewData } from "./Overview";
import { ABSENT, seconds, shortBytes } from "./units";

/** Band 1 of the run view — **four panels, never five**.
 *
 * `.design/RunView.dc.html`, and the annotation on `page-5` is the specification: *"Band 1 is
 * FOUR panels, never six. Attention decays left to right — a fifth tile is a fifth thing nobody
 * reads. The four are RED adapted to a pipeline: how far, what broke, is it moving, what is it
 * costing. On a narrow layout they wrap 2x2; they are never dropped to fit, because dropping
 * one drops a question."*
 *
 * **Every panel says what it cannot say yet rather than drawing a zero.** That is the same
 * page's `RunEarly` rule — *"41 seconds in, four tiles that would each read zero. Ship that
 * state deliberately or the page lies for its first minute"* — and `A DASH NEVER MEANS ZERO
 * anywhere on these boards`. A zero here is a measurement; absence is `—` and a sentence.
 */

const PANEL = "bg-surface border border-line rounded-[var(--r)] shadow-e1 px-4 pt-3 pb-3.5 " +
  "flex flex-col";
const LABEL = "text-label uppercase tracking-[.08em] text-ink-3";
const FIGURE = "font-data text-[29px] leading-none tracking-[-.03em] text-ink";
const NOTE = "text-label text-ink-3 mt-2 leading-[1.45]";

function Panel({ label, children, note, testid }: {
  label: string; children: React.ReactNode; note: React.ReactNode; testid: string;
}) {
  return (
    <div className={PANEL} data-testid={testid}>
      <div className={LABEL}>{label}</div>
      <div className="flex items-end justify-between gap-2.5 mt-2.5">{children}</div>
      <div className={NOTE}>{note}</div>
    </div>
  );
}

/** **Steps, not tasks, and the artboard says why on the panel itself.** Nextflow discovers
 *  tasks as channels emit, so a task percentage has no denominator; the artifact declares its
 *  steps before the run starts. Absent when nothing was declared — A192, the artifact could not
 *  be read, and a bar over a denominator of zero is an invented number. */
function Progress({ data }: { data?: OverviewData }) {
  const declared = data?.steps_declared ?? 0;
  const finished = data?.steps_finished ?? 0;
  if (declared === 0) {
    return (
      <Panel label="progress" testid="panel-progress"
             note="no artifact to declare them — a bar over a denominator of zero is invented"
      ><span className={FIGURE}>{ABSENT}</span></Panel>
    );
  }
  // One cell per declared step, in declared order — the artboard's five-segment bar. A step
  // that is running is its own colour, so *where* the run is reads without the table.
  const cells = (data?.rows ?? []).filter((row) => row.declared);
  return (
    <Panel label="progress" testid="panel-progress"
           note={<>Steps, not tasks — the artifact declares {declared}.{" "}
             <span className="text-[var(--ink-4)]">Nextflow discovers tasks as channels emit, so a task
             percentage has no denominator.</span></>}>
      <span className={FIGURE}>
        {finished} <span className="text-[16px] text-ink-3">of {declared}</span>
      </span>
      <span className="flex gap-[3px] w-[120px] h-[9px]">
        {cells.map((row) => (
          <span key={row.process} className="flex-1" style={{
            background: row.tasks > 0 && row.done === row.tasks ? "var(--pea)"
              : row.running > 0 ? "var(--running)"
              : row.failed > 0 ? "var(--fault)"
              : "var(--surface-2)",
          }} />
        ))}
      </span>
    </Panel>
  );
}

/** **What broke.** A retry is not a failure and the artboard draws it as a separate badge —
 *  a task that was OOM-killed at 36 GB and succeeded at 72 is the most interesting thing on
 *  the page and it is not a failure count. */
function Failures({ failed, retried }: { failed: number; retried: number }) {
  return (
    <Panel label="failures" testid="panel-failures"
           note={retried > 0
             ? `${retried} task${retried === 1 ? "" : "s"} retried — a retry is not a failure`
             : "nothing has failed and nothing has retried"}>
      <span className={FIGURE} style={failed > 0 ? { color: "var(--fault)" } : undefined}>
        {failed}
      </span>
      {retried > 0 && (
        <span className="font-data text-label uppercase tracking-[.1em] px-2 py-[3px]"
              style={{ color: "var(--measured)", background: "color-mix(in srgb, var(--measured) 12%, transparent)",
                       border: "1px solid color-mix(in srgb, var(--measured) 27%, transparent)" }}>
          {retried} retry
        </span>
      )}
    </Panel>
  );
}

/** **Is it moving** — time since the last thing finished, which is the question a watched run
 *  actually raises. A run with four tasks running and nothing completing for twenty minutes is
 *  not visibly different from a healthy one on any other panel here. */
function Moving({ lastMs, now, live }: { lastMs: number | null; now: number; live: boolean }) {
  if (!live) {
    return (
      <Panel label="moving" testid="panel-moving" note="the run has ended"
      ><span className={FIGURE}>{ABSENT}</span></Panel>
    );
  }
  if (lastMs == null) {
    // **Absent is not zero.** Nothing has completed yet, so *since the last completion* has
    // no value — and drawing `0s` would say the opposite of the truth.
    return (
      <Panel label="moving" testid="panel-moving"
             note="nothing has completed yet, so there is no interval to measure"
      ><span className={FIGURE}>{ABSENT}</span></Panel>
    );
  }
  return (
    <Panel label="moving" testid="panel-moving" note="Since the last completion.">
      <span className={FIGURE}>{seconds(Math.max(0, now - lastMs))}</span>
    </Panel>
  );
}

/** **What it is costing** — the worst over-ask among processes that reported, which is the one
 *  number that turns a resource complaint into a specific edit. Only reported rows count: a
 *  process that never ran has asked for nothing and peaked at nothing, and dividing those is
 *  an invented ratio rather than a missing one. */
function ResourceFit({ data }: { data?: OverviewData }) {
  const rows = (data?.rows ?? []).filter(
    (row) => (row.memory_asked_bytes ?? 0) > 0 && (row.memory_peak_bytes ?? 0) > 0,
  );
  if (rows.length === 0) {
    return (
      <Panel label="resource fit" testid="panel-fit"
             note="no process has reported both what it asked for and what it touched"
      ><span className={FIGURE}>{ABSENT}</span></Panel>
    );
  }
  const worst = rows.reduce((a, b) =>
    (a.memory_asked_bytes! / a.memory_peak_bytes!) >= (b.memory_asked_bytes! / b.memory_peak_bytes!)
      ? a : b);
  const ratio = worst.memory_asked_bytes! / worst.memory_peak_bytes!;
  return (
    <Panel label="resource fit" testid="panel-fit"
           note={<>{worst.process} asks {shortBytes(worst.memory_asked_bytes)} and peaked at{" "}
             {shortBytes(worst.memory_peak_bytes)}.{" "}
             <span className="text-[var(--ink-4)]">Worst over-ask of {rows.length} process
             {rows.length === 1 ? "" : "es"} that reported.</span></>}>
      <span className={FIGURE} style={ratio >= 2 ? { color: "var(--measured)" } : undefined}>
        {ratio.toFixed(1)}×
      </span>
    </Panel>
  );
}

export function Panels({ overview, failed, retried, lastMs, now, live }: {
  overview?: OverviewData; failed: number; retried: number;
  lastMs: number | null; now: number; live: boolean;
}) {
  return (
    // **They wrap 2x2 and are never dropped to fit** — dropping one drops a question. `auto-fit`
    // with a floor rather than a media query, so the wrap happens at the width where a panel
    // stops being readable rather than at a number somebody guessed.
    <div data-testid="run-panels"
         className="grid gap-3 mt-3"
         style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
      <Progress data={overview} />
      <Failures failed={failed} retried={retried} />
      <Moving lastMs={lastMs} now={now} live={live} />
      <ResourceFit data={overview} />
    </div>
  );
}
