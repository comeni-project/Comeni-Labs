import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Panel } from "../../ui/Panel";
import { fileOf, get as fromWiener } from "../../wiener/api/client";
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
  const [error, setError] = useState<string | null>(null);
  const files = results.data?.files ?? [];
  const steps = [...new Set(files.map((f) => f.process))];
  const open = async (process: string, name: string) => {
    setError(null);
    try {
      const file = await fileOf(`/api/runs/${runId}/results/file?process=${encodeURIComponent(process)}&name=${encodeURIComponent(name)}`);
      window.open(URL.createObjectURL(file), "_blank", "noopener");
    } catch (failed) {
      setError(failed instanceof Error ? failed.message : String(failed));
    }
  };

  if (results.data && !results.data.published) {
    return <Panel title="Outputs"><p className="m-0 px-5 pb-4 text-[13px] text-ink-3">Nothing published yet: the run has not reached its first step.</p></Panel>;
  }
  return (
    <Panel title="Outputs" hint={results.data ? `${results.data.total} files` : undefined}>
      {error && <p role="alert" className="m-0 px-5 pb-2 text-[13px] text-needs-you-ink">{error}</p>}
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
                <button type="button" onClick={() => void open(f.process, f.name)}
                        className="h-[26px] px-[10px] rounded-control border border-line-2 bg-surface text-[12px] font-semibold text-ink cursor-pointer hover:bg-surface-2">
                  Open
                </button>
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
