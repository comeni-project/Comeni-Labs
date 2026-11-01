import { useEffect, useRef, useState } from "react";

import { Composer } from "../../build/living/Composer";
import { Failed } from "../../ui/States";
import { summaryOf } from "./PieceItems";
import { elapsed, outcomeOf, progressOf, type Step } from "./progress";
import type { AdaptationView, ItemView, MessageView } from "./useAdaptation";
import { nameOf } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

type Actions = ReturnType<typeof useForgeActions>;
type Proposal = { move: string; item: string; n: number; value?: unknown; because?: string };
type Fate = { open: boolean; label: string };

const MOVE: Record<string, string> = {
  revise: "Change", add: "Add", propose_removal: "Remove",
};
const DECIDED: Record<string, string> = { approve: "Approved", reject: "Rejected" };
const WHO: Record<string, string> = { person: "You", ai: "AI", engine: "Comeni" };
const DRAFT = "draft:";
const WIDTH = { least: 320, most: 620, start: 380, step: 24, saved: "forge-chat-width" };

/** What became of a card's proposal: open only while the item is still at the card's revision,
 *  so approving a card approves the value on it. */
function fate(item: ItemView | undefined, card: Proposal): Fate {
  if (!item) return { open: false, label: "" };
  const after = item.revisions.find((r) => r.n === card.n + 1);
  if (after) return { open: false, label: DECIDED[after.move] ?? "Superseded by a newer revision" };
  const waiting = item.status === "proposed" || item.status === "reopened";
  return { open: waiting, label: item.status };
}

const clock = (at: string) => new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

/** The engine's own words, one step back from the sentence a person reads first. */
function useDetails(lines: string[]) {
  const [open, setOpen] = useState(false);
  return {
    toggle: lines.length > 0 && (
      <button type="button" className="link-plain ml-auto" aria-expanded={open} onClick={() => setOpen(!open)}>Details</button>
    ),
    list: open && (
      <ul className="mt-1 mb-0 pl-4 font-data text-[12px] text-ink-3 break-words">{lines.map((l) => <li key={l}>{l}</li>)}</ul>
    ),
  };
}

function ProposalCard({ card, item, onDecide, onChange }: {
  card: Proposal; item: ItemView | undefined; onDecide: (move: "approve" | "reject") => void; onChange: () => void;
}) {
  const decided = fate(item, card);
  const said = card.value === undefined || card.value === null ? "" : summaryOf(card.item, card.value);
  return (
    <div className="proposal" data-open={decided.open}>
      <div className="flex justify-between items-start gap-[10px]">
        <span className="font-data text-[13px] min-w-0 [overflow-wrap:anywhere]">
          {MOVE[card.move] ?? card.move} {nameOf(card.item)}{said && <span className="text-ink-3"> → </span>}{said}
        </span>
        {decided.open && <span className="status-chip">waiting for you</span>}
      </div>
      {card.because && <span className="text-[12.5px] text-ink-2">{card.because}</span>}
      {decided.open ? (
        <span className="flex gap-2">
          <button type="button" className="control-primary" onClick={() => onDecide("approve")}>Accept</button>
          <button type="button" className="control" onClick={onChange}>Change</button>
          <button type="button" className="control" onClick={() => onDecide("reject")}>Decline</button>
        </span>
      ) : <span className="text-[12px] text-ink-3">{decided.label}</span>}
    </div>
  );
}

function Message({ message, latest, view, actions, busy, onWrite, setAbout }: {
  message: MessageView; latest: boolean; view: AdaptationView; actions: Actions; busy: boolean;
  onWrite: () => void; setAbout: (key: string | null) => void;
}) {
  const details = useDetails(message.details ?? []);
  if (message.resolved) {
    return <li className="text-[12.5px] text-ink-3">An earlier draft was refused, then redone.</li>;
  }
  const person = message.role === "person";
  const outcome = outcomeOf(message);
  const refused = message.role === "engine" && (message.item ?? "").startsWith(DRAFT);
  const decide = (card: Proposal, move: "approve" | "reject") => {
    actions.command.mutate({ move, item: card.item, expected: card.n });
    if (move === "reject") setAbout(card.item);
  };
  return (
    <li className={`settle flex flex-col gap-[3px] min-w-0 ${person ? "items-end" : ""}`}>
      <span className={`flex gap-[10px] w-full text-[11.5px] text-ink-3 ${person ? "justify-end" : "justify-between"}`}>
        {person ? <><span className="font-data">{clock(message.at)}</span><span>You</span></>
          : <><span>{WHO[message.role] ?? message.role}</span><span className="font-data">{clock(message.at)}</span></>}
      </span>
      {message.item && !refused && <span className="font-data text-[11.5px] text-ink-3">about {nameOf(message.item)}</span>}
      <p className={`m-0 text-[13.5px] leading-[1.55] whitespace-pre-line break-words ${refused ? "font-medium" : ""} ${
        person ? "bg-now-soft px-[11px] py-[7px] rounded-button max-w-[88%]" : ""}`}>{message.content}</p>
      {message.pending && <span className="text-[12px] text-ink-3">Waiting for the reply</span>}
      {outcome?.tone === "none" && (
        <span className="flex flex-wrap items-center gap-2 mt-[3px] w-full">
          <span className="status-chip">{outcome.label}</span>
          <span className="text-[12px] text-ink-3">{outcome.note}</span>
          {latest && !busy && view.next_piece && (
            <button type="button" className="link-plain ml-auto" onClick={() => actions.draft.mutate(view.next_piece as string)}>Redraft</button>
          )}
        </span>
      )}
      {outcome?.tone === "some" && <span className="text-[12px] text-ink-3">{outcome.label}</span>}
      {(message.commands as Proposal[]).map((card, n) => (
        <ProposalCard key={n} card={card} item={view.items.find((i) => i.key === card.item)}
                      onDecide={(move) => decide(card, move)} onChange={() => setAbout(card.item)} />
      ))}
      {refused ? (
        <span className="flex flex-wrap items-center gap-2 mt-[6px] w-full">
          <button type="button" className="control-primary" disabled={busy}
                  onClick={() => actions.draft.mutate((message.item ?? "").slice(DRAFT.length))}>Try again</button>
          <button type="button" className="control" onClick={onWrite}>Write it myself</button>
          {details.toggle}
        </span>
      ) : details.toggle}
      {details.list}
    </li>
  );
}

