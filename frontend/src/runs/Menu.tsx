import { useCallback, useEffect, useRef, useState } from "react";

/** One item. `w4` marks a verb this slice cannot perform yet.
 *
 * **Listed and dimmed rather than absent** — §12.3. A menu that grows two new items in six
 * months is worse than one that always had the shape, because people learn positions.
 */
export type MenuItem = {
  label: string;
  onPick?: () => void;
  w4?: boolean;
  /** Why this item is dim, when the reason is not "W4 does it".
   *
   * The distinction is worth a field: `retry this task` is a verb W4 will add, and `copy work
   * directory` is a verb nothing will add here — `/tasks` carries `tag` and no other lab
   * string, which A200 decided on purpose. Tagging both `W4` would promise one of them. */
  why?: string;
  separated?: boolean;
};

const MENU_WIDTH = 240;

export function Menu({ items, at, onClose }: {
  items: MenuItem[];
  at: { x: number; y: number };
  onClose: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) onClose();
    };
    const key = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    // `capture` on the pointer listener: a click that lands on another row must close this
    // menu before that row's own handler opens a second one.
    document.addEventListener("mousedown", away, true);
    document.addEventListener("keydown", key);
    box.current?.querySelector<HTMLElement>("button:not([aria-disabled='true'])")?.focus();
    return () => {
      document.removeEventListener("mousedown", away, true);
      document.removeEventListener("keydown", key);
    };
  }, [onClose]);

  // Clamped to the viewport, so a right-click near the bottom right does not open a menu
  // half off the screen — the commonest place to right-click a long table is its last row.
  const height = items.length * 28 + 12;
  const x = Math.min(at.x, Math.max(0, window.innerWidth - MENU_WIDTH - 8));
  const y = Math.min(at.y, Math.max(0, window.innerHeight - height - 8));

  return (
    <div
      ref={box}
      data-testid="menu"
      role="menu"
      style={{ position: "fixed", left: x, top: y, width: MENU_WIDTH,
               boxShadow: "var(--e3)", zIndex: 50 }}
      className="py-1.5 bg-surface border border-line rounded-[var(--r)]"
    >
      {items.map((item) => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          aria-disabled={item.w4 || item.why || !item.onPick ? "true" : undefined}
          disabled={Boolean(item.w4 || item.why) || !item.onPick}
          onClick={() => { item.onPick?.(); onClose(); }}
          className={`w-full text-left px-3 py-1 bg-transparent border-0 text-body
                      flex items-baseline gap-2 cursor-pointer
                      ${item.separated ? "border-t border-line mt-1 pt-2" : ""}
                      ${item.w4 || item.why || !item.onPick
                        ? "text-ink-3 opacity-50 cursor-default"
                        : "text-ink hover:bg-[var(--hover)]"}`}
          style={{ transition: `background-color var(--t)` }}
        >
          {item.label}
          {(item.w4 || item.why) && (
            <span className="ml-auto text-label text-ink-3">{item.w4 ? "W4" : item.why}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/** Open a menu from a row, by pointer or by keyboard.
 *
 * **Shift+F10 and the ContextMenu key open it too** — §12.4. A gesture only a mouse can reach
 * is a gesture half the users do not have.
 */
export function useContextMenu() {
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  const close = useCallback(() => {
    setAt(null);
    // Focus goes back where it came from, or the reader loses their place in the table.
    opener.current?.focus();
    opener.current = null;
  }, []);

  const open = useCallback((event: { clientX: number; clientY: number;
                                     currentTarget: unknown; preventDefault: () => void }) => {
    event.preventDefault();
    opener.current = event.currentTarget as HTMLElement;
    setAt({ x: event.clientX, y: event.clientY });
  }, []);

  const bind = {
    onContextMenu: (event: React.MouseEvent<HTMLElement>) => {
      // **The browser's own menu survives on a text selection** — §12.3. Overriding
      // right-click everywhere steals Copy from people, which is worse than having no menu.
      if (!window.getSelection()?.isCollapsed) return;
      open(event);
    },
    onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => {
      if (event.key !== "ContextMenu" && !(event.key === "F10" && event.shiftKey)) return;
      event.preventDefault();
      const box = event.currentTarget.getBoundingClientRect();
      opener.current = event.currentTarget;
      setAt({ x: box.left + 24, y: box.top + box.height });
    },
    tabIndex: 0,
  };

  return { at, open, close, bind };
}

/** Put text on the clipboard. Every clipboard verb in §12.3's table goes through here, so
 *  there is one answer to *what happens when the clipboard is unavailable* — which it is on
 *  an insecure origin, and silently. */
export async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // A copy that cannot happen must not throw into a menu handler.
  }
}
