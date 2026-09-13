/** Where a person says something. Square, a chevron, and the text.
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
      className="flex items-center gap-[10px] px-[13px] py-[11px] border"
      style={{ background: "var(--paper-2)", borderColor: "var(--link-line)" }}
    >
      <span aria-hidden className="text-link text-[13px]">›</span>
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
        className="flex-1 min-w-0 resize-none bg-transparent border-0 outline-none text-[13px]
                   text-ink placeholder:text-ink-3 [field-sizing:content] max-h-[120px]"
      />
    </form>
  );
}
