import { useEffect, useState } from "react";
import { useLocation } from "react-router";

import { Refused } from "../api/client";
import { RailControls } from "../app/rail/RailContext";
import { useTitle } from "../app/useTitle";
import { Empty, Failed, Loading } from "../ui/States";
import { SettingRow } from "./SettingRow";
import { type Entry, type Menu, type Server, useLastSweep, useMenu, useWienerMenu, useWrite } from "./usePreferences";

type Section = Menu["sections"][number];

/** The board's sections, in its order, and which served sections each holds. */
const BOARD: { id: string; label: string; intro: string; holds: (s: Section, e: Entry) => boolean }[] = [
  { id: "general", label: "General", intro: "You, and how Comeni looks.",
    holds: (s, e) => s.key === "appearance" || e.setting.key === "system.author" },
  { id: "building", label: "Building", intro: "How the assistant works with you while it builds.",
    holds: (s) => s.key === "building" },
  { id: "models", label: "Models", intro: "Which models Comeni talks to, and for what.",
    holds: (s) => s.key === "models" },
  { id: "running", label: "Running", intro: "Where runs execute and what they can read.",
    holds: (s) => s.served_by === "wiener" && !s.key.startsWith("retention") },
  { id: "privacy", label: "Data & privacy", intro: "What leaves this machine, and how long things are kept.",
    holds: (s) => s.key === "privacy" || s.key.startsWith("retention") },
  { id: "registry", label: "Registry", intro: "The tools and rules pipelines are built from.",
    holds: (s) => s.key === "registry" },
  { id: "about", label: "About", intro: "This installation.",
    holds: (s) => s.key === "system" || s.key === "dev" },
];

interface Group { section: Section; entries: Entry[] }
interface Place { id: string; label: string; intro: string; groups: Group[] }

/** Served sections, placed where the board puts them; a section it does not place keeps its own
 *  title, after them, so a newly declared one still shows. */
export function placesOf(sections: Section[]): Place[] {
  const places: Place[] = BOARD.map((b) => ({ id: b.id, label: b.label, intro: b.intro, groups: [] }));
  for (const section of [...sections].sort((a, b) => a.order - b.order)) {
    const byPlace = new Map<number, Entry[]>();
    for (const entry of section.entries) {
      const at = BOARD.findIndex((b) => b.holds(section, entry));
      const list = byPlace.get(at) ?? [];
      list.push(entry);
      byPlace.set(at, list);
    }
    for (const [at, entries] of byPlace) {
      if (at >= 0) places[at].groups.push({ section, entries });
      else places.push({ id: section.key, label: section.title, intro: section.lede ?? "", groups: [{ section, entries }] });
    }
  }
  return places.filter((p) => p.groups.length > 0);
}

/** `/settings` · **Settings** (board "4 · Settings"): every section on one page, listed in the
 *  rail; `#<section>` opens at one. **Drawn from what the servers declare**: a row is a served
 *  setting through `SettingRow`, written back to the server that serves it. */
export function SettingsPage() {
  useTitle("Settings");
  const menu = useMenu();
  const wiener = useWienerMenu();
  const write = useWrite();
  const { hash } = useLocation();
  const [refused, setRefused] = useState<{ key: string; message: string } | null>(null);
  const sections = [...(menu.data?.sections ?? []), ...(wiener.data?.sections ?? [])];
  // Held until Mendel answers, so Wiener's sections never arrive first and jump the page.
  const places = menu.data ? placesOf(sections) : [];
  useEffect(() => {
    if (hash && places.length) document.getElementById(hash.slice(1))?.scrollIntoView?.({ block: "start" });
  }, [hash, places.length]);

  const save = (key: string, value: unknown, served: Server, done?: () => void) => {
    setRefused(null);
    write.mutate({ key, value, served }, {
      onSuccess: () => done?.(),
      onError: (error) => setRefused({ key, message: error instanceof Refused ? error.message : String(error) }),
    });
  };

  return (
    <div className="overflow-y-auto h-full">
      {places.length > 0 && (
        <RailControls label="Settings sections">
          <nav aria-label="Settings sections" className="flex flex-col gap-[2px]">
            {places.map((p) => (
              <a key={p.id} href={`#${p.id}`}
                 className={`px-[10px] py-[6px] rounded-control text-[13px] no-underline
                             ${hash === `#${p.id}` ? "bg-now-soft text-now-ink font-semibold" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}>
                {p.label}
              </a>
            ))}
          </nav>
        </RailControls>
      )}
      <div className="page max-w-[880px]">
        <h1 className="m-0 text-[22px] font-semibold">Settings</h1>
        {menu.isLoading && <Loading what="settings" />}
        {menu.error && <Failed error={menu.error} />}
        {menu.data && places.length === 0 && <Empty title="There are no settings to show." />}
        {wiener.error && (
          <p className="m-0 text-[13px] text-ink-3">
            Running could not be read: {wiener.error instanceof Error ? wiener.error.message : "no answer"}.
          </p>
        )}
        {places.map((p) => (
          <section key={p.id} id={p.id} aria-labelledby={`${p.id}-title`} className="flex flex-col gap-3 scroll-mt-4">
            <div className="flex flex-col gap-1">
              <h2 id={`${p.id}-title`} className="m-0 text-[17px] font-semibold">{p.label}</h2>
              {p.intro && <p className="m-0 text-[13px] text-ink-2">{p.intro}</p>}
            </div>
            {p.groups.map((g) => (
              <div key={`${g.section.key}-${g.entries[0]?.setting.key}`} className="bg-surface border border-line rounded-panel px-5 py-2">
                {p.groups.length > 1 && <h3 className="m-0 pt-3 text-[13px] font-semibold text-ink-2">{g.section.title}</h3>}
                {g.section.key.startsWith("retention") && <LastCleared served={g.section.served_by} />}
                {g.entries.map((entry) => (
                  <SettingRow key={entry.setting.key} entry={entry} menu={menu.data}
                              onWrite={(value, done) => save(entry.setting.key, value, g.section.served_by, done)}
                              refusal={refused?.key === entry.setting.key ? refused.message : null} />
                ))}
              </div>
            ))}
          </section>
        ))}
        <p className="m-0 text-[12.5px] text-ink-3">A value in <code className="font-data">.env</code> always wins.</p>
      </div>
    </div>
  );
}

/** What each category is called when counted (Part H). Working files of either outcome are
 *  one thing to a reader: folders that went. */
const SWEPT: [string[], string, string][] = [
  [["work_succeeded", "work_failed"], "working folder", "working folders"],
  [["runs"], "run", "runs"],
  [["model_replies"], "reply", "replies"],
  [["drafts"], "draft", "drafts"],
];

/** *Last cleared 12 Oct: 3 working folders, 41 replies* — the line that says the limits above
 *  are being kept, read from the server that keeps them. */
function LastCleared({ served }: { served: Server }) {
  const last = useLastSweep(served, true);
  if (last.isPending || last.error) return null;
  const sweep = last.data;
  let words: string;
  if (!sweep) {
    words = "Not run yet.";
  } else {
    const day = new Date(sweep.ran_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    const parts = SWEPT
      .map(([keys, one, many]) => {
        const n = keys.reduce((sum, k) => sum + (sweep.removed[k] ?? 0), 0);
        return n > 0 ? `${n} ${n === 1 ? one : many}` : null;
      })
      .filter(Boolean);
    words = `Last cleared ${day}: ${parts.length ? parts.join(", ") : "nothing was due"}.`;
  }
  return (
    <p data-testid="last-cleared" className="mt-[6px] mb-0 text-secondary text-ink-3">{words}</p>
  );
}
