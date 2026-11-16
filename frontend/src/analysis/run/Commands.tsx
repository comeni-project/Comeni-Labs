import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { get as fromWiener } from "../../wiener/api/client";

export type Command = { name: string; does: string; command: string; group: string; tool?: string; read_only: boolean };

const GROUPS = ["This run", "A step's task", "From this pipeline's tools", "Disk and machine"];

/** **Commands** (#511, the Console board): every command a person can run in the run's shell,
 *  found by searching what it does, grouped, each with **Insert** and, for one that only reads,
 *  **Run**. The list is declared beside Wiener (`commands.yml`); a tool's own commands show only
 *  when its step is in the run. */
export function Commands({ runId, onInsert, onRun, onClose }: {
  runId: string;
  onInsert: (command: string) => void;
  onRun: (command: string) => void;
  onClose: () => void;
}) {
  const listed = useQuery({
    queryKey: ["terminal-commands", runId],
    queryFn: () => fromWiener<{ commands: Command[] }>(`/api/runs/${runId}/terminal/commands`),
  });
  const [find, setFind] = useState("");
  const [group, setGroup] = useState<string | null>(null);
  const [at, setAt] = useState(0);
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => { search.current?.focus(); }, []);
  const words = find.trim().toLowerCase();
  const shown = (listed.data?.commands ?? [])
    .map((c) => ({ ...c, command: c.command.replaceAll("{run}", runId) }))
    .filter((c) => (!group || c.group === group)
      && (!words || `${c.name} ${c.does} ${c.command}`.toLowerCase().includes(words)));
  const total = listed.data?.commands.length ?? 0;
  const pick = (c: Command, run: boolean) => { (run ? onRun : onInsert)(c.command); onClose(); };

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center pt-[10vh] px-4" role="presentation"
         onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
         style={{ background: "var(--scrim)" }}>
      <section role="dialog" aria-label="Commands" aria-modal="true"
               className="w-full max-w-[720px] max-h-[76vh] flex flex-col bg-surface rounded-panel border border-line shadow-e3 overflow-hidden"
               onKeyDown={(e) => {
                 if (e.key === "Escape") onClose();
                 if (e.key === "ArrowDown") { e.preventDefault(); setAt((n) => Math.min(shown.length - 1, n + 1)); }
                 if (e.key === "ArrowUp") { e.preventDefault(); setAt((n) => Math.max(0, n - 1)); }
                 if (e.key === "Enter" && shown[at]) { e.preventDefault(); pick(shown[at], shown[at].read_only); }
                 if (e.key === "Tab" && shown[at] && !e.shiftKey) { e.preventDefault(); pick(shown[at], false); }
               }}>
        <header className="flex items-center gap-3 px-5 pt-4 pb-3">
          <h2 className="m-0 text-[17px] font-semibold text-ink">Commands</h2>
          <span className="text-[12.5px] text-ink-3">run in the shell, in this run's folder</span>
          <button type="button" aria-label="Close" onClick={onClose}
                  className="ml-auto w-8 h-8 rounded-control border-0 bg-transparent text-ink-3 text-[18px] cursor-pointer hover:bg-surface-2">×</button>
        </header>
        <div className="px-5 pb-3 flex flex-col gap-[10px]">
          <input ref={search} aria-label="Search commands" placeholder="Search what you want to see or do" value={find}
                 onChange={(e) => { setFind(e.target.value); setAt(0); }}
                 className="h-10 px-3 rounded-control border border-line-2 bg-surface text-[14px] text-ink focus:shadow-[var(--ring)] outline-none" />
          <div role="group" aria-label="Kinds of command" className="flex flex-wrap gap-[6px]">
            {[null, ...GROUPS].map((g) => (
              <button key={g ?? "all"} type="button" aria-pressed={group === g} onClick={() => { setGroup(g); setAt(0); }}
                      className={`h-7 px-[10px] rounded-control border text-[12px] font-semibold cursor-pointer
                                  ${group === g ? "border-now-line bg-now-soft text-now-ink" : "border-line-2 bg-surface text-ink-2"}`}>
                {g ?? "All"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto border-t border-line-soft">
          {listed.isPending && <p className="m-0 px-5 py-4 text-[13px] text-ink-3">Reading the commands…</p>}
          {listed.isError && <p className="m-0 px-5 py-4 text-[13px] text-needs-you-ink">The commands could not be read.</p>}
          {GROUPS.filter((g) => shown.some((c) => c.group === g)).map((g) => (
            <div key={g}>
              <h3 className="m-0 px-5 pt-3 pb-1 text-[11px] font-semibold tracking-[.07em] uppercase text-ink-3">{g}</h3>
              <ul className="list-none m-0 p-0">
                {shown.filter((c) => c.group === g).map((c) => {
                  const on = shown[at] === c;
                  return (
                    <li key={c.name} data-testid={`command-${c.name}`}
                        className={`grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-[3px] items-center px-5 py-[10px] ${on ? "bg-surface-2" : ""}`}
                        onMouseEnter={() => setAt(shown.indexOf(c))}>
                      <span className="flex flex-col gap-[3px] min-w-0">
                        <span className="text-[13.5px] font-semibold text-ink">{c.name}</span>
                        <span className="text-[12.5px] text-ink-2">{c.does}</span>
                        <code className="font-data text-[11.5px] text-ink-3 truncate">{c.command}</code>
                      </span>
                      <span className="flex gap-[6px]">
                        <button type="button" onClick={() => pick(c, false)}
                                className="h-[30px] px-[10px] rounded-control border border-line-2 bg-surface text-[12px] font-semibold text-ink-2 cursor-pointer">
                          Insert
                        </button>
                        {c.read_only && (
                          <button type="button" onClick={() => pick(c, true)}
                                  className="h-[30px] px-3 rounded-control border-0 bg-action text-on-action shadow-raise text-[12px] font-semibold cursor-pointer">
                            Run
                          </button>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {listed.data && shown.length === 0 && <p className="m-0 px-5 py-4 text-[13px] text-ink-3">No command matches.</p>}
        </div>
        <footer className="flex items-center gap-3 px-5 py-[10px] border-t border-line-soft bg-surface-2 text-[12px] text-ink-3">
          <span>{shown.length} of {total} commands</span>
          <span className="ml-auto flex gap-3"><span><b className="text-ink-2">↑↓</b> choose</span><span><b className="text-ink-2">Enter</b> run</span><span><b className="text-ink-2">Tab</b> insert</span></span>
        </footer>
      </section>
    </div>
  );
}
