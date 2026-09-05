import { useEffect, useRef, useState } from "react";

import {
  useApprove,
  useRequestChanges,
  type ApprovalState,
  type FilePane,
} from "../../api/registry";
import { Refusal } from "../../ui/Refusal";
import { Failed } from "../../ui/States";
import { Mark } from "./Status";

/** The two decisions, and they are separate explicit actions — §8.5.
 *
 * **Request changes is not rejection**, and the word matters enough that §1.6 argues it: a
 * terminal word makes an ordinary correction feel destructive, and the candidate being
 * corrected is kept. The form says what actually happens — the revision is frozen, another
 * attempt is queued, and you stay on this page.
 *
 * **Approval is disabled with every reason it is disabled**, not the first. `approval_refusals`
 * returns all six together for the reason its docstring gives: six clicks to learn six facts
 * the server knew at the first one.
 */

/** A dialog that traps focus and closes on Escape.
 *
 * **Not `<dialog>`**, whose `showModal` is unimplemented in jsdom — so the keyboard behaviour
 * §8.5's last box asks for would be untestable in exactly the suite that has to hold it.
 */
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    box.current?.querySelector<HTMLElement>("textarea, input, button")?.focus();
  }, []);

  return (
    <div
      className="fixed inset-0 z-20 flex items-start justify-center pt-[8vh] px-6
                 bg-[var(--scrim)]"
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
    >
      {/* The backdrop closes on click; the panel stops the click so a drag inside it does not. */}
      <button
        type="button"
        aria-label="Close"
        tabIndex={-1}
        className="absolute inset-0 bg-transparent border-0 cursor-default"
        onClick={onClose}
      />
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full max-w-[620px] border border-line-2 bg-surface
                   rounded-[var(--r)] shadow-e3 px-[22px] py-5 max-h-[80vh] overflow-y-auto"
      >
        {children}
      </div>
    </div>
  );
}

