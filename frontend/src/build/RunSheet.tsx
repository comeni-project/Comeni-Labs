import { useEffect } from "react";

import { GateVerdict } from "./Gate";
import { SubmitAction, SubmitForm } from "./Submit";
import type { AnsweredStep } from "./useBuilder";
import { open as isOpen } from "./useBuilder";
import { useSubmit } from "./useSubmit";

/** One thing that has to be bound before this pipeline can run — `Sources.entryChannels`. */
type Entry = { key: string; name: string; type_id: string };

/** **Run — numbered sections, and a summary that holds the one action** (the *Run sheet* board).
 *
 * *Run = keep → lint → open this sheet → submit.* The sheet says whether the check passed, which
 * files the pipeline needs, and which values are still open; the summary beside it says what is
 * about to happen and holds the action.
 *
 * ═══ INVARIANT 15 IS WHY THE FILES ARE NAMED HERE BUT CHOSEN AFTER SENDING ═════════════════
 *
 * The goal holds a shape, never a path: the canvas carries typed inputs and the **binding lives
 * with the run**. Mendel never receives the data — it writes the pipeline with its own holes and
 * Wiener reads them out of the artifact when it is sent (`docs/design/wiener.md` §12), so the
 * sample sheet and the paths appear under *Your files* once *Send to Wiener* has run.
 *
 * **What nothing in the product knows is not drawn**: the board's reference picker, other
 * executors, task limits, task estimates and *took last time*. Absence is absence.
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
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const submit = useSubmit(draftId, name);

  const open = steps.flatMap((step) =>
    step.settings.filter(isOpen).map((setting) => ({ step, setting })),
  );
  const sent = submit.artifact !== null;

  return (
    <div
      className="fixed inset-0 z-50 overflow-auto bg-[var(--scrim)]"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Run ${name}`}
        data-testid="run-sheet"
        onClick={(e) => e.stopPropagation()}
        className="settle mx-auto my-6 sm:my-12 w-[1120px] max-w-[calc(100vw-32px)] grid gap-4
                   grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] items-start"
      >
        <div className="rounded-panel border border-line bg-surface shadow-e3 px-5 sm:px-7 py-6 flex flex-col gap-6 min-w-0">
          <header className="flex items-start gap-4">
            <h2 className="m-0 text-title font-semibold tracking-[-.02em] text-ink flex-1 min-w-0">Run {name}</h2>
            <button type="button" aria-label="Close" data-testid="sheet-cancel" onClick={onClose}
                    className="w-[32px] h-[32px] rounded-full border-0 bg-transparent text-ink-2 text-[18px]
                               cursor-pointer hover:text-ink focus-visible:shadow-[var(--ring)]">
              ×
            </button>
          </header>

          <Section n={1} title="Checked" done={gated}>
            <GateVerdict draftId={draftId} blocked={blocked} />
          </Section>

          <Section n={2} title="Your files" done={sent && submit.unfilled.length === 0}>
            <ul className="m-0 p-0 flex flex-col gap-2">
              {sources.map((source) => (
                <li key={source.key} data-testid="sheet-input"
                    className="list-none flex flex-wrap items-baseline gap-3 px-4 py-3 rounded-button border border-line">
                  <span className="font-data text-body text-ink">{source.name}</span>
                  <span className="font-data text-label text-now-ink">{source.type_id}</span>
                </li>
              ))}
            </ul>
            {sent ? <SubmitForm submit={submit} /> : (
              <p className="m-0 text-secondary text-ink-3 leading-[1.55]">
                You point at these files after sending: the pipeline declares what it needs, and
                Wiener asks for it when it receives the pipeline. Mendel never receives your data.
              </p>
            )}
          </Section>

          {open.length > 0 && (
            <Section n={3} title="Values still open" done={false} warn>
              <ul className="m-0 p-0 flex flex-col">
                {open.map(({ step, setting }) => (
                  <li key={`${step.id}.${setting.name}`} className="list-none">
                    <button type="button" data-testid="sheet-open-row" onClick={() => onOpenSettings?.(step.id)}
                            className="w-full text-left bg-transparent border-0 px-0 py-2 cursor-pointer
                                       focus-visible:shadow-[var(--ring)]">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="font-data text-secondary text-ink">{setting.name}</span>
                        <span className="font-data text-label text-ink-3">{step.process}</span>
                      </span>
                      <span className="block text-secondary text-ink-2 pt-1">{setting.reason}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-secondary text-ink-3 m-0">
                You can run with these open. Whatever they end up as is recorded as yours.
              </p>
            </Section>
          )}
        </div>

        <aside aria-label="Ready to run" className="flex flex-col gap-4 lg:sticky lg:top-6">
          <div className="rounded-panel border border-line bg-surface shadow-e3 px-5 py-5 flex flex-col gap-4">
            <h3 className="m-0 text-heading font-semibold text-ink">Ready to run</h3>
            <table className="w-full border-collapse text-[13px]">
              <tbody>
                <Fact name="Steps" value={String(steps.length)} />
                <Fact name="Inputs" value={String(sources.length)} />
                <Fact name="Values open" value={String(open.length)} warn={open.length > 0} />
                <Fact name="Where" value="this machine" />
              </tbody>
            </table>
            <SubmitAction submit={submit} draftId={draftId} gated={gated} errors={false} />
            {submit.error && (
              <p role="alert" data-testid="submit-error" className="m-0 text-secondary text-needs-you-ink">
                {submit.error}
              </p>
            )}
          </div>
          <div className="rounded-panel border border-line bg-surface px-5 py-4">
            <h3 className="m-0 text-heading font-semibold text-ink">What this run will record</h3>
            <p className="m-0 mt-2 text-secondary text-ink-2 leading-[1.55]">
              Every task's time, CPU and memory, and each retry with what it asked for. You can
              leave this page; the run keeps going.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

/** A numbered section: a tick once it is done, its number until then. */
function Section({ n, title, done, warn = false, children }: {
  n: number; title: string; done: boolean; warn?: boolean; children: React.ReactNode;
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h3 className="m-0 flex items-center gap-3 text-heading font-semibold text-ink">
        <span aria-hidden className="w-[28px] h-[28px] rounded-full grid place-items-center text-[13px] font-semibold"
              style={done ? { background: "var(--done)", color: "var(--on-action)" }
                : { border: `2px solid ${warn ? "var(--needs-you)" : "var(--ink-2)"}`,
                    color: warn ? "var(--needs-you-ink)" : "var(--ink)" }}>
          {done ? "✓" : n}
        </span>
        {title}
      </h3>
      <div className="flex flex-col gap-3 sm:pl-[40px]">{children}</div>
    </section>
  );
}

function Fact({ name, value, warn = false }: { name: string; value: string; warn?: boolean }) {
  return (
    <tr aria-label={name} style={{ borderTop: "1px solid var(--line)" }}>
      <td className="py-[9px] text-ink-2">{name}</td>
      <td className={`py-[9px] text-right ${warn ? "text-needs-you-ink font-semibold" : "text-ink"}`}>{value}</td>
    </tr>
  );
}
