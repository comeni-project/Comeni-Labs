import { useEffect, useId, useRef, useState } from "react";

/** The ⓘ beside a setting: what it is, and why it is greyed out (spec §5).
 *
 * **A toggletip, not a hover tooltip.** A touch screen has no hover and a keyboard cannot reach
 * one, so it opens on click, tap or Enter and closes on Escape or a click elsewhere. The words
 * are the API's: `help` from the declaration, `reason` from the closed list of reasons.
 */
export function Help({ label, help, reason }: { label: string; help: string; reason?: string | null }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const box = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <span ref={box} className="relative inline-block">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="bg-transparent text-ink-3 hover:text-ink cursor-pointer text-secondary px-1"
      >
        ⓘ
      </button>
      {open && (
        <span
          id={id}
          role="note"
          className="absolute left-0 top-full z-10 mt-1 w-[300px] max-w-[calc(100vw-32px)]
                     border border-line bg-surface p-3 text-secondary text-ink shadow-lg"
        >
          <span className="block">{help}</span>
          {reason && (
            <span className="block mt-2 text-ink-2">
              <strong>Why it is greyed out:</strong> {reason}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
