import { useState } from "react";

import { Failed } from "../../ui/States";
import { nameOf, type ItemView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

type Actions = ReturnType<typeof useForgeActions>;

const button = "px-3 py-[7px] rounded-control border border-line-2 bg-surface text-[13px]";
const primary = "px-3 py-[7px] rounded-control bg-action text-on-action text-[13px] font-semibold shadow-raise";

/** What an item's value says in one line: a setting's default and route, a port's type. */
function summary(item: ItemView): string {
  const v = item.value as Record<string, unknown> | null;
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
  return JSON.stringify(v);
}

type Asked = { asks: string; suggested?: string | null; allows_new?: boolean;
                options: { id: string; label: string; because: string }[] };

/** The question an item asks, from its revisions: once answered, its value is the answer. */
function asked(item: ItemView): Asked | null {
  const found = item.revisions.findLast((r) => (r.value as Partial<Asked> | null)?.asks !== undefined);
  return found ? found.value as Asked : null;
}

/** A proposed removal carries no value of its own: approving it removes the item. */
function removing(item: ItemView): boolean {
  return item.status === "proposed" && item.revisions.at(-1)?.move === "propose_removal";
}

/** A question is answered, never approved: its options, the AI's suggestion marked but not
 *  chosen, and a name of the person's own where the question allows one. */
function Answer({ item, question, actions }: { item: ItemView; question: Asked; actions: Actions }) {
  const [own, setOwn] = useState("");
  const chosen = (item.value as { choice?: string } | null)?.choice;
  const answer = (value: { choice: string; new?: boolean }) =>
    actions.command.mutate({ move: "answer", item: item.key, expected: item.current_n, value });
  return (
    <div className="flex flex-col gap-2">
      <ul className="list-none m-0 p-0 flex flex-col gap-[6px]">
        {question.options.map((o) => (
          <li key={o.id}>
            <button type="button" aria-pressed={chosen === o.id} onClick={() => answer({ choice: o.id })}
                    className={`${button} text-left w-full ${chosen === o.id ? "border-action" : ""}`}>
              <span className="font-medium text-ink">{o.label}</span>
              {question.suggested === o.id && <span className="ml-2 text-[12px] text-measured-ink">suggested</span>}
              <span className="block text-[12.5px] text-ink-2">{o.because}</span>
            </button>
          </li>
        ))}
      </ul>
      {question.allows_new !== false && (
        <form className="flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          if (own.trim()) answer({ choice: own.trim(), new: true });
        }}>
          <label className="sr-only" htmlFor={`own-${item.key}`}>Another answer</label>
          <input id={`own-${item.key}`} value={own} onChange={(e) => setOwn(e.target.value)}
                 placeholder="Another answer"
                 className="flex-1 min-w-0 font-data text-[12.5px] p-2 border border-line-2 rounded-control" />
          <button type="submit" className={button}>Answer</button>
        </form>
      )}
    </div>
  );
}

const STATUS: Record<string, { label: string; tone: string }> = {
  proposed: { label: "waiting for you", tone: "text-measured-ink" },
  approved: { label: "Approved", tone: "text-done-ink" },
  rejected: { label: "Rejected by you", tone: "text-needs-you-ink" },
  removed: { label: "Removed", tone: "text-ink-3" },
  reopened: { label: "Re-opened: approve again", tone: "text-measured-ink" },
};

/** The current piece's items (boards 3, 3c): value, how it is passed, the reason, who
 *  proposed it, and the person's moves. Change edits the value as JSON. */
