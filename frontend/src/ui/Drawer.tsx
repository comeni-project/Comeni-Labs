import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** A panel over the page from the right (the assistant overlay, #511). The page underneath keeps
 *  its state; Escape closes it and focus goes back to whatever opened it. */
export function Drawer({ open, onClose, label, children }: {
  open: boolean;
  onClose: () => void;
  label: string;
  children: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  // **Held in a ref, so a page that passes a new `onClose` each render does not reopen the
  // drawer**: the effect runs on opening and closing only, and focus stays where the person is
  // typing while replies stream in (Checkpoint A).
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const first = panel.current?.querySelector<HTMLElement>(
      "input, textarea, button, [tabindex]:not([tabindex='-1'])");
    (first ?? panel.current)?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close.current(); };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (opener?.isConnected) opener.focus();
    };
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div ref={panel} role="dialog" aria-label={label} tabIndex={-1}
         className="fixed right-4 top-4 bottom-4 z-30 w-[min(400px,calc(100vw-32px))] flex flex-col bg-surface
                    border border-line rounded-panel shadow-e3 overflow-hidden outline-none">
      {children}
    </div>,
    document.body,
  );
}
