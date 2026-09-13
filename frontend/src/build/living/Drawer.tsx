import { useEffect, useRef } from "react";

/** A contextual overlay — the YAML, validation findings — over the canvas, never beside it.
 *
 * **Focus goes in when it opens and back where it came from when it closes.** A drawer that drops
 * focus on the body sends a keyboard user to the top of the page, which on a page this dense is
 * the same as losing their place. Escape closes it.
 */
export function Drawer({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    opener.current = document.activeElement;
    panel.current?.focus();
    return () => {
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
  }, []);

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={title}
      tabIndex={-1}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
      className="absolute inset-0 z-20 flex flex-col outline-none"
      style={{ background: "var(--scrim)" }}
    >
      <div className="m-4 flex flex-col min-h-0 flex-1 border"
           style={{ background: "var(--paper-2)", borderColor: "var(--line-2)" }}>
        <header className="flex items-center justify-between px-4 py-3"
                style={{ borderBottom: "1px solid var(--line)" }}>
          <span className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3">{title}</span>
          <button type="button" data-testid="drawer-close" onClick={onClose}
                  className="bg-transparent border-0 text-ink-2 cursor-pointer text-[12.5px]
                             focus-visible:shadow-[var(--ring)]">
            Close
          </button>
        </header>
        <div className="flex-1 min-h-0 overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}
