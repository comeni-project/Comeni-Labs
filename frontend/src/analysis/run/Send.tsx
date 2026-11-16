import { Link, useNavigate } from "react-router";

import { useAnalysis } from "../../app/AnalysisFrame";
import { Loading } from "../../ui/States";
import type { Bindings } from "./useSend";
import { useSend } from "./useSend";

type Missing = Bindings["missing"][number];

/** Where a missing input is fixed: the Data page that holds its kind, or Build for a pipeline not
 *  kept yet. */
function fixedAt(draftId: string, missing: Missing): { to: string; words: string } {
  const base = `/a/${encodeURIComponent(draftId)}`;
  if (!missing.channel) return { to: `${base}/build`, words: "Open Build" };
  if (/reference/.test(missing.why)) return { to: `${base}/data/references`, words: "Open References" };
  return { to: `${base}/data/samples`, words: "Open Samples" };
}

/** A new run (#508): what it reads, from Data, and **Run**. No form: Build connected the
 *  pipeline's inputs to Data's tables by type, and the run is sent with exactly what this says. */
export function Send({ draftId, kept }: { draftId: string; kept: boolean }) {
  const { name } = useAnalysis();
  const navigate = useNavigate();
  const sending = useSend(draftId, { name, keep: !kept });
  const missing = sending.bindings?.missing ?? [];
  const ready = sending.bindings !== null && missing.length === 0;

  const go = async () => {
    const accepted = await sending.send().catch(() => null);
    if (accepted) navigate(`/a/${encodeURIComponent(draftId)}/run/${encodeURIComponent(accepted.run_id)}`);
  };

  return (
    <div className="overflow-y-auto h-full">
      <div className="max-w-[760px] px-4 sm:px-6 pt-4 pb-10 flex flex-col gap-4">
        <h1 className="m-0 text-[24px] font-semibold tracking-[-.015em] text-ink">New run</h1>
        {sending.loading ? <Loading what="what the run reads" /> : (
          <section aria-label="What the run reads" className="bg-surface border border-line rounded-panel px-5 py-5 flex flex-col gap-4">
            {sending.bindings && (
              <p data-testid="run-summary" className="m-0 text-[20px] font-semibold tracking-[-.01em] text-ink">
                {sending.bindings.summary || "Nothing to read yet"}
              </p>
            )}
            <p className="m-0 text-[13px] text-ink-2">
              The pipeline's inputs are connected to this analysis's data by type, so nothing is typed: the run
              reads the files where they are.
            </p>
            {missing.length > 0 && (
              <ul aria-label="Missing before it can run" className="list-none m-0 p-0 flex flex-col rounded-control border border-needs-you-line">
                {missing.map((m) => {
                  const fix = fixedAt(draftId, m);
                  return (
                    <li key={`${m.channel}-${m.why}`} className="flex items-center gap-3 px-4 py-[10px] border-t border-line-soft first:border-t-0">
                      <span aria-hidden className="w-2 h-2 rounded-full bg-needs-you shrink-0" />
                      <span className="flex-1 text-[13px] text-ink">{m.why}</span>
                      <Link to={fix.to} className="text-[12.5px] font-semibold text-now-ink no-underline hover:underline">{fix.words}</Link>
                    </li>
                  );
                })}
              </ul>
            )}
            {sending.error && <p role="alert" className="m-0 text-[13px] text-needs-you-ink">{sending.error}</p>}
            <div className="flex items-center gap-3">
              <button type="button" onClick={go} disabled={!ready || sending.sending}
                      className="h-[38px] px-5 rounded-button border-0 bg-action text-on-action shadow-raise text-[14px] font-semibold cursor-pointer
                                 disabled:opacity-50 disabled:cursor-not-allowed">
                {sending.sending ? "Starting…" : "Run"}
              </button>
              <span className="text-[12.5px] text-ink-3">on this machine</span>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
