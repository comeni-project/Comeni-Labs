import { useEffect, useId, useRef, useState } from "react";

/** The ⓘ beside a setting: what it is, and why it is greyed out (spec §5).
 *
 * **A toggletip, not a hover tooltip.** A touch screen has no hover and a keyboard cannot reach
 * one, so it opens on click, tap or Enter and closes on Escape or a click elsewhere. The words
 * are the API's: `help` from the declaration, `reason` from the closed list of reasons.
 */
export function Help({
  label, help, reason, locked = true,
}: { label: string; help: string; reason?: string | null; locked?: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const box = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    // **In the capture phase, and marked**: inside the settings overlay one Escape closes this
    // note and not the overlay, which closes only on an Escape nobody used.
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape, true);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape, true);
    };
  }, [open]);

  return (
    <span ref={box} className="inline-block">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="bg-transparent text-ink-3 hover:text-ink cursor-pointer text-secondary px-[4px]"
      >
        ⓘ
      </button>
      {open && (
        <span
          id={id}
          role="note"
          // **Anchored to the row, not to the ⓘ** (review I-5): the row is `relative`, so the
          // note spans its width and cannot run past a 390px screen.
          className="absolute left-0 right-0 top-full z-10 mt-[4px]
                     border border-line bg-surface p-[12px] text-secondary text-ink shadow-lg"
        >
          <span className="block">{help}</span>
          {reason && (
            <span className="block mt-[8px] text-ink-2">
              {/* Only a locked setting is greyed; an unlocked one can carry a note (review I-4). */}
              {locked && <strong>Why it is greyed out: </strong>}
              {reason}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
