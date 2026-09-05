import { useState } from "react";

import { useAsk, useConversation, type Citation } from "../../api/registry";
import { Failed } from "../../ui/States";
import { Mark } from "./Status";

/** The review chat — part of review, not a floating support widget (§8.5).
 *
 * **It is read-only with respect to the candidate, and the interface says so rather than
 * relying on it being true.** `forge_review.py` moves no adaptation and writes no file, and the
 * composer's own line — *asking does not change the candidate* — is what stops a curator
 * expecting a question to fix something. A chat that could edit files would be a chat that can
 * approve one.
 *
 * **This is egress door 5.** What a curator types here is free text written at request time and
 * sent to a provider, which is the leg the forge's 2026-08-17 exemption stood on. The 4,000
 * character bound is the server's; the counter here exists so somebody pasting a file finds out
 * before they press Ask rather than after.
 *
 * **A pending turn is drawn immediately.** §7: a curator who sees nothing until an answer
 * arrives cannot tell *sent* from *lost*, and at 227 seconds they retype it.
 */

const MAX = 4000;

function Cite({ citation, onEvidence }: { citation: Citation; onEvidence: (id: string) => void }) {
  const label = citation.evidence_id
    ? citation.evidence_id
    : `${citation.file}${citation.line ? `:${citation.line}` : ""}`;
  return (
    <button
      type="button"
      onClick={() => citation.evidence_id && onEvidence(citation.evidence_id)}
      title={citation.kind.replace("_", " ")}
      className="font-data text-[10px] text-link border border-[var(--link-line)]
                 rounded-[var(--r)] px-2 py-[3px] bg-transparent hover:bg-[var(--link-soft)]"
    >
      {label}
    </button>
  );
}

export function ReviewChat({
  adaptationId,
  onEvidence,
}: {
  adaptationId: string;
  onEvidence: (id: string) => void;
}) {
  const { data: turns, error } = useConversation(adaptationId);
  const ask = useAsk(adaptationId);
  const [draft, setDraft] = useState("");

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    ask.mutate(text, { onSuccess: () => setDraft("") });
  };

  return (
    <aside className="border border-line bg-surface rounded-[var(--r)] flex flex-col">
      <div className="px-4 pt-3.5">
        <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-1">
          Ask about this revision
        </div>
      </div>

      <div className="px-4 flex-1 min-h-0 overflow-y-auto max-h-[420px]">
        {error && <Failed error={error} padded={false} />}
        {turns?.length === 0 && (
          <p className="text-body text-ink-3 py-3 m-0">
            Nothing asked yet. Answers are grounded on this revision and its evidence — the
            model reads the candidate, and cannot change it.
          </p>
        )}
        {turns?.map((turn) => (
          <div key={turn.id} className="py-[11px] border-b border-line-soft">
            <div
              className={`font-data text-[9.5px] tracking-[.14em] uppercase pb-[5px] ${
                turn.role === "curator" ? "text-ink-3" : "text-link"
              }`}
            >
              {turn.role === "curator" ? "You" : "Assistant"}
            </div>
            {turn.state === "pending" ? (
              /* The receipt. It says *queued*, not *thinking* — nothing is streamed here, and
                 §8.4's rule against faking model thoughts applies to the rail too. */
              <div className="flex items-center gap-2">
                <Mark shape="run" />
                <span className="font-data text-[10.5px] text-ink-3">
                  {turn.content ? "queued — waiting for the AI lane" : "queued"}
                </span>
              </div>
            ) : null}
            {turn.content && (
              <div
                className={`text-body leading-[1.55] ${
                  turn.role === "curator" ? "text-ink" : "text-ink-2"
                } ${turn.state === "pending" ? "pt-1.5" : ""}`}
              >
                {turn.content}
              </div>
            )}
            {turn.state === "failed" && (
              <div className="flex items-center gap-2 pt-1.5">
                <Mark shape="fail" />
                <span className="font-data text-[10.5px] text-fault">
                  the answer did not arrive — ask again
                </span>
              </div>
            )}
            {turn.citations.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-2">
                {turn.citations.map((citation, i) => (
                  <Cite
                    key={`${citation.evidence_id}${citation.file}${i}`}
                    citation={citation}
                    onEvidence={onEvidence}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="px-4 pt-3 pb-4">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value.slice(0, MAX))}
          // **Enter sends, Shift+Enter breaks a line.** A review question is usually one
          // sentence, and a textarea whose only send is a mouse trip is one people stop using.
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          placeholder="Ask about this revision…"
          aria-label="Ask about this revision"
          rows={3}
          className="w-full border border-line-2 bg-paper text-ink text-body rounded-[var(--r)]
                     px-[11px] py-[9px] resize-y placeholder:text-ink-3
                     focus-visible:outline-none focus-visible:shadow-[var(--ring)]"
        />
        {ask.error && (
          <div className="pt-2">
            <Failed error={ask.error} padded={false} />
          </div>
        )}
        <div className="flex items-center justify-between pt-2.5">
          <span className="font-data text-label text-ink-3">
            {draft.length > MAX - 400
              ? `${MAX - draft.length} characters left`
              : "asking does not change the candidate"}
          </span>
          <button
            type="button"
            onClick={send}
            disabled={!draft.trim() || ask.isPending}
            className="border border-line-2 bg-transparent text-ink text-[11.5px]
                       rounded-[var(--r)] px-3.5 py-[5px] hover:bg-surface-2
                       disabled:text-ink-3 disabled:border-line disabled:cursor-not-allowed"
          >
            {ask.isPending ? "Sending…" : "Ask"}
          </button>
        </div>
      </div>
    </aside>
  );
}
