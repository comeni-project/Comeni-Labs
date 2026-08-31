import { useEffect } from "react";

import { GateVerdict } from "./Gate";
import { SubmitPanel } from "./Submit";
import type { AnsweredStep } from "./useBuilder";
import { open as isOpen } from "./useBuilder";

/** One thing that has to be bound before this pipeline can run — `Sources.entryChannels`. */
type Entry = { key: string; name: string; type_id: string };

/** **Run — the sheet, not a tab.** `n-brun`, and it is where three controls that were sitting
 * beside the canvas actually belong.
 *
 * ═══ IT DID NOT EXIST, AND `Run` OPENED IT ANYWAY ═════════════════════════════════════════
 *
 * `impl-walk` collapses four verbs into one action: *Run = keep → lint → open the run sheet →
 * submit*. Phase 3a built the first two and wired the third to `setPanel("run")` — a panel value
 * **no branch rendered**. So the header's one action ended by blanking the rail, and the only
 * way to finish was the Lint and Send to Wiener buttons still parked above it. Three controls
 * for one sequence, which is exactly what `impl-walk` removed the rail to stop.
 *
 * ═══ INVARIANT 15 IS WHY THIS SHEET EXISTS AT ALL ═════════════════════════════════════════
 *
 * `impl-inv`: *no input accepts a sample identifier, filename or path. The Goal holds a SHAPE.*
 * So the canvas carries the shape — typed input sockets, no settings — and the **binding lives
 * with the run**. Same pipeline, different data, no edit. A source node that carried a path
 * would break the product's central promise, and this sheet is the other half of that split.
 *
 * ═══ THE SHAPE IS THE ARTBOARD'S. THE FACTS UNDER IT ARE NOT INVENTED. ════════════════════
 *
 * `_run_sheet.html` draws `INPUTS · 2`, one bound row per input with `change ▾`, then facts
 * beneath it — *24 pairs*, *already reachable from the cluster*, *14 GB will be staged first,
 * about 6 minutes* — then `RESULTS GO TO`, then the red band, then `96 tasks · last run of this
 * shape took 21m` beside Cancel and Start run.
 *
 * **Every row is here and every unknowable fact is absent**, which is a different thing from
 * replacing the section with a paragraph — that was the first attempt and it threw away the
 * layout to avoid the copy. There is no data-location registry, no reachability probe and no
 * run-shape history in this repository; and `docs/design/wiener.md` §12 is explicit that
 * **uploading is what discovers the parameters** — the artifact declares its own holes and
 * Wiener reads them out on upload, so the binding control genuinely lives on the other side.
 * So each row says what it is, what type it takes, and that it is **not bound yet** — and the
 * one line of prose says where it gets bound. Absence is absence.
 */
