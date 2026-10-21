/** Where a person says something: a rounded field and a Send button, as the *Build* board draws it.
 *
 * **Enter sends; Shift+Enter is a new line.** The half-typed text is the reducer's `composer`,
 * which is component state and allowed to vanish on reload — the durable record is the transcript
 * on the server, never a copy in the browser.
 */
export function Composer({
  value,
  onChange,
  onSend,
  disabled = false,
  placeholder = "Ask about a step, or say what to change",
}: {
  value: string;
  onChange: (text: string) => void;
  onSend: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const send = () => {
    const text = value.trim();
    if (text && !disabled) onSend(text);
  };

  return (
    <form
      aria-label="say something"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className="flex items-end gap-[10px] pl-[14px] pr-[8px] py-[8px] border rounded-panel
                 focus-within:border-[var(--now)] focus-within:shadow-[0_0_0_3px_var(--now-soft)]"
      style={{ background: "var(--surface)", borderColor: "var(--line-2)" }}
    >
      <textarea
        data-testid="composer"
        aria-label={placeholder}
        rows={1}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        className="flex-1 min-w-0 self-center resize-none bg-transparent border-0 outline-none text-[14px]
                   leading-[1.45] py-[4px] text-ink placeholder:text-ink-3 [field-sizing:content] max-h-[120px]"
      />
      <button type="submit" aria-label="Send" disabled={disabled || value.trim() === ""}
              className="shrink-0 grid place-items-center w-[32px] h-[32px] p-0 rounded-control border-0
                         cursor-pointer text-ink-2 enabled:hover:text-now-ink disabled:cursor-not-allowed
                         disabled:opacity-50 focus-visible:shadow-[var(--ring)]"
              style={{ background: "var(--line-soft)" }}>
        <svg aria-hidden width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor"
             strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
          <path d="M14.5 1.5 7 9M14.5 1.5 10 14.5 7 9 1.5 6z" />
        </svg>
      </button>
    </form>
  );
}
