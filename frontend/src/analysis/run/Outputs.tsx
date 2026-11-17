import { useQuery } from "@tanstack/react-query";

import { Panel } from "../../ui/Panel";
import { get as fromWiener } from "../../wiener/api/client";
import type { components as wiener } from "../../wiener/api/schema";
import { bytes } from "./units";
import { factsOf, useBuildCanvas } from "./useRuns";

type Results = wiener["schemas"]["ResultsOut"];

const PAGE = 500;

/** Run's Outputs: what the run published, by the step that made it, each to open. */
export function Outputs({ draftId, runId, live }: { draftId: string; runId: string; live: boolean }) {
  const results = useQuery({
    queryKey: ["results", runId],
    queryFn: () => fromWiener<Results>(`/api/runs/${runId}/results?limit=${PAGE}`),
    refetchInterval: live ? 6_000 : false,
  });
  const facts = factsOf(useBuildCanvas(draftId).data);
  const files = results.data?.files ?? [];
  const steps = [...new Set(files.map((f) => f.process))];
  // **A link, not a fetched blob** (Checkpoint D): a blob took the app's origin, so a report's
  // scripts could reach the terminal; Wiener serves reports sandboxed. A link opens on the click
  // (no popup blocker) and streams the file rather than loading it into the page. The local
  // proxy adds the token; a hosted install would need a signed link.
  const href = (process: string, name: string) =>
    `/api/runs/${runId}/results/file?process=${encodeURIComponent(process)}&name=${encodeURIComponent(name)}`;

  if (results.data && !results.data.published) {
    return <Panel title="Outputs"><p className="m-0 px-5 pb-4 text-[13px] text-ink-3">Nothing published yet: the run has not reached its first step.</p></Panel>;
  }
  return (
    <Panel title="Outputs" hint={results.data ? `${results.data.total} files` : undefined}>
      {results.error && <p role="alert" className="m-0 px-5 pb-2 text-[13px] text-needs-you-ink">The outputs could not be listed.</p>}
      {steps.length === 0 && <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">Nothing published yet.</p>}
      {steps.map((process) => (
        <div key={process} className="border-t border-line-soft">
          <h3 className="m-0 px-5 pt-3 pb-1 text-[12px] font-semibold text-ink-3">
            {process === "decided" ? "Decided in the run" : facts[process]?.does ?? process}
          </h3>
          <ul aria-label={facts[process]?.does ?? process} className="list-none m-0 p-0">
            {files.filter((f) => f.process === process).map((f) => (
              <li key={f.name} className="flex items-center gap-3 px-5 py-[7px]">
                <span className="flex-1 min-w-0 font-data text-[12.5px] text-ink truncate">{f.name}</span>
                <span className="font-data text-[12px] text-ink-3">{bytes(f.size_bytes)}</span>
                {/* Open shows the file in a tab; a binary (BAM, gzip) cannot be shown, so is not offered. */}
                {f.viewable ? (
                  <a href={href(f.process, f.name)} target="_blank" rel="noopener noreferrer" aria-label={`Open ${f.name}`}
                     className="h-[26px] px-[10px] inline-flex items-center rounded-control border border-line-2 bg-surface text-[12px] font-semibold text-ink no-underline hover:bg-surface-2">
                    Open
                  </a>
                ) : <span className="w-[52px] text-center text-[11.5px] text-ink-3">binary</span>}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {results.data && results.data.total > files.length && (
        <p className="m-0 px-5 py-3 border-t border-line-soft text-[12.5px] text-ink-3">
          Showing {files.length} of {results.data.total}.
        </p>
      )}
    </Panel>
  );
}
