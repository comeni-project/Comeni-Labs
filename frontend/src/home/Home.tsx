import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { analysisAddress } from "../app/address";
import { RailControls } from "../app/rail/RailContext";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { get as fromWiener } from "../wiener/api/client";
import type { components as wiener } from "../wiener/api/schema";
import { Analyses } from "./Analyses";
import { Ask } from "./Ask";
import { NeedsYou, RunningNow } from "./Bands";
import { ThisMachine } from "./Machine";
import { dataLine } from "./progress";
import { useAiConfigured } from "./useAiConfigured";
import { Welcome } from "./Welcome";

type DraftsPage = components["schemas"]["DraftsPage"];
type RunsPage = wiener["schemas"]["RunsPage"];

const STARTERS = ["Gene counts from RNA-seq", "Assemble bacterial isolates", "Variants against a reference"];

/** Home (board: `Home.dc.html`): the question, what runs now, what needs you, every analysis, and
 *  this machine. Before there is any analysis it is Welcome instead.
 *
 *  **Absence is absence**: a band with nothing in it is not drawn, so a quiet page is shorter,
 *  not filled with reassurance. **Never an inventory**: this page shows the laboratory's analyses
 *  and runs, never a contract id, a registry subject or a count of what the product knows.
 *
 *  Mendel and Wiener do not know each other; the browser joins them on the kept pipeline's digest.
 *  Wiener may be away, and then the analyses are still listed, without their runs. */
export function Home() {
  useTitle();
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: () => get<DraftsPage>("/pipeline/drafts") });
  const runs = useQuery({
    queryKey: ["runs", "board"],
    queryFn: () => fromWiener<RunsPage>("/api/runs?limit=200"),
    retry: false,
    refetchInterval: 10_000,
  });
  // Waited for with the rest, so the question box does not arrive after the page and lose typing.
  const model = useAiConfigured();

  if (drafts.isLoading || model.pending) return <Loading what="your analyses" />;
  if (drafts.error) return <Failed error={drafts.error} />;
  const analyses = drafts.data?.drafts ?? [];
  if (!analyses.length) return <Welcome />;
  const board = runs.data?.runs ?? [];

  return (
    <div className="overflow-auto">
      <RailControls label="Recent">
        <ul className="list-none m-0 p-0 flex flex-col">
          {analyses.slice(0, 6).map((d) => (
            <li key={d.id}>
              <Link to={analysisAddress(d.id)}
                    className="flex flex-col px-[10px] py-[6px] rounded-control no-underline hover:bg-surface-2">
                <span className="text-[13px] font-medium text-ink truncate">{d.name || "Untitled"}</span>
                <span className="text-[12px] text-ink-3 truncate">{dataLine(d)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </RailControls>
      <div className="page">
        <h1 className="sr-only">Home</h1>
        <Ask starters={STARTERS} />
        <div className="grid gap-4 items-start [grid-template-columns:repeat(auto-fit,minmax(min(380px,100%),1fr))] empty:hidden">
          <RunningNow runs={board} drafts={analyses} />
          <NeedsYou runs={board} drafts={analyses} />
        </div>
        <Analyses drafts={analyses} runs={board} />
        {runs.error && (
          <p className="m-0 text-[12.5px] text-ink-3">Runs are not shown: the run service did not answer.</p>
        )}
        <ThisMachine />
      </div>
    </div>
  );
}
