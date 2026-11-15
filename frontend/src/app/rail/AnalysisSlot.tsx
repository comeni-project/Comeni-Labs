import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router";

import { get, post } from "../../api/client";
import type { components } from "../../api/schema";
import { Icon, type IconName } from "./icons";
import { useRail } from "./RailContext";

type DraftOut = components["schemas"]["DraftOut"];
type DraftsPage = components["schemas"]["DraftsPage"];

export type AnalysisPage = "data" | "build" | "run";

/** The sub-pages each analysis page has, in rail order. Build has none: its rail holds controls. */
export const SUB_PAGES: Record<AnalysisPage, { sub: string | null; label: string }[]> = {
  data: [
    { sub: null, label: "Overview" },
    { sub: "samples", label: "Samples" },
    { sub: "references", label: "References" },
    { sub: "files", label: "Files" },
  ],
  build: [],
  run: [
    { sub: null, label: "Overview" },
    { sub: "steps", label: "Steps" },
    { sub: "outputs", label: "Outputs" },
    { sub: "console", label: "Console" },
  ],
};

const PAGES: { page: AnalysisPage; label: string; icon: IconName }[] = [
  { page: "data", label: "Data", icon: "data" },
  { page: "build", label: "Build", icon: "build" },
  { page: "run", label: "Run", icon: "run" },
];

/** What is open: the analysis switcher, then Data / Build / Run with the active page's sub-pages
 *  indented under it. `status` is the one-line state under each page's name ("24 samples"). */
export function AnalysisSlot({ draftId, page, run, status = {} }: {
  draftId: string;
  page: AnalysisPage;
  /** The run open under Run, whose sub-pages are listed; none, and Run lists no sub-pages. */
  run?: string;
  status?: Partial<Record<AnalysisPage, string>>;
}) {
  const { mini } = useRail();
  const draft = useQuery({
    queryKey: ["draft", draftId],
    queryFn: () => get<DraftOut>(`/pipeline/drafts/${encodeURIComponent(draftId)}`),
  });
  const base = `/a/${encodeURIComponent(draftId)}`;

  return (
    <div className="flex flex-col gap-[2px]">
      {!mini && <Switcher draftId={draftId} name={draft.data?.name || "Untitled analysis"} />}
      {PAGES.map(({ page: p, label, icon }) => {
        const root = p === "run" && run ? `${base}/run/${encodeURIComponent(run)}` : `${base}/${p}`;
        const subs = p === "run" && !run ? [] : SUB_PAGES[p];
        const on = p === page;
        return (
          <div key={p} className="flex flex-col">
            <Link to={`${base}/${p}`} title={label} aria-label={mini ? label : undefined}
                  aria-current={on && subs.length === 0 ? "page" : undefined}
                  className={`flex items-center gap-[11px] rounded-control no-underline
                              ${mini ? "justify-center py-[10px]" : "px-[10px] py-[9px]"}
                              ${on ? "bg-now-soft text-now-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
              <Icon name={icon} />
              {!mini && (
                <span className="flex flex-col gap-[1px] min-w-0">
                  <span className="text-[14px] font-semibold">{label}</span>
                  {status[p] && <span className={`text-[12px] ${on ? "text-now-ink" : "text-ink-3"}`}>{status[p]}</span>}
                </span>
              )}
            </Link>
            {on && !mini && subs.length > 0 && (
              <ul aria-label={`${label} pages`} className="list-none m-0 p-0 flex flex-col">
                {subs.map(({ sub, label: name }) => {
                  const to = sub ? `${root}/${sub}` : root;
                  return (
                    <li key={name}>
                      <NavLink to={to} end
                               className={({ isActive }) =>
                                 `flex items-center pl-[39px] pr-[10px] py-[6px] rounded-control text-[13px] no-underline
                                  ${isActive ? "text-ink font-semibold" : "text-ink-2 hover:text-ink hover:bg-surface-2"}`}>
                        {name}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** The analysis switcher: this analysis's name, and the others to open instead. */
function Switcher({ draftId, name }: { draftId: string; name: string }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const drafts = useQuery({
    queryKey: ["drafts"],
    queryFn: () => get<DraftsPage>("/pipeline/drafts"),
    enabled: open,
  });
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  const fresh = async () => {
    setOpen(false);
    const { id } = await post<{ id: string }>("/pipeline/drafts", { graph: { nodes: [], edges: [] } });
    navigate(`/a/${encodeURIComponent(id)}/data`);
  };

  return (
    <div ref={box} className="relative mb-2 mr-[42px]">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="listbox"
              className="w-full flex items-center justify-between gap-2 px-[10px] py-[9px] rounded-control border
                         border-line bg-surface cursor-pointer text-left">
        <span className="flex flex-col gap-[1px] min-w-0">
          <span className="text-[11.5px] text-ink-3">Analysis</span>
          <span className="text-[14px] font-semibold text-ink truncate">{name}</span>
        </span>
        <span className="text-ink-3"><Icon name="updown" size={16} /></span>
      </button>
      {open && (
        <div role="listbox" aria-label="Analyses"
             className="absolute z-20 left-0 right-0 mt-1 rounded-control border border-line bg-surface shadow-e2 py-1
                        max-h-[320px] overflow-y-auto">
          {(drafts.data?.drafts ?? []).map((d) => (
            <Link key={d.id} role="option" aria-selected={d.id === draftId}
                  to={`/a/${encodeURIComponent(d.id)}/data`} onClick={() => setOpen(false)}
                  className={`block px-[10px] py-[7px] text-[13px] no-underline truncate
                              ${d.id === draftId ? "text-now-ink font-semibold" : "text-ink-2 hover:bg-surface-2"}`}>
              {d.name || d.id.slice(0, 8)}
            </Link>
          ))}
          <button type="button" onClick={fresh}
                  className="w-full text-left px-[10px] py-[7px] text-[13px] text-now-ink border-0 bg-transparent
                             cursor-pointer hover:bg-surface-2">
            + New analysis
          </button>
        </div>
      )}
    </div>
  );
}
