import { useId, useState } from "react";

import { nameOf, type ItemView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

/** Removing a false premise is a separate recorded decision from rejecting a proposal. */
export function QuestionRemoval({ item, actions, onClose }: {
  item: ItemView; actions: ReturnType<typeof useForgeActions>; onClose: () => void;
}) {
  const id = useId();
  const [expected] = useState(item.current_n);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  return <form aria-label={`Remove ${nameOf(item.key)} question`} className="mt-3 flex flex-col gap-2"
    onSubmit={async (e) => {
      e.preventDefault();
      if (!reason.trim() || saving) return;
      setSaving(true); setError("");
      try {
        await actions.command.mutateAsync({ move: "remove", item: item.key, expected,
          because: reason.trim() });
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally { setSaving(false); }
    }}>
    <p className="m-0 text-[13px]">Remove only if this question does not apply. Its wording, answers and your reason stay in the history.</p>
    <fieldset disabled={saving} className="border-0 m-0 p-0 min-w-0 flex flex-col gap-2">
      <label htmlFor={id}>Why does this question not apply?</label>
      <textarea id={id} required rows={2} value={reason} onChange={(e) => setReason(e.target.value)}
        className="w-full min-w-0 bg-surface text-ink p-2 border border-line-2 rounded-control" />
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="control" disabled={saving || !reason.trim()} aria-busy={saving}>
          {saving ? "Removing…" : "Remove question"}
        </button>
        <button type="button" className="control" onClick={onClose}>Cancel</button>
      </div>
    </fieldset>
    {error && <p role="alert" className="m-0 text-needs-you-ink">{error}</p>}
  </form>;
}
