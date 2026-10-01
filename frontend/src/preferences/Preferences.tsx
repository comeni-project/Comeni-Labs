import { useState } from "react";

import { Refused } from "../api/client";
import { Empty, Failed, Loading } from "../ui/States";
import { sourceOf } from "./shared";
import { SettingRow } from "./SettingRow";
import { type Menu, useMenu, useWienerMenu, useWrite } from "./usePreferences";

/** The overlay's body: sections down the left, the chosen one's settings on the right (spec §1,
 * §7; the overlay's design, 2026-10-01).
 *
 * **Drawn from what the API serves and nothing else.** No section or setting is named here, so a
 * new one appears when it is declared on the server. The rail groups sections by where their
 * values live, worked out from the declarations rather than listed. On a narrow screen the rail
 * becomes a row of tabs above the settings.
 */
type Section = Menu["sections"][number];

const GROUPS = ["This browser", "This installation", "Reported"] as const;

/** Where a section's values live: kept by the browser, set for the installation, or reported by
 *  a server and never set here. */
function groupOf(section: Section): (typeof GROUPS)[number] {
  const settings = section.entries.map((e) => e.setting);
  if (settings.every((s) => s.where === "browser")) return "This browser";
  if (section.served_by === "wiener" || settings.every((s) => s.kind === "readonly")) {
    return "Reported";
  }
  return "This installation";
}

/** What the rail says beside a section: how many values are set here, or that none is built. */
function countOf(section: Section): { text: string; set: boolean } | null {
  const set = section.entries.filter((e) => sourceOf(e) === "installation").length;
  if (set) return { text: `${set} set`, set: true };
  if (section.entries.every((e) => e.shown.reason?.kind === "designed")) {
    return { text: "not built", set: false };
  }
  return null;
}

export function Preferences({
  section, onSelect,
}: { section: string; onSelect: (key: string) => void }) {
  const menu = useMenu();
  const wiener = useWienerMenu();
  const write = useWrite();
  const [refused, setRefused] = useState<{ key: string; message: string } | null>(null);

  if (menu.isLoading) return <Loading what="settings" />;
  if (menu.error) return <Failed error={menu.error} />;
  // **Both servers' sections, by order.** Every Wiener row is locked, so nothing here writes to
  // Wiener; a Wiener that does not answer costs its own section and says so in the rail.
  const sections = [...(menu.data?.sections ?? []), ...(wiener.data?.sections ?? [])]
    .sort((a, b) => a.order - b.order);
  if (!sections.length) return <Empty title="There are no settings to show." />;
  const current = section ? sections.find((s) => s.key === section) : sections[0];

  const save = (key: string, value: unknown, done?: () => void) => {
    setRefused(null);
    write.mutate(
      { key, value },
      {
        onSuccess: () => done?.(),
        onError: (error) =>
          setRefused({ key, message: error instanceof Refused ? error.message : String(error) }),
      },
    );
  };

  return (
    <div className="flex flex-col md:grid md:grid-cols-[212px_minmax(0,1fr)] flex-1 min-h-0">
      <nav
        aria-label="Settings sections"
        className="flex md:flex-col gap-[4px] md:gap-0 overflow-x-auto md:overflow-visible shrink-0
                   [scrollbar-width:none] [&::-webkit-scrollbar]:hidden
                   px-[12px] py-[8px] md:px-[10px] md:pt-[6px] md:pb-[14px] border-b md:border-b-0 md:border-r
                   border-line"
      >
        {GROUPS.map((group) => {
          const members = sections.filter((s) => groupOf(s) === group);
          if (!members.length) return null;
          return (
            <div key={group} className="contents md:block">
              <div
                className="hidden md:block font-data text-label uppercase tracking-[.14em]
                           text-ink-4 px-[12px] pt-[14px] pb-[6px]"
              >
                {group}
              </div>
              {members.map((s) => {
                const here = s.key === current?.key;
                const count = countOf(s);
                return (
                  <button
                    key={s.key}
                    type="button"
                    aria-current={here ? "page" : undefined}
                    onClick={() => onSelect(s.key)}
                    className={`shrink-0 md:w-full flex items-center justify-between gap-[12px]
                                h-[36px] md:h-[34px] px-[12px] rounded-[3px] text-[12.5px] md:text-body
                                whitespace-nowrap bg-transparent cursor-pointer
                                transition-colors border md:border-0
                                ${here
                                  ? "text-ink bg-hover border-line-2"
                                  : "text-ink-3 hover:text-ink hover:bg-hover border-transparent"}`}
                  >
                    {s.title}
                    {count && (
                      <span
                        className={`hidden md:inline font-data text-label
                                    ${count.set ? "text-link" : "text-ink-4"}`}
                      >
                        {count.text}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
        {/* `contents` on a phone, so the note sits in the row of tabs; a footer on a desk. */}
        <div className="contents md:flex md:mt-auto md:flex-col md:gap-[6px] md:px-[12px] md:pt-[12px] md:border-t md:border-line-soft">
          {wiener.error && (
            <span className="shrink-0 self-center md:self-auto px-[8px] md:px-0 text-label md:text-secondary text-ink-3">
              Running could not be read:{" "}
              {wiener.error instanceof Error ? wiener.error.message : "no answer"}.
            </span>
          )}
          <span className="hidden md:inline font-data text-label text-ink-4">a value in .env always wins</span>
        </div>
      </nav>

      <div className="overflow-y-auto min-h-0 px-[16px] md:px-[32px] pt-[18px] md:pt-[22px] pb-[32px]">
        {current ? (
          <>
            <h3 className="m-0 text-[20px] md:text-[22px] font-semibold tracking-[-.02em] text-ink">
              {current.title}
            </h3>
            {current.lede && (
              <p className="mt-[6px] mb-0 text-body leading-normal text-ink-2 max-w-[560px]">
                {current.lede}
              </p>
            )}
            <div className="mt-[20px]">
              {current.entries.map((entry) => (
                <SettingRow
                  key={entry.setting.key}
                  entry={entry}
                  menu={menu.data}
                  onWrite={(value, done) => save(entry.setting.key, value, done)}
                  refusal={refused?.key === entry.setting.key ? refused.message : null}
                />
              ))}
            </div>
          </>
        ) : (
          <Empty title={`There is no section called ${section}.`} next="Choose one from the list." />
        )}
      </div>
    </div>
  );
}
