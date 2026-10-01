import type { Entry } from "./usePreferences";

/** Values the settings overlay's components share; components live in `parts.tsx`. */

/** One field style for every inline control (the design's `.pick`). */
export const FIELD =
  "h-[34px] w-full max-w-[280px] px-[12px] text-[12.5px] text-ink bg-surface border border-line-2 rounded-[3px] hover:border-ink-4 disabled:bg-transparent disabled:border-dashed disabled:text-ink-3 disabled:cursor-not-allowed";

/** Where a value came from, as a person would say it. **A value stored here that equals the
 *  default is the default**: a purpose set back to *same as the default* is stored as `null`,
 *  and calling it *set here* would claim a choice nobody made. */
export function sourceOf(entry: Entry): string {
  const { shown, setting } = entry;
  if (shown.source === "installation"
      && JSON.stringify(shown.value ?? null) === JSON.stringify(setting.default ?? null)) {
    return "default";
  }
  return shown.source;
}
