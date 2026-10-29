import type { components } from "../api/schema";

export type State = components["schemas"]["State"];

/** A module's state as board 1 draws it: a word, a colour and an icon, never the colour alone.
 *  The two pull request states are placeholders until part 4 (#365). */
export const STATES: { state: State; label: string; colour: string; placeholder?: boolean }[] = [
  { state: "not_imported", label: "Not imported", colour: "text-ink-3" },
  { state: "imported", label: "Imported", colour: "text-done-ink" },
  { state: "update_available", label: "Update available", colour: "text-measured-ink" },
  { state: "unknown", label: "Unknown version", colour: "text-ink-3" },
  { state: "gone_upstream", label: "Gone upstream", colour: "text-measured-ink" },
  { state: "in_review", label: "In review", colour: "text-now-ink", placeholder: true },
  { state: "merged_not_released", label: "Merged, not released", colour: "text-ink-2",
    placeholder: true },
];

export const PLACEHOLDER_NOTE = "Arrives with pull requests (part 4)";

export function labelOf(state: State): string {
  return STATES.find((s) => s.state === state)?.label ?? state;
}

export function colourOf(state: State): string {
  return STATES.find((s) => s.state === state)?.colour ?? "text-ink-3";
}

/** The icon beside a state's word. Decorative: the word carries the meaning. */
export function StateIcon({ state }: { state: State }) {
  const common = { width: 15, height: 15, viewBox: "0 0 24 24", "aria-hidden": true,
                   fill: "none", stroke: "currentColor", strokeWidth: 2,
                   strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (state) {
    case "imported":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M8 12.5l2.7 2.7L16 9.8" /></svg>;
    case "update_available":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 16V8M8.5 11.5L12 8l3.5 3.5" /></svg>;
    case "in_review":
      return (
        <svg {...common}>
          <circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" />
          <circle cx="18" cy="18" r="2.5" /><path d="M6 8.5v7M18 15.5V10a3 3 0 0 0-3-3h-4" />
        </svg>
      );
    case "merged_not_released":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7.5V12l3 2" /></svg>;
    case "unknown":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6M12 16.5v.01" /></svg>;
    case "gone_upstream":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M6 18L18 6" /></svg>;
    default:
      return <svg {...common}><circle cx="12" cy="12" r="9" strokeDasharray="3 3" /></svg>;
  }
}

/** `12 min ago`, for the last sync. */
export function ago(iso: string, now = Date.now()): string {
  const minutes = Math.max(0, (now - Date.parse(iso)) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 90) return `${Math.round(minutes)} min ago`;
  const hours = minutes / 60;
  if (hours < 36) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}
