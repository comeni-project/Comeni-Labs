import { useEffect, useRef, useState } from "react";

import type { AuthoringSession } from "../../api/types";
import type { About } from "./blocks/Block";
import { Chat } from "./Chat";
import { docked, questionTitle } from "./format";
import { Waiting, type WaitingProps } from "./Waiting";

export type StreamProps = {
  session: AuthoringSession;
  waiting: Omit<WaitingProps, "session" | "onAsk" | "saying">;
  sending: string[];
  onRetry: () => void;
  /** Say something in the conversation: *Why this one?* is a real turn. */
  onAsk: (text: string) => void;
  /** A request from outside (the dock's *show the full question*) to open the docked card. */
  showRequest?: number;
  /** Show what an announcement changed. */
  onAbout?: (about: About) => void;
};

/** **One conversation** (one builder plan 3): what was said, then what the engine waits on as the
 *  newest message. Once the person says something after the question was asked, the question's
 *  place keeps a one-line pointer (*Asked: … · see it*) and the question docks above the composer
 *  (`QuestionDock`); the pointer opens the full card again in place. */
export function Stream({ session, waiting, sending, onRetry, onAsk, showRequest = 0, onAbout }: StreamProps) {
  const [opened, setOpened] = useState<string | null>(null);
  const pending = session.pending_proposal;
  const away = docked(session);
  const open = pending !== null && opened === pending.id;
  const place = useRef<HTMLDivElement>(null);
  const show = () => {
    if (!pending) return;
    setOpened(pending.id);
    place.current?.scrollIntoView?.({ block: "nearest" });
  };
  useEffect(() => {
    if (showRequest > 0) show();
  }, [showRequest]); // eslint-disable-line react-hooks/exhaustive-deps -- once per request
  const card = <Waiting session={session} onAsk={onAsk} saying={sending.at(-1) ?? null} {...waiting} />;
  const tail = pending && away ? (
    <div ref={place} className="flex flex-col gap-2">
      <button type="button" data-testid="asked-pointer" onClick={show}
              className="self-start bg-transparent border-0 border-l-[3px] pl-[10px] py-[4px] text-left
                         text-[12.5px] text-ink-3 cursor-pointer" style={{ borderColor: "var(--line-2)" }}>
        Asked: {questionTitle(pending)} · <span className="underline">see it</span>
      </button>
      {open && card}
    </div>
  ) : card;
  return (
    <Chat session={session} sending={sending} failedPhase={session.phase === "failed"} onRetry={onRetry}
          onPoint={() => undefined} pointers={false} tail={tail} onAbout={onAbout} />
  );
}
