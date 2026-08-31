/** The gate control, and the panel that reports it.
 *
 * **A gate, not a run.** `docs/design/execution-boundary.md` §3: a gate proves this artifact on
 * public test data and takes no samplesheet; running a laboratory's data is Wiener's job and
 * Wiener is not built. The two must not share a label — a control called *Run* that sometimes
 * gates is how invariant 15 stops being structural and starts being a promise.
 *
 * `dashboard.md` §6's disabled *Run pipeline* button carried that sentence in a `title`. It is
 * kept here, where a reader will still find it.
 */
import { useGate } from "./useGate";

/** LINT and PREVIEW only, and the reason is in the Dockerfile: STUB and TEST pass
 *  `-profile ...,docker` and need a Docker daemon, which means mounting the host socket into
 *  the worker — root-equivalent host access, deliberately not taken. */
const GATES = [
  { id: "lint", label: "Lint", what: "the file parses" },
  { id: "preview", label: "Preview", what: "the DAG wires up" },
];

const COLOUR: Record<string, string> = {
  queued: "var(--ink-3)",
  running: "var(--measured)",
  passed: "var(--pea)",
  failed: "var(--undecided)",
};

export function Gate({ draftId, blocked }: { draftId: string | null; blocked?: string | null }) {
  const gate = useGate(draftId);
  const stopped = blocked ?? (draftId ? null : "Keep this pipeline first.");

  return (
    <div className="flex items-center gap-2">
      {GATES.map((g) => (
        <button
          key={g.id}
          data-testid={g.id === "lint" ? "gate-button" : `gate-${g.id}`}
          disabled={gate.running || stopped !== null}
          onClick={() => gate.start(g.id)}
          title={stopped ?? `Gate: ${g.what}. Running a pipeline is Wiener's job.`}
          className="px-3 py-1 rounded-r text-body font-semibold bg-pea text-[var(--on-pea)]
                     border-0 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {gate.active === g.id ? "Gating…" : g.label}
        </button>
      ))}
      {gate.running && (
        // **A gate is slow enough to need saying so.** `lint` is ~2s and `preview` ~10s, and a
        // button that only dims for ten seconds reads as a page that broke. Indeterminate on
        // purpose: Nextflow reports no progress a caller can poll, so a percentage would be
        // invented. `--measured` is the tier colour for *the machinery worked, check it*.
        <span
          data-testid="gate-progress"
          aria-live="polite"
          className="font-data text-secondary text-[var(--measured)] animate-pulse"
        >
          running {gate.active}…
        </span>
      )}
      {gate.run && !gate.running && (
        <span
          data-testid="gate-state"
          className="font-data text-secondary"
          style={{ color: COLOUR[gate.run.state] }}
        >
          {gate.run.gate}: {gate.run.state}
        </span>
      )}
    </div>
  );
}

export function GatePanel({ draftId, blocked }: { draftId: string | null; blocked?: string | null }) {
  const gate = useGate(draftId);

  return (
    <div className="p-3 flex flex-col gap-3">
      <Gate draftId={draftId} blocked={blocked} />
      <p className="text-secondary text-ink-3">
        A gate runs this pipeline on a small public dataset to prove it works. It is not a
        pipeline run — running your own data happens in your laboratory's own environment, and
        Mendel never receives it.
      </p>
      {gate.error && (
        <p data-testid="gate-error" className="text-secondary text-[var(--undecided)]">
          {gate.error}
        </p>
      )}
      {gate.run?.output && (
        <pre
          data-testid="gate-output"
          className="text-secondary font-data bg-surface-2 rounded-r p-2 overflow-x-auto
                     max-h-[40vh] overflow-y-auto whitespace-pre"
        >
          {gate.run.output}
        </pre>
      )}
    </div>
  );
}

/** The gate's **verdict**, with the console only when there is something wrong in it.
 *
 * `GatePanel` is the gate's own workbench — two buttons, the prose, and the full output — and it
 * is the right thing where somebody is deliberately gating. This is what the **run sheet** shows
 * instead, and the difference is the moment: `Run` has already fired the lint by the time the
 * sheet opens, so a button offering to fire it again is a third control for one sequence, and
 * a passing gate's 200 lines of Groovy deprecation warnings bury the two sentences the sheet
 * exists for.
 *
 * **A failure still shows everything.** The rule is not *hide the console*, it is *a green gate
 * has nothing to read*.
 */
export function GateVerdict({
  draftId,
  blocked,
}: {
  draftId: string | null;
  blocked?: string | null;
}) {
  const gate = useGate(draftId);
  const stopped = blocked ?? (draftId ? null : "Keep this pipeline first.");
  const failed = gate.run?.state === "failed";

  return (
    <div className="min-w-0">
      {stopped && <span className="text-secondary text-ink-3">{stopped}</span>}

      {gate.running && (
        <span
          data-testid="gate-progress"
          aria-live="polite"
          className="font-data text-secondary text-[var(--measured)] animate-pulse"
        >
          running {gate.active}…
        </span>
      )}

      {gate.run && !gate.running && (
        <span
          data-testid="gate-state"
          className="font-data text-secondary"
          style={{ color: COLOUR[gate.run.state] }}
        >
          {gate.run.gate}: {gate.run.state}
        </span>
      )}

      {gate.error && (
        <p data-testid="gate-error" className="text-secondary text-[var(--undecided)] mt-1 mb-0">
          {gate.error}
        </p>
      )}

      {failed && gate.run?.output && (
        <pre
          data-testid="gate-output"
          className="text-secondary font-data bg-surface-2 rounded-r p-2 mt-2 mb-0 max-h-[30vh]
                     overflow-auto whitespace-pre"
        >
          {gate.run.output}
        </pre>
      )}
    </div>
  );
}
