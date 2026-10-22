import type { AuthoringSuggestion } from "../../../api/types";
import { Primary, Secondary } from "./parts";

/** A change the model offered and the person has not yet taken (Part I.0 §5.3).
 *
 * **One click applies it, as the person's own change**; nothing moves until then. It says whose
 * reading it is: *suggested by AI* when the model did not quote them, or the words it heard when
 * it did but the goal was already confirmed — every change mid-build is shown before it applies.
 * A value against what the sample measured is a question, *are you sure?*, answered Yes or No
 * (issue 345): Yes records what they said.
 *
 * **A hand edit, read by the engine** (one builder, #395), is a card too: *from your edit*, the
 * engine's sentence, and *Yes* / *No, undo*. One card per edit (`byEdit`) — the server takes or
 * sets aside every reading of it together.
 */
export function SuggestionCard({
  suggestion,
  busy,
  onApply,
  onDismiss,
}: {
  suggestion: AuthoringSuggestion;
  busy: boolean;
  onApply: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const read = suggestion.edit != null;
  const asks = read || suggestion.measured != null;
  return (
    <div data-testid="suggestion" className="flex items-center gap-3 px-[10px] py-2 border"
         style={{ borderColor: "var(--line-2)" }}>
      <div className="flex-1 min-w-0">
        <p className="m-0 text-[12.5px] text-ink">{suggestion.says}</p>
        <p className="m-0 font-data text-[9.5px] text-ink-3">
          {read ? "from your edit"
            : suggestion.heard && suggestion.quote ? `you said "${suggestion.quote}"`
            : "suggested by AI"}
        </p>
      </div>
      <Primary disabled={busy} onClick={() => onApply(suggestion.id)}>{asks ? "Yes" : "Apply"}</Primary>
      <Secondary disabled={busy} onClick={() => onDismiss(suggestion.id)}>
        {read ? "No, undo" : asks ? "No" : "Dismiss"}
      </Secondary>
    </div>
  );
}

/** The waiting readings of hand edits, one per edit (its first, which carries the sentence), and
 *  the model's suggestions. */
export function byEdit(all: AuthoringSuggestion[]) {
  const seen = new Set<string>();
  const readings = all.filter((s) => s.edit != null && !seen.has(s.edit) && seen.add(s.edit));
  return { readings, suggestions: all.filter((s) => s.edit == null) };
}