export function RunSheet({
  name,
  steps,
  sources,
  draftId,
  blocked,
  gated,
  onClose,
  onOpenSettings,
}: {
  name: string;
  steps: AnsweredStep[];
  /** The graph's entry channels — what this pipeline needs before it can run. */
  sources: Entry[];
  draftId: string | null;
  blocked?: string | null;
  gated: boolean;
  onClose: () => void;
  /** Jump to the value on its own node. The sheet reports; the card is where you answer. */
  onOpenSettings?: (id: string) => void;
}) {
  // `esc to close`, said on the sheet and therefore true.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const open = steps.flatMap((step) =>
    step.settings.filter(isOpen).map((setting) => ({ step, setting })),
  );
  const tasks = steps.length;

  return (
    <div
      className="fixed inset-0 z-50 overflow-auto
                 bg-[color-mix(in_srgb,var(--paper)_74%,transparent)]"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Run ${name}`}
        data-testid="run-sheet"
        onClick={(e) => e.stopPropagation()}
        className="settle mx-auto mt-[50px] mb-12 w-[820px] max-w-[calc(100vw-48px)]
                   border border-line-2 bg-[var(--paper-2)] shadow-e3"
      >
        <div
          className="flex items-baseline justify-between gap-4 px-6 pt-[18px] pb-4 border-b
                     border-line"
        >
          <div>
            <div className="text-[19px] font-semibold tracking-[-.02em] text-ink">
              Run {name}
            </div>
            <div className="font-data text-label text-ink-4 pt-[5px]">
              the pipeline says what it needs · this is where you say where it is
            </div>
          </div>
          <span className="font-data text-label text-ink-4">esc to close</span>
        </div>

        <div className="px-6 pt-5 pb-1.5">
          <div className="text-label font-data uppercase tracking-[.15em] text-ink-3 pb-3.5">
            Inputs · {sources.length}
          </div>

          {sources.map((source, n) => (
            <div
              key={source.key}
              data-testid="sheet-input"
              className="settle pb-5"
              style={{ animationDelay: `${Math.min(n, 8) * 40}ms` }}
            >
              <div className="flex items-baseline gap-3 pb-[9px]">
                <span className="font-data text-body text-ink">{source.name}</span>
                <span className="font-data text-label text-link">{source.type_id}</span>
              </div>
              <Slot what="choose where these files are" />
            </div>
          ))}

          <div className="settle pb-[22px]" style={{ animationDelay: "80ms" }}>
            <div className="text-label font-data uppercase tracking-[.15em] text-ink-3 pb-[9px]">
              Results go to
            </div>
            <Slot what="choose where the results are written" />
          </div>

          {/* One line, and it is the reason every row above is empty rather than a control. */}
          <p className="text-secondary text-ink-3 leading-[1.55] m-0 pb-4">
            Mendel never receives your data. It writes the pipeline with its own holes —{" "}
            <code className="font-data text-ink-2">params.input</code>,{" "}
            <code className="font-data text-ink-2">params.outdir</code> — and{" "}
            <b className="font-normal text-ink-2">Wiener reads them out of the artifact when you
            send it</b>, which is where you fill them in. That is why sending is two clicks.
          </p>
        </div>

        {/* ── Invariant 6's fourth place ─────────────────────────────────────────────── */}
        {open.length > 0 && (
          <div
            data-testid="sheet-open"
            className="settle px-6 pt-4 pb-2 border-t border-line
                       bg-[color-mix(in_srgb,var(--undecided)_4.5%,transparent)]"
            style={{ animationDelay: "120ms" }}
          >
            <div
              className="text-label font-data uppercase tracking-[.15em] text-[var(--undecided)]
                         pb-3.5"
            >
              {open.length} value{open.length === 1 ? " has" : "s have"} no rule
            </div>
            {open.map(({ step, setting }) => (
              <button
                key={`${step.id}.${setting.name}`}
                type="button"
                data-testid="sheet-open-row"
                onClick={() => onOpenSettings?.(step.id)}
                className="w-full text-left bg-transparent border-0 p-0 pb-4 cursor-pointer lift"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-data text-secondary text-ink">{setting.name}</span>
                  <span className="font-data text-label text-ink-4">{step.process}</span>
                </div>
                <div className="text-secondary text-ink-2 pt-1.5">{setting.reason}</div>
              </button>
            ))}
            {/* Invariant 6 says flagged, and `impl-inv` says the sealed profile must INVERT
                this and block the build — nobody has specified that branch, so this does not
                guess it. It proceeds and records the answer as the person's. */}
            <p className="text-secondary text-ink-3 m-0 pb-3">
              You can run with these open. Whatever they end up as is recorded as yours.
            </p>
          </div>
        )}

        {/* ── The footer: what is about to happen, and the two ways out ──────────────────
            **No Lint and Preview buttons.** `Run` already ran the lint on its way to opening
            this — offering the button that just fired is a third control for one sequence in a
            new place. What a person needs here is whether it passed, and the console only when
            it did not: a green gate's output is 200 lines of Groovy deprecation warnings over
            the two sentences the sheet is for.

            **The artboard's `96 tasks · 24 samples × 4 steps · last run of this shape took 21m`
            is one third knowable.** The step count is; the sample count is not, because samples
            arrive with the data and this side never sees them (invariant 15); and there is no
            run-shape history. So it says the part it knows. */}
        <div className="border-t border-line px-6 py-4 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="font-data text-secondary text-ink-3">
              {tasks} step{tasks === 1 ? "" : "s"} · tasks depend on how many samples you bind
            </div>
            <GateVerdict draftId={draftId} blocked={blocked} />
          </div>
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              data-testid="sheet-cancel"
              onClick={onClose}
              className="border border-line-2 px-4 py-[9px] text-body text-ink-2 bg-transparent
                         cursor-pointer lift"
            >
              Cancel
            </button>
            <SubmitPanel draftId={draftId} gated={gated} />
          </div>
        </div>
      </div>
    </div>
  );
}

/** The artboard's binding row: a bordered slot with `change ▾` on the right.
 *
 * **A placeholder, drawn as the control it will be.** It said `not bound yet · bound in Wiener`,
 * which is this codebase's vocabulary rather than a researcher's — somebody reading that has to
 * already know Wiener is the other half of the product before the sentence means anything.
 *
 * It is `disabled` rather than live-but-inert: `impl-walkbugs` records two *Send to Wiener*
 * buttons stacked with the visible one dead, and the rule it left is **do not let a label become
 * a control**. A disabled control is visibly not-yet; a live one that does nothing is a bug.
 *
 * The `title` carries the reason, which is real rather than a limitation worth hiding:
 * `docs/design/wiener.md` §12 — the artifact declares its own holes and **uploading is what
 * discovers the parameters**, so the list of what you could pick does not exist until then.
 */
function Slot({ what }: { what: string }) {
  return (
    <button
      type="button"
      disabled
      data-testid="sheet-slot"
      title={
        "You choose this after sending. The pipeline declares the hole and it is read out of " +
        "the artifact on arrival, so the list of what you can pick does not exist until then."
      }
      className="w-full border border-line bg-[color-mix(in_srgb,var(--paper)_60%,transparent)]
                 px-[13px] py-[11px] flex items-center justify-between gap-3 text-left
                 cursor-not-allowed"
    >
      <span className="font-data text-secondary text-ink-3">{what}</span>
      <span className="font-data text-label text-ink-4">choose ▾</span>
    </button>
  );
}
