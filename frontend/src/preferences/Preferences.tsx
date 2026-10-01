import { useState } from "react";
import { Link, Navigate, NavLink, useParams } from "react-router";

import { Refused } from "../api/client";
import { Empty, Failed, Loading } from "../ui/States";
import { SettingRow } from "./SettingRow";
import { useMenu, useWrite } from "./usePreferences";

/** Settings (spec §1, §7): sections down the left, the chosen one's settings on the right.
 *
 * **Drawn from what the API serves and nothing else.** No section or setting is named here, so
 * a new one appears when it is declared on the server. On a narrow screen the sections stack
 * above the settings.
 */
export function Preferences() {
  const { section } = useParams();
  const menu = useMenu();
  const write = useWrite();
  const [refused, setRefused] = useState<{ key: string; message: string } | null>(null);

  if (menu.isLoading) return <Loading what="settings" />;
  if (menu.error) return <Failed error={menu.error} />;
  const sections = menu.data?.sections ?? [];
  if (!sections.length) return <Empty title="There are no settings to show." />;
  if (!section) return <Navigate to={`/settings/${sections[0].key}`} replace />;
  const current = sections.find((s) => s.key === section);

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
    <main className="gutter grid content-start gap-6 py-7 md:grid-cols-[180px_1fr] max-w-[960px]">
      <nav aria-label="Settings sections" className="flex md:flex-col gap-3 flex-wrap">
        {sections.map((s) => (
          <NavLink
            key={s.key}
            to={`/settings/${s.key}`}
            className={({ isActive }) =>
              `text-secondary no-underline ${isActive ? "text-ink" : "text-ink-3 hover:text-ink"}`}
          >
            {s.title}
          </NavLink>
        ))}
      </nav>
      <section>
        {current ? (
          <>
            <h1 className="text-title text-ink mb-3">{current.title}</h1>
            {current.entries.map((entry) => (
              <SettingRow
                key={entry.setting.key}
                entry={entry}
                menu={menu.data}
                onWrite={(value, done) => save(entry.setting.key, value, done)}
                refusal={refused?.key === entry.setting.key ? refused.message : null}
              />
            ))}
          </>
        ) : (
          <Empty
            title={`There is no section called ${section}.`}
            next="Choose one from the list."
          />
        )}
        {!current && <Link to="/settings" className="text-link text-secondary">All settings</Link>}
      </section>
    </main>
  );
}
