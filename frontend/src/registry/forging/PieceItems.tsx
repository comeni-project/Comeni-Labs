import { useState } from "react";

import { Failed } from "../../ui/States";
import { ItemConstructor } from "./ItemConstructor";
import { asked, QuestionList } from "./QuestionCards";
import { RulePreview } from "./RulePreview";
import { ValueDetails } from "./ValueDetails";
import { ReviewComment, type Review } from "./Reviews";
import { nameOf, type ItemView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

type Actions = ReturnType<typeof useForgeActions>;

const button = "control";
const primary = "control-primary";

/** What an item's value says in one line: a setting's default and route, a port's type. */
function summary(item: ItemView): string {
  return summaryOf(item.key, item.value);
}

/** A value in a line, never as JSON: the chat's proposals read the same as the items. */
export function summaryOf(key: string, value: unknown): string {
  const item = { key, value };
  const v = value as Record<string, unknown> | null;
  if (!v || typeof v !== "object") return v === null ? "" : String(v);
  if ("type_id" in v) return String(v.type_id);
  if ("expect" in v) {
    const feeds = Object.keys(v.inputs as object).join(", ") || "setup";
    return `${feeds} → ${(v.expect as { pattern: string }[]).map((e) => e.pattern).join(", ")}`;
  }
  if ("choice" in v) return String(v.choice);
  if ("asks" in v) return String(v.asks);
  if (item.key.startsWith("parameters:param:")) {
    const value = v.tier_hint === 4 && v.default == null ? "asks the person" : `default ${JSON.stringify(v.default)}`;
    return `${value} · ${v.via ?? ""}${v.key ? ` · ${v.key}` : ""}`;
  }
  if (Array.isArray(item.value)) {
    // The wiring: each input channel in order, by its ports or its setting.
    return (item.value as { ports?: string[]; param?: string }[])
      .map((i) => (i.ports?.length ? i.ports.join("+") : i.param) || "—").join(" · ");
  }
  if ("nf_process" in v) return `${v.nf_process} · ${(v.roles as string[] | undefined)?.join(", ") ?? ""}`;
  if ("template" in v) return String(v.template);
  if ("decides" in v) return `decides ${(v.decides as { of?: string }).of ?? ""}`;
  if ("id" in v) return String(v.id);
  if ("because" in v) return String(v.because);
  return "Declared details below";
}

/** A proposed removal carries no value of its own: approving it removes the item. */
function removing(item: ItemView): boolean {
  return item.status === "proposed" && item.revisions.at(-1)?.move === "propose_removal";
}

const STATUS: Record<string, { label: string; tone: string }> = {
  proposed: { label: "waiting for you", tone: "text-measured-ink" },
  approved: { label: "Approved", tone: "text-done-ink" },
  rejected: { label: "Rejected by you", tone: "text-needs-you-ink" },
  removed: { label: "Removed", tone: "text-ink-3" },
  reopened: { label: "Re-opened: approve again", tone: "text-measured-ink" },
};

/** The current piece's items (boards 3, 3c): value, how it is passed, the reason, who
 *  proposed it, and the person's moves. Change opens the same constructor used to write an item. */
export function PieceItems({ id, items, reviews = [], actions, onReject, focus }: {
  id: string;
  reviews?: Review[];
  items: ItemView[];
  actions: Actions;
  onReject: (key: string) => void;
  focus?: string | null;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const open = items.filter((i) => i.status === "proposed" || i.status === "reopened");
  // Each of these is a decision of its own: a question wants an answer, a removal a second look.
  const rest = open.filter((i) => !asked(i) && !removing(i));

  const ordered = [...items].sort((a, b) => {
    const rank = (i: ItemView) => i.key === "questions:role" ? 0
      : i.key.startsWith("questions:input_type:") ? 1
      : i.key.startsWith("questions:output_type:") ? 2 : i.piece === "questions" ? 3 : 4;
    return rank(a) - rank(b);
  });
  const questions = ordered.filter((i) => i.piece === "questions");
  return (
    <div>
      {questions.length > 0 && <QuestionList id={id} items={questions} reviews={reviews}
        actions={actions} onReject={onReject} focus={focus} />}
      {ordered.filter((i) => i.piece !== "questions").map((item) => {
        const current = item.revisions.at(-1);
        const supplied = item.revisions.findLast((r) =>
          ["draft", "revise", "add", "answer", "write", "change"].includes(r.move));
        const author = supplied?.actor === "ai" ? "proposed by the AI"
          : supplied?.actor === "registry" ? "from the registry" : "written by you";
        const waiting = item.status === "proposed" || item.status === "reopened";
        return (
          <div key={item.key} role="group" aria-label={nameOf(item.key)} data-item={item.key}
               className="grid grid-cols-1 sm:grid-cols-[minmax(0,190px)_minmax(0,1fr)] gap-x-4 gap-y-2 items-start px-[22px] py-4 border-t border-line-soft">
            <div>
              <div className="font-data font-medium break-words">{item.key.includes(":input") ? "Input · " : item.key.includes(":output") ? "Output · " : ""}{nameOf(item.key)}</div>
              <div className="font-data text-[12.5px] text-ink-2 break-words">{summary(item)}</div>
              <div className="text-[12px] text-ink-3">{author}</div>
            </div>
            <div className="min-w-0 text-[13.5px] text-ink-2 leading-[1.55]">
              {editing === item.key ? (
                <ItemConstructor id={id} piece={item.piece} items={items} item={item} actions={actions}
                                 onCancel={() => setEditing(null)} />
              ) : (
                <>
                  <ValueDetails value={item.value} />
                  {item.key.startsWith("rules:rule:") && !["removed", "rejected"].includes(item.status)
                    && <RulePreview key={`${item.key}:${item.current_n}`} id={id} item={item} />}
                  {current?.because ?? ""}
                  <span className={`block mt-1 text-[12.5px] ${removing(item) ? "text-needs-you-ink" : STATUS[item.status]?.tone ?? ""}`}>
                    {removing(item) ? "The AI proposes removing this" : STATUS[item.status]?.label}
                  </span>
                </>
              )}
              {reviews.filter((r) => r.item === item.key && r.revision === item.current_n && r.comment)
                .map((r) => <ReviewComment key={r.item} review={r} />)}
            </div>
            <div className="flex flex-wrap gap-[6px] sm:col-start-2 sm:justify-end [&>button]:flex-1 sm:[&>button]:flex-none">
              {waiting && editing !== item.key && (
                <button type="button" className={primary} disabled={actions.command.isPending}
                        aria-busy={actions.command.isPending}
                        onClick={() => actions.command.mutate({ move: "approve", item: item.key,
                                                                expected: item.current_n })}>
                  Approve
                </button>
              )}
              {item.status !== "removed" && editing !== item.key && (
                <button type="button" className={button}
                        onClick={() => setEditing(item.key)}>
                  Change
                </button>
              )}
              {waiting && (
                <button type="button" disabled={actions.command.isPending} className={`${button} text-needs-you-ink`}
                        onClick={() => { actions.command.mutate({ move: "reject", item: item.key,
                                                                   expected: item.current_n });
                                         onReject(item.key); }}>
                  Reject
                </button>
              )}
            </div>
          </div>
        );
      })}
      {actions.command.isError && <div className="px-[22px] py-3"><Failed error={actions.command.error} padded={false} /></div>}
      {rest.length > 1 && (
        <div className="flex justify-between items-center gap-3 px-[22px] py-4 border-t border-line bg-paper-2">
          <span className="text-[13px] text-ink-3">{open.length} items still need you</span>
          <button type="button" disabled={actions.command.isPending} className={primary}
                  onClick={() => rest.forEach((i) => actions.command.mutate({
                    move: "approve", item: i.key, expected: i.current_n }))}>
            Approve the rest
          </button>
        </div>
      )}
    </div>
  );
}

/** A person writes through the same value models and checks as a model draft. */
export function WriteItem({ id, piece, items, actions }: {
  id: string;
  piece: string;
  items: ItemView[];
  actions: Actions;
}) {
  return <div className="px-[22px] py-4"><ItemConstructor id={id} piece={piece} items={items} actions={actions} /></div>;
}
