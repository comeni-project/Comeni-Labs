import { useMenu } from "../preferences/usePreferences";

/** The installation's *Building → Pacing* value as the server would resolve it now —
 *  `together`, `stop_where_needed` or `ask` — or `null` while the menu has not loaded.
 *
 *  **Read when the goal is confirmed, as the engine reads it**: the walk's `pace` route consults
 *  the same setting at that moment, so the describe page can draw the pace cards exactly when the
 *  engine will ask. Anything but a menu is no answer, and the page then leaves the question to the
 *  engine's own card. */
export function usePacing(): string | null {
  const { data, error } = useMenu();
  // A menu that failed to load is no answer: the engine still asks the pace, on its own card.
  if (error) return null;
  const sections = Array.isArray(data?.sections) ? data.sections : [];
  const entry = sections.flatMap((section) => section.entries ?? [])
    .find((e) => e?.setting?.key === "building.pacing");
  const value = entry?.shown?.value;
  return typeof value === "string" ? value : null;
}