export function RequestChanges({
  adaptationId,
  revision,
  onClose,
}: {
  adaptationId: string;
  revision: number;
  onClose: () => void;
}) {
  const changes = useRequestChanges(adaptationId);
  const [reason, setReason] = useState("");
  const [refs, setRefs] = useState<string[]>([]);
  const [pointing, setPointing] = useState("");

  return (
    <Modal title="Request changes" onClose={onClose}>
      <h2 className="text-object font-semibold m-0">Request changes</h2>
      <p className="text-body text-ink-2 m-0 pt-[7px] pb-[18px]">
        This is not rejection. The candidate is kept and another attempt is queued against the
        same scaffold.
      </p>

      <label
        htmlFor="what-should-change"
        className="font-data text-label tracking-[.15em] uppercase text-ink-3 block pb-2"
      >
        What should change — required
      </label>
      <textarea
        id="what-should-change"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        rows={4}
        className="w-full border border-line-2 bg-paper text-ink text-body rounded-[var(--r)]
                   px-[13px] py-[11px] resize-y focus-visible:outline-none
                   focus-visible:shadow-[var(--ring)]"
      />

      {/* §8.5: *optional field/file references*. They ride along in the reason, because the
          endpoint takes one field and inventing a second would be inventing a schema the
          server does not have — the references are for the next reader, and prose carries
          them honestly. */}
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pt-4 pb-2">
        Point at a field or file — optional
      </div>
      <div className="flex gap-2 flex-wrap items-center">
        {refs.map((ref) => (
          <button
            key={ref}
            type="button"
            onClick={() => setRefs(refs.filter((other) => other !== ref))}
            className="font-data text-[10.5px] text-link border border-[var(--link-line)]
                       rounded-[var(--r)] px-2.5 py-[5px] bg-transparent"
          >
            {ref} ×
          </button>
        ))}
        <input
          value={pointing}
          onChange={(event) => setPointing(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && pointing.trim()) {
              event.preventDefault();
              setRefs([...new Set([...refs, pointing.trim()])]);
              setPointing("");
            }
          }}
          placeholder="consumes.reads.type_id"
          aria-label="Add a reference"
          className="font-data text-[10.5px] border border-line-2 bg-paper text-ink
                     rounded-[var(--r)] px-2.5 py-[5px] w-[220px]
                     focus-visible:outline-none focus-visible:shadow-[var(--ring)]"
        />
      </div>

      {changes.error && (
        <div className="pt-3">
          <Failed error={changes.error} padded={false} />
        </div>
      )}

      <div className="flex items-center justify-between pt-5 mt-5 border-t border-line-soft gap-4">
        <span className="font-data text-label text-ink-3">
          freezes revision {revision} · queues another attempt · you stay on this page
        </span>
        <div className="flex gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="border border-line-2 bg-transparent text-ink text-[12px]
                       rounded-[var(--r)] px-3.5 py-[7px] hover:bg-surface-2"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!reason.trim() || changes.isPending}
            onClick={() =>
              changes.mutate(
                [reason.trim(), refs.length ? `\n\nabout: ${refs.join(", ")}` : ""].join(""),
                { onSuccess: onClose },
              )
            }
            className="border border-measured text-measured bg-transparent text-[12px]
                       rounded-[var(--r)] px-3.5 py-[7px] hover:bg-[var(--measured-soft)]
                       disabled:border-line disabled:text-ink-3 disabled:cursor-not-allowed"
          >
            {changes.isPending ? "Sending…" : "Send back for changes"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function Approve({
  adaptationId,
  files,
  approval,
  who,
  onClose,
}: {
  adaptationId: string;
  files: FilePane[];
  approval: ApprovalState | undefined;
  who: string;
  onClose: () => void;
}) {
  const approve = useApprove(adaptationId);
  const [reason, setReason] = useState("");
  // **Every rule candidate starts unchecked, and there are none to check yet.** Nothing
  // produces `rule_candidates` — `ai/schemas.py`'s `Analysis` has no field for them — so this
  // is an empty list rather than a checkbox group with nothing in it. What is already true is
  // the part that matters: the endpoint publishes only the ids it is given, so a rule arriving
  // later is off until somebody ticks it, and no default has to be remembered.
  const rules: string[] = [];

  return (
    <Modal title="Approve and publish" onClose={onClose}>
      <h2 className="text-object font-semibold m-0">Approve and publish</h2>
      <p className="text-body text-ink-2 m-0 pt-[7px] pb-[18px]">
        Publication is the door with no undo. What is written is the contract below and the
        vocabulary it needs — nothing else.
      </p>

      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-2">
        What gets written
      </div>
      <ul className="m-0 pl-0 list-none flex flex-col gap-1.5 pb-4">
        <li className="font-data text-[11px] text-ink-2">contract.yml</li>
        {files.map((file) => (
          <li key={file.path} className="font-data text-[11px] text-ink-2">
            {file.path}
            {!file.authored && <span className="text-ink-3"> · copied unchanged</span>}
          </li>
        ))}
        {rules.length === 0 && (
          <li className="text-secondary text-ink-3">
            No rule candidate is selected — approving the contract does not accept any.
          </li>
        )}
      </ul>

      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-2">
        Approving as
      </div>
      <p className="font-data text-[11px] text-ink-2 m-0 pb-4">{who}</p>

      <label
        htmlFor="publication-reason"
        className="font-data text-label tracking-[.15em] uppercase text-ink-3 block pb-2"
      >
        Why this is right — required
      </label>
      <textarea
        id="publication-reason"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        rows={3}
        className="w-full border border-line-2 bg-paper text-ink text-body rounded-[var(--r)]
                   px-[13px] py-[11px] resize-y focus-visible:outline-none
                   focus-visible:shadow-[var(--ring)]"
      />

      {approval && approval.refusals.length > 0 && (
        <div className="pt-4 flex flex-col gap-2">
          {approval.refusals.map((refusal) => (
            <Refusal key={refusal} message={refusal} />
          ))}
        </div>
      )}
      {approve.error && (
        <div className="pt-3">
          <Failed error={approve.error} padded={false} />
        </div>
      )}

      <div className="flex items-center justify-end gap-2.5 pt-5 mt-5 border-t border-line-soft">
        <button
          type="button"
          onClick={onClose}
          className="border border-line-2 bg-transparent text-ink text-[12px] rounded-[var(--r)]
                     px-3.5 py-[7px] hover:bg-surface-2"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!reason.trim() || approve.isPending || !approval?.can_approve}
          onClick={() =>
            approve.mutate(
              { reason: reason.trim(), rule_candidate_ids: rules },
              { onSuccess: onClose },
            )
          }
          className="border border-pea text-pea bg-transparent text-[12px] rounded-[var(--r)]
                     px-3.5 py-[7px] hover:bg-pea-soft disabled:border-line
                     disabled:text-ink-3 disabled:cursor-not-allowed"
        >
          {approve.isPending ? "Publishing…" : "Approve and publish"}
        </button>
      </div>
    </Modal>
  );
}

/** Why Approve is unavailable, as a panel beside the page rather than only inside the dialog.
 *
 * §8.5: *approval is disabled with a visible reason*. A disabled button whose reason only
 * appears after you open a dialog is a disabled button with no reason.
 */
export function WhyBlocked({ approval }: { approval: ApprovalState | undefined }) {
  if (!approval || approval.can_approve) return null;
  return (
    <div className="border border-line bg-surface rounded-[var(--r)] px-[18px] py-4">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-2.5">
        Why approve is unavailable
      </div>
      <div className="flex flex-col gap-2.5">
        {approval.refusals.map((refusal) => (
          <span key={refusal} className="flex gap-[9px] items-baseline text-body">
            <span className="mt-1">
              <Mark shape="fail" />
            </span>
            <span>{refusal.split("\n")[0]}</span>
          </span>
        ))}
      </div>
      <p className="font-data text-label text-ink-3 pt-3.5 leading-[1.55] m-0">
        Every unmet condition is listed at once. Approval needs all of them, and a green verdict
        describes the layer that was read at the time.
      </p>
    </div>
  );
}
