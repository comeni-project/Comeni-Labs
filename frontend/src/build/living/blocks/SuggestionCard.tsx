import type { AuthoringSuggestion } from "../../../api/types";
import { Primary, Secondary } from "./parts";

/** A change the model offered and the person has not yet taken (Part I.0 §5.3).
 *
 * **One click applies it, as the person's own change**; nothing moves until then. It says whose
 * reading it is: *suggested by AI* when the model did not quote them, or the words it heard when
 * it did but the goal was already confirmed — every change mid-build is shown before it applies.
 * A value against what the sample measured is a question, *are you sure?*, answered Yes or No
 * (#345): Yes records what they said.
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
  const asks = suggestion.measured != null;
  return (
    <div data-testid="suggestion" className="flex items-center gap-3 px-[10px] py-2 border"
         style={{ borderColor: "var(--line-2)" }}>
      <div className="flex-1 min-w-0">
        <p className="m-0 text-[12.5px] text-ink">{suggestion.says}</p>
        <p className="m-0 font-data text-[9.5px] text-ink-4">
          {suggestion.heard && suggestion.quote ? `you said "${suggestion.quote}"`
            : "suggested by AI"}
        </p>
      </div>
      <Primary disabled={busy} onClick={() => onApply(suggestion.id)}>{asks ? "Yes" : "Apply"}</Primary>
      <Secondary disabled={busy} onClick={() => onDismiss(suggestion.id)}>
        {asks ? "No" : "Dismiss"}
      </Secondary>
    </div>
  );
}
