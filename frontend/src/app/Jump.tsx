import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { inkOf, isPhase } from "../runs/phases";
import { get as fromWiener } from "../wiener/api/client";
import type { components as wiener } from "../wiener/api/schema";
import { jumpTargets, type Target } from "./jump";

type DraftsPage = components["schemas"]["DraftsPage"];
type RunsPage = wiener["schemas"]["RunsPage"];

/** Jump to a pipeline or run: a box in the shell, and ⌘K (Ctrl+K) from anywhere, even a field.
 *
 * The two lists are the ones Home reads, under the same query keys, so the cache is shared and
 * nothing new is asked of either server. Wiener may not answer; the pipelines are still listed. */
export function Jump() {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const close = () => {
    setOpen(false);
    opener.current?.focus();
  };

  return (
    <>
      <button
        ref={opener}
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Jump to a pipeline or run"
        className="flex items-center gap-[10px] h-[38px] px-[14px] w-[38px] sm:w-[340px] justify-center
                   sm:justify-start rounded-button border border-line-2 bg-surface text-ink-3
                   text-[13.5px] cursor-pointer hover:text-ink transition-colors"
      >
        <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor"
             strokeWidth="1.6" strokeLinecap="round" className="shrink-0">
          <circle cx="7" cy="7" r="5" />
          <path d="M11 11l3.5 3.5" />
        </svg>
        <span className="hidden sm:inline">Jump to a pipeline or run</span>
        <kbd className="hidden sm:inline ml-auto font-data text-[11px] px-[6px] rounded-xs border border-line-2
                        bg-paper text-ink-2">⌘K</kbd>
      </button>
      {open && <Palette onClose={close} />}
    </>
  );
}

function Palette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const drafts = useQuery({ queryKey: ["drafts"], queryFn: () => get<DraftsPage>("/pipeline/drafts") });
  const runs = useQuery({
    queryKey: ["runs", "board"],
    queryFn: () => fromWiener<RunsPage>("/api/runs?limit=25"),
    retry: false,
  });

  const found = jumpTargets(query, drafts.data?.drafts ?? [], runs.data?.runs ?? []);
  const options = [...found.pipelines, ...found.runs];
  const current = Math.min(active, Math.max(0, options.length - 1));

  const go = (target: Target) => {
    onClose();
    navigate(target.to);
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      // Marked as used, so the settings overlay behind this does not close on the same press.
      event.preventDefault();
      event.stopPropagation();
      onClose();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && options[current]) {
      event.preventDefault();
      go(options[current]);
    }
  };

  const optionId = (t: Target) => `${listId}-${t.kind}-${t.id}`;
  const row = (t: Target) => {
    const index = options.indexOf(t);
    return (
      <li
        key={optionId(t)}
        id={optionId(t)}
        role="option"
        aria-selected={index === current}
        onMouseEnter={() => setActive(index)}
        onClick={() => go(t)}
        className={`flex items-baseline gap-3 px-3 py-2 rounded-control cursor-pointer
                    ${index === current ? "bg-now-soft" : ""}`}
      >
        <span className={`truncate ${t.kind === "pipeline" ? "font-data text-body text-ink" : "text-body text-ink"}`}>
          {t.label}
        </span>
        <span className="ml-auto shrink-0 text-secondary"
              style={{ color: t.phase && isPhase(t.phase) ? inkOf[t.phase] : "var(--ink-3)" }}>
          {t.detail}
        </span>
        {t.when && (
          <time dateTime={t.when} className="shrink-0 text-secondary text-ink-3 tnum">
            {new Date(t.when).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
          </time>
        )}
      </li>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-center items-start pt-[12vh] px-4"
         style={{ background: "var(--scrim)" }}
         onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-label="Jump to a pipeline or run" onKeyDown={onKeyDown}
           className="w-full max-w-[560px] rounded-panel border border-line bg-surface shadow-e3 overflow-hidden">
        <input
          autoFocus
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={options[current] ? optionId(options[current]) : undefined}
          aria-label="Pipeline or run"
          placeholder="Jump to a pipeline or run"
          value={query}
          onChange={(event) => { setQuery(event.target.value); setActive(0); }}
          className="w-full px-4 py-3 text-heading bg-surface text-ink border-0 border-b border-line
                     outline-none"
        />
        <ul id={listId} role="listbox" aria-label="Pipelines and runs" className="m-0 p-2 list-none max-h-[60vh] overflow-y-auto">
          {found.pipelines.length > 0 && <li role="presentation" className="px-3 pt-2 pb-1 text-label text-ink-3">Pipelines</li>}
          {found.pipelines.map(row)}
          {found.runs.length > 0 && <li role="presentation" className="px-3 pt-3 pb-1 text-label text-ink-3">Runs</li>}
          {found.runs.map(row)}
        </ul>
        {runs.isError && <p className="m-0 px-5 pb-3 text-secondary text-ink-3">Runs could not be read</p>}
        {!query && options.length === 0 && !drafts.isPending && !runs.isPending && (
          <p className="m-0 px-5 py-4 text-secondary text-ink-3">No saved pipelines or runs yet</p>
        )}
        {query && options.length === 0 && !drafts.isPending && (
          <p className="m-0 px-5 pb-4 text-secondary text-ink-3">Nothing matches "{query}"</p>
        )}
      </div>
    </div>
  );
}