function Working({ steps, piece }: { steps: Step[]; piece: string | null }) {
  const progress = progressOf(steps, piece);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(clock);
  }, []);
  return (
    <li role="status" className="flex flex-col gap-2">
      <span className="flex justify-between gap-[10px] text-[11.5px] text-ink-3">
        <span>Comeni</span>
        {progress.since && <span className="font-data">{elapsed(progress.since, now)}</span>}
      </span>
      <p className="m-0 text-[13.5px] font-medium">{progress.title}</p>
      <ol className="list-none m-0 p-0 flex flex-col gap-[6px]">
        {progress.steps.map((line) => (
          <li key={line.key} className="progress-line" data-state={line.state}>
            <span className="progress-mark" aria-hidden="true">{line.state === "done" ? "✓" : line.state === "refused" ? "!" : <i />}</span>
            <span className="min-w-0">
              {line.label}
              {line.detail && <span className="block font-data text-[12px] text-ink-3 break-words">{line.detail}</span>}
            </span>
          </li>
        ))}
      </ol>
      <p className="m-0 pt-2 border-t border-line-soft text-[12px] text-ink-3">
        {progress.tokens ? `${progress.tokens.sent.toLocaleString("en")} tokens sent, ${progress.tokens.received.toLocaleString("en")} received. ` : ""}
        The page stays yours while it works.
      </p>
    </li>
  );
}

function savedWidth(): number {
  try {
    const found = Number(localStorage.getItem(WIDTH.saved));
    return found >= WIDTH.least && found <= WIDTH.most ? found : WIDTH.start;
  } catch {
    return WIDTH.start;
  }
}

/** The chat beside the pieces: one message shape, each reply saying what it did, and what the AI
 *  is doing while it works. A proposal is decided where it appears. */
export function Chat({ view, steps, working, actions, about, setAbout, onWrite }: {
  view: AdaptationView;
  steps: Step[];
  working: boolean;
  actions: Actions;
  about: string | null;
  setAbout: (key: string | null) => void;
  onWrite: () => void;
}) {
  const [text, setText] = useState("");
  const [width, setWidth] = useState(savedWidth);
  const [open, setOpen] = useState(false);
  const end = useRef<HTMLLIElement>(null);
  const count = view.messages.length + steps.length;
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [count]);

  const widen = (next: number) => {
    const clamped = Math.min(WIDTH.most, Math.max(WIDTH.least, next));
    setWidth(clamped);
    try { localStorage.setItem(WIDTH.saved, String(clamped)); } catch { /* the width just is not kept */ }
  };
  const drag = (event: React.PointerEvent) => {
    event.preventDefault();
    const from = event.clientX;
    const start = width;
    const move = (e: PointerEvent) => widen(start + from - e.clientX);
    const stop = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };
  const last = view.messages.at(-1);

  return (
    <>
      <button type="button" className="chat-handle" aria-label="Resize the chat. Use the left and right arrow keys."
              onPointerDown={drag}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft") widen(width + WIDTH.step);
                if (e.key === "ArrowRight") widen(width - WIDTH.step);
              }}><span /></button>
      <aside aria-label="Chat with the AI" className="chat-panel" data-open={open} style={{ "--chat-width": `${width}px` } as React.CSSProperties}>
        <button type="button" className="chat-peek" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="font-medium">Chat</span>
          <span className="chat-peek-line" data-line={working ? progressOf(steps, view.next_piece).title : last?.content ?? ""} />
        </button>
        <div className="chat-head">
          <h2 className="m-0 text-[14px] font-semibold">Chat</h2>
          <span className="text-[12px] text-ink-3">about {about ? nameOf(about) : view.path}</span>
        </div>
        <ol role="log" aria-label="Messages" className="chat-log">
          {view.messages.length === 0 && !working && (
            <li className="text-[13.5px] text-ink-3">Ask anything about {view.path}, or say what to change.</li>
          )}
          {view.messages.map((message) => (
            <Message key={message.seq} message={message} latest={message === last} view={view} actions={actions} busy={working}
                     onWrite={onWrite} setAbout={setAbout} />
          ))}
          {working && <Working steps={steps} piece={view.next_piece ?? null} />}
          <li ref={end} aria-hidden="true" />
        </ol>
        {actions.command.isError && <div className="px-3"><Failed error={actions.command.error} padded={false} /></div>}
        <div className="flex flex-col gap-[6px] p-[12px] border-t border-line">
          {about && (
            <span className="text-[12px] text-ink-3">
              About <span className="font-data">{nameOf(about)}</span>.{" "}
              <button type="button" className="link-plain" onClick={() => setAbout(null)}>Ask about the whole tool</button>
            </span>
          )}
          <Composer value={text} onChange={setText} placeholder="Ask, or say what to change"
                    onSend={(content) => { actions.say.mutate({ content, item: about }); setText(""); }} />
          {actions.say.isError && <Failed error={actions.say.error} padded={false} />}
        </div>
      </aside>
    </>
  );
}
