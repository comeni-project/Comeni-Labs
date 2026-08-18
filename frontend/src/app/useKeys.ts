import { useEffect } from "react";

/** One key-binding hook, registered per route.
 *
 * Declared in one place rather than scattered through components, so the map the design
 * promises — J/K move, ↵ opens, A accepts, E evidence — can be read off the code.
 * Ignores keystrokes aimed at a field: `A` in a reason box is the letter A.
 */
export function useKeys(map: Record<string, () => void>) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      const run = map[e.key.toLowerCase()];
      if (run) {
        e.preventDefault();
        run();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [map]);
}
