import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { Icon, type IconName } from "../app/rail/icons";
import { RailControls, RailSlot, useRailMini } from "../app/rail/RailContext";
import { describe, live, waiting, type ItemView } from "./items";
import { useUpstream } from "./useUpstream";
import { progressOfSummary, progressOfView, releasedOf, stagesOf, statusOf, type Stage, type StageState } from "./stages";

type View = components["schemas"]["AdaptationView"];
type List = components["schemas"]["AdaptationList"];

export const forgeName = (path: string, version?: string | null) => `${path}${version ? ` ${version}` : ""}`;

const DOT: Record<StageState, string> = { done: "bg-now-mid", now: "bg-measured", failed: "bg-needs-you", later: "bg-mark" };
const PAGES: { name: Stage["name"]; to: string; icon: IconName }[] = [
  { name: "tool", to: "", icon: "tool" },
  { name: "tests", to: "/tests", icon: "check" },
  { name: "publish", to: "/publish", icon: "publish" },
];

export function useForgings() {
  return useQuery({ queryKey: ["adaptations"], queryFn: () => get<List>("/forge/adaptations") });
}

/** **The Forge in the rail** (boards "5 · Forge", "6 · Forging"): the forging picker; on Forge
 *  home the forgings under it; inside a forging its three pages with their status lines, then
 *  **Review**: the AI's choices still waiting for a person. */
export function ForgeSlot({ view, onReview }: { view?: View; onReview?: (key: string) => void }) {
  const mini = useRailMini();
  const forgings = useForgings();
  const list = forgings.data?.adaptations ?? [];
  const upstream = useUpstream(view);
  const stages = view ? stagesOf({ ...progressOfView(view), released: releasedOf(upstream.data?.row?.state) }) : [];
  const review = view ? live(view.items).filter(waiting) : [];
  const base = view ? `/forge/${encodeURIComponent(view.id)}` : "";

  return (
    <>
      <RailSlot>
        {!mini && <Picker current={view ? forgeName(view.path, view.version) : null} />}
        {view && PAGES.map(({ name, to, icon }) => {
          const stage = stages.find((s) => s.name === name);
          return (
            <NavLink key={name} to={`${base}${to}`} end title={stage?.label} aria-label={mini ? stage?.label : undefined}
                     className={({ isActive }) => `flex items-center gap-[11px] rounded-control no-underline
                                 ${mini ? "w-10 h-10 mx-auto justify-center" : "px-[10px] py-[9px]"}
                                 ${isActive ? "bg-now-soft text-now-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
              {({ isActive }) => (
                <>
                  <Icon name={icon} />
                  {!mini && stage && (
                    <span className="flex flex-col gap-[1px] min-w-0">
                      <span className="text-[14px] font-semibold">{stage.label}</span>
                      <span className={`text-[12px] ${stage.state === "failed" ? "text-needs-you-ink" : isActive ? "text-now-ink" : "text-ink-3"}`}>{stage.note}</span>
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </RailSlot>
      {view && !mini && (
        <RailControls label="Review">
          {review.length === 0 && <span className="px-[10px] py-1 text-[12.5px] text-ink-3">Everything reviewed.</span>}
          {review.map((item) => <ReviewRow key={item.key} item={item} onPick={onReview} />)}
        </RailControls>
      )}
      {!view && !mini && list.length > 0 && (
        <RailControls label="Forgings">
          {list.map((f) => <ForgingRow key={f.id} forging={f} />)}
        </RailControls>
      )}
    </>
  );
}

function ForgingRow({ forging: f }: { forging: List["adaptations"][number] }) {
  const upstream = useUpstream({ source: "nf-core", path: f.path });
  const status = statusOf(stagesOf({ ...progressOfSummary(f), released: releasedOf(upstream.data?.row?.state) }));
  return (
              <Link to={`/forge/${encodeURIComponent(f.id)}`}
                    className="flex gap-2 px-[10px] py-[6px] rounded-control no-underline hover:bg-surface-2">
                <span aria-hidden="true" className={`mt-[6px] w-[7px] h-[7px] rounded-full shrink-0 ${DOT[status.state]}`} />
                <span className="flex flex-col min-w-0">
                  <span className="font-data text-[12.5px] font-semibold text-ink truncate">{forgeName(f.path, f.version)}</span>
                  <span className="text-[11.5px] text-ink-3">{status.note}</span>
                </span>
              </Link>
  );
}

function ReviewRow({ item, onPick }: { item: ItemView; onPick?: (key: string) => void }) {
  const { title, kind } = describe(item);
  return (
    <button type="button" onClick={() => onPick?.(item.key)}
            className="flex gap-2 w-full px-[10px] py-[6px] rounded-control border-0 bg-transparent text-left cursor-pointer hover:bg-surface-2">
      <span className="mt-[1px] h-[18px] px-[5px] rounded-xs bg-ai-soft text-ai text-[10.5px] font-bold leading-[18px] shrink-0">AI</span>
      <span className="flex flex-col min-w-0">
        <span className="text-[12.5px] font-semibold text-ink truncate">{title}</span>
        <span className="text-[11.5px] text-ink-3 truncate">{kind}</span>
      </span>
    </button>
  );
}

/** "Forging · Open a forging": this forging's name, and the others to open instead. */
function Picker({ current }: { current: string | null }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const forgings = useForgings();
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div ref={box} className="relative mb-2">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="listbox"
              className="w-full flex items-center justify-between gap-2 px-[10px] py-[9px] rounded-control border border-line bg-surface cursor-pointer text-left">
        <span className="flex flex-col gap-[1px] min-w-0">
          <span className="text-[11.5px] text-ink-3">Forging</span>
          <span className={`text-[14px] font-semibold truncate ${current ? "text-ink font-data" : "text-ink-2"}`}>{current ?? "Open a forging"}</span>
        </span>
        <span className="text-ink-3"><Icon name="updown" size={16} /></span>
      </button>
      {open && (
        <div role="listbox" aria-label="Forgings"
             className="absolute z-20 left-0 right-0 mt-1 rounded-control border border-line bg-surface shadow-e2 py-1 max-h-[320px] overflow-y-auto">
          {(forgings.data?.adaptations ?? []).map((f) => (
            <Link key={f.id} role="option" aria-selected={forgeName(f.path, f.version) === current}
                  to={`/forge/${encodeURIComponent(f.id)}`} onClick={() => setOpen(false)}
                  className="block px-[10px] py-[7px] font-data text-[13px] text-ink-2 no-underline truncate hover:bg-surface-2">
              {forgeName(f.path, f.version)}
            </Link>
          ))}
          <Link to="/forge" onClick={() => setOpen(false)}
                className="block px-[10px] py-[7px] text-[13px] text-now-ink no-underline hover:bg-surface-2">
            + Forge a tool
          </Link>
        </div>
      )}
    </div>
  );
}
