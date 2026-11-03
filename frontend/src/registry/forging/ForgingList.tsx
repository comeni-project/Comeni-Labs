import { useState } from "react";
import { Link } from "react-router";

import { useTitle } from "../../app/useTitle";
import { Empty, Failed, Loading } from "../../ui/States";
import { RegistryTabs } from "../RegistryTabs";
import { useAdaptations } from "./useAdaptation";

/** `/registry/forging` (board 3f): the open adaptations, each with its progress. */
export function ForgingList() {
  useTitle("Forging");
  const list = useAdaptations();
  const [filter, setFilter] = useState("all");
  const shown = list.data?.adaptations.filter((a) => filter === "all"
    || (filter === "you" ? !a.drafting && (a.waiting > 0
        || ["reviewing", "assembled", "tested"].includes(a.phase))
      : filter === "working" ? a.drafting || ["assembling", "testing", "publishing"].includes(a.phase)
      : ["in_review", "merged"].includes(a.phase))) ?? [];
  return (
    <div className="min-h-full bg-paper">
      <RegistryTabs />
      <main className="frame gutter pt-6 pb-12 flex flex-col gap-[14px]">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="m-0 text-[22px] font-semibold">Forging</h1>
          <span className="text-[13px] text-ink-3">Each tool is forged on its own. Start one from the catalogue.</span>
        </div>
        <div role="group" aria-label="Show adaptations" className="seg self-start">
          {[["all", "All"], ["you", "Needs you"], ["working", "Working"], ["review", "In review or merged"]].map(([key, name]) =>
            <button key={key} type="button" className="seg-item" aria-pressed={filter === key} onClick={() => setFilter(key)}>{name}</button>)}
        </div>
        {list.data && list.data.adaptations.length > 0 && shown.length === 0 && <p className="text-ink-3">No adaptations in this view.</p>}
        {list.isPending && <Loading what="the open adaptations" />}
        {list.isError && <Failed error={list.error} />}
        {list.data && list.data.adaptations.length === 0 && (
          <Empty title="Nothing is being forged." next="Pick a module that is not imported in the catalogue, and choose Forge." />
        )}
        {list.data && list.data.adaptations.length > 0 && (
          <ul className="list-none m-0 p-0 bg-surface border border-line rounded-panel overflow-hidden">
            {shown.map((a) => (
              <li key={a.id} className="border-b border-line-soft last:border-b-0">
                <Link to={`/registry/forging/${a.id}`}
                      className="flex flex-wrap items-center gap-x-6 gap-y-1 px-[18px] py-[14px] text-ink no-underline hover:bg-hover">
                  <span className="flex-[1_1_200px] font-data font-medium [overflow-wrap:anywhere]">{a.path} <span className="text-ink-3 font-normal">{a.version}</span></span>
                  <span className="flex-[1_1_160px] text-[13px] text-ink-2">
                    {a.approved} of {a.total} items approved
                    <progress className="block w-full h-1 mt-2 accent-done" aria-label={`${a.path} approval progress`} value={a.approved} max={Math.max(1, a.total)} />
                  </span>
                  <span className={`flex-[1_1_180px] text-[13px] ${a.drafting ? "text-action" : a.waiting ? "text-measured-ink" : "text-ink-3"}`}>
                    {a.drafting ? "the AI is drafting…" : a.phase === "merged" ? "merged, not released"
                      : a.phase === "in_review" ? "in review on comeni-registry"
                      : a.phase === "publishing" ? "opening a pull request"
                      : a.phase === "assembling" ? "checking the assembled draft"
                      : a.phase === "tested" ? "tests green"
                      : a.phase === "testing" ? "tests running in Wiener"
                      : a.phase === "assembled" ? "assembled · tests not green yet"
                      : a.waiting ? `${a.waiting} ${a.waiting === 1 ? "proposal" : "proposals"} waiting for you` : `next: ${a.next_piece ?? "assemble"}`}
                  </span>
                  <span className="text-[12.5px] text-ink-3">{a.started_by === "unknown" ? "Author not recorded" : `Started by ${a.started_by}`}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