export function PieceItems({ items, actions, onReject }: {
  items: ItemView[];
  actions: Actions;
  onReject: (key: string) => void;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const open = items.filter((i) => i.status === "proposed" || i.status === "reopened");
  // Each of these is a decision of its own: a question wants an answer, a removal a second look.
  const rest = open.filter((i) => !asked(i) && !removing(i));

  return (
    <div>
      {items.map((item) => {
        const current = item.revisions.at(-1);
        const author = current?.actor === "ai" ? "proposed by the AI"
          : current?.actor === "registry" ? "from the registry" : "yours";
        const waiting = item.status === "proposed" || item.status === "reopened";
        const question = asked(item);
        return (
          <div key={item.key} role="group" aria-label={nameOf(item.key)}
               className={`grid grid-cols-1 sm:grid-cols-[minmax(0,190px)_minmax(0,1fr)_auto] gap-x-4 gap-y-2 items-start px-[22px] py-4 border-t border-line-soft ${
                 item.status === "rejected" ? "bg-needs-you-soft" : ""}`}>
            <div>
              <div className="font-data font-medium">{nameOf(item.key)}</div>
              <div className="font-data text-[12.5px] text-ink-2 break-all">{summary(item)}</div>
              <div className="text-[12px] text-ink-3">{author}</div>
            </div>
            <div className="text-[13.5px] text-ink-2 leading-[1.55]">
              {editing === item.key ? (
                <form className="flex flex-col gap-2" onSubmit={(e) => {
                  e.preventDefault();
                  actions.command.mutate({ move: "change", item: item.key, expected: item.current_n,
                                           value: JSON.parse(draft) });
                  setEditing(null);
                }}>
                  <label className="sr-only" htmlFor={`edit-${item.key}`}>New value for {nameOf(item.key)}</label>
                  <textarea id={`edit-${item.key}`} value={draft} onChange={(e) => setDraft(e.target.value)}
                            rows={4} className="font-data text-[12.5px] p-2 border border-line-2 rounded-control" />
                  <span className="flex gap-2"><button type="submit" className={primary}>Save</button>
                    <button type="button" className={button} onClick={() => setEditing(null)}>Cancel</button></span>
                </form>
              ) : (
                <>
                  {current?.because ?? ""}
                  {question && item.status !== "removed" && <Answer item={item} question={question} actions={actions} />}
                  <span className={`block mt-1 text-[12.5px] ${removing(item) ? "text-needs-you-ink" : STATUS[item.status]?.tone ?? ""}`}>
                    {removing(item) ? "The AI proposes removing this" : STATUS[item.status]?.label}
                  </span>
                </>
              )}
            </div>
            <div className="flex flex-wrap gap-[6px] sm:justify-end [&>button]:flex-1 sm:[&>button]:flex-none">
              {waiting && !question && (
                <button type="button" className={primary}
                        onClick={() => actions.command.mutate({ move: "approve", item: item.key,
                                                                expected: item.current_n })}>
                  Approve
                </button>
              )}
              {item.status !== "removed" && !question && (
                <button type="button" className={button}
                        onClick={() => { setEditing(item.key); setDraft(JSON.stringify(item.value, null, 2)); }}>
                  Change
                </button>
              )}
              {waiting && (
                <button type="button" className={`${button} text-needs-you-ink`}
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
          <button type="button" className={primary}
                  onClick={() => rest.forEach((i) => actions.command.mutate({
                    move: "approve", item: i.key, expected: i.current_n }))}>
            Approve the rest
          </button>
        </div>
      )}
    </div>
  );
}

/** *Write it myself* (board 3a): an item key in this piece and its value as JSON, checked by
 *  the server like any AI draft. */
export function WriteItem({ piece, items, actions }: {
  piece: string;
  items: ItemView[];
  actions: Actions;
}) {
  const [key, setKey] = useState(`${piece}:`);
  const [value, setValue] = useState("{}");
  return (
    <form className="flex flex-col gap-2 px-[22px] py-4 border-t border-line-soft" onSubmit={(e) => {
      e.preventDefault();
      actions.command.mutate({ move: piece === "questions" ? "answer" : "write", item: key,
                               expected: items.find((i) => i.key === key)?.current_n,
                               value: JSON.parse(value) });
    }}>
      <label htmlFor="write-key" className="text-[12.5px] text-ink-2">Item</label>
      <input id="write-key" value={key} onChange={(e) => setKey(e.target.value)}
             className="font-data text-[13px] p-2 border border-line-2 rounded-control" />
      <label htmlFor="write-value" className="text-[12.5px] text-ink-2">Value (JSON)</label>
      <textarea id="write-value" rows={5} value={value} onChange={(e) => setValue(e.target.value)}
                className="font-data text-[12.5px] p-2 border border-line-2 rounded-control" />
      <button type="submit" className={`${primary} self-start`}>Save</button>
      {actions.command.isError && <Failed error={actions.command.error} padded={false} />}
    </form>
  );
}
