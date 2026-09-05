import { useState } from "react";

/** A one-line decision that the API requires a reason for.
 *
 * **Every state-changing forge request carries a reason and it is the only field**, which is
 * `routes/forge.py`'s own rule — so a button that sent a constant would be filling in the audit
 * trail on the reviewer's behalf. "retried from the work queue" answers nothing the timestamp
 * beside it did not.
 *
 * A row rather than a dialog, because retry and archive are one-line decisions: a modal for
 * each is two modals a reviewer dismisses without reading, which is how a required field
 * becomes a formality.
 */
export function ReasonButton({
  label,
  placeholder,
  tone = "neutral",
  busy,
  onSend,
}: {
  label: string;
  placeholder: string;
  tone?: "neutral" | "warn";
  busy: boolean;
  onSend: (reason: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  const border = tone === "warn" ? "border-measured text-measured" : "border-line-2 text-ink";

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`border bg-transparent text-[12px] rounded-[var(--r)] px-3.5 py-[7px]
                    hover:bg-surface-2 ${border}`}
      >
        {label}
      </button>
    );
  }

  return (
    <span className="flex items-center gap-2">
      <input
        autoFocus
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
          if (event.key === "Enter" && reason.trim()) onSend(reason.trim());
        }}
        placeholder={placeholder}
        aria-label={placeholder}
        className="border border-line-2 bg-surface text-ink text-secondary rounded-[var(--r)]
                   px-2.5 py-1.5 w-[240px] focus-visible:outline-none
                   focus-visible:shadow-[var(--ring)]"
      />
      <button
        type="button"
        disabled={!reason.trim() || busy}
        onClick={() => onSend(reason.trim())}
        className="font-data text-label tracking-[.08em] uppercase border border-pea text-pea
                   rounded-[var(--r)] px-[11px] py-[6px] bg-transparent hover:bg-pea-soft
                   disabled:border-line disabled:text-ink-3 disabled:cursor-not-allowed"
      >
        {busy ? "…" : "Go"}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="font-data text-label tracking-[.08em] uppercase text-ink-3 hover:text-ink
                   bg-transparent border-0 cursor-pointer"
      >
        Cancel
      </button>
    </span>
  );
}
