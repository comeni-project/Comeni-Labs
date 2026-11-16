import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router";

import { post } from "../api/client";
import { ChatPanel } from "../build/living/ChatPanel";
import { useAuthoringSession } from "../build/living/useAuthoringSession";
import { useAiConfigured } from "../home/useAiConfigured";
import { Drawer } from "../ui/Drawer";

/** The assistant over a page (#511): a floating button that opens the analysis's conversation in
 *  a drawer. It is the same conversation Build has, with the Data tools, so the page underneath
 *  keeps its state and the agent's changes appear on it, marked AI. */
export function Assistant({ draftId }: { draftId: string }) {
  // `?assistant=1` opens it, so it can be linked open.
  const [params] = useSearchParams();
  const [open, setOpen] = useState(params.get("assistant") === "1");
  const model = useAiConfigured();
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-label="Assistant"
              className="fixed right-4 bottom-4 z-20 h-11 px-4 rounded-full border border-ai-line bg-surface text-ai
                         text-[13.5px] font-semibold shadow-e2 cursor-pointer flex items-center gap-2">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M12 3l1.8 4.6L18.5 9.4 13.8 11.2 12 16l-1.8-4.8L5.5 9.4l4.7-1.8z" />
        </svg>
        Assistant
      </button>
      <Drawer open={open} onClose={() => setOpen(false)} label="Assistant">
        <div className="flex items-center gap-2 px-[14px] py-3 border-b border-line-soft">
          <span className="text-[14px] font-semibold text-ink">Assistant</span>
          <span className="text-[12px] text-ink-3">about this analysis's data</span>
          <button type="button" onClick={() => setOpen(false)} aria-label="Close the assistant"
                  className="ml-auto border-0 bg-transparent text-[18px] text-ink-3 cursor-pointer">×</button>
        </div>
        {model.configured ? <Conversation draftId={draftId} /> : <NeedsAModel />}
      </Drawer>
    </>
  );
}

function NeedsAModel() {
  const { pathname } = useLocation();
  return (
    <div className="flex flex-col gap-2 p-4">
      <p className="m-0 text-[14px] font-semibold text-ink">Needs a model</p>
      <p className="m-0 text-[13px] text-ink-2">
        Everything on this page works without one. The assistant reads your data and changes it for you once a model
        is connected.
      </p>
      <Link to={`${pathname}?settings=models`} className="self-start text-[13px] text-now-ink">Connect a model in Settings</Link>
    </div>
  );
}

function Conversation({ draftId }: { draftId: string }) {
  const [session, setSession] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const asked = useRef<string | null>(null);
  useEffect(() => {
    if (asked.current === draftId) return;
    asked.current = draftId;
    post<{ session_id: string }>(`/pipeline/drafts/${encodeURIComponent(draftId)}/session`, {})
      .then(({ session_id }) => setSession(session_id), setError);
  }, [draftId]);
  if (error) return <p role="alert" className="m-4 text-[13px] text-needs-you-ink">The conversation could not open.</p>;
  if (!session) return <p className="m-4 text-[13px] text-ink-3">Opening the conversation…</p>;
  return <Talk draftId={draftId} sessionId={session} />;
}

function Talk({ draftId, sessionId }: { draftId: string; sessionId: string }) {
  const living = useAuthoringSession(sessionId);
  const client = useQueryClient();
  // When the agent changes the data (its turn lands), the page underneath reads it again.
  const landed = living.session?.decision_revision;
  useEffect(() => {
    void client.invalidateQueries({ queryKey: ["analysis-data", draftId] });
  }, [landed, client, draftId]);
  if (!living.session) return <p className="m-4 text-[13px] text-ink-3">Opening the conversation…</p>;
  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex-1 min-h-0 flex flex-col">
        <ChatPanel embedded session={living.session} sending={living.sending} composer={living.composer}
                   onCompose={living.compose} onSay={living.say} onAnswer={living.answer} onRetry={living.retry}
                   notices={null} />
      </div>
      <p className="m-0 px-[14px] py-2 border-t border-line-soft text-[11.5px] text-ink-3">
        It reads your samples by name and what was measured, never a file's contents. Changes it makes are marked AI
        until you keep them.
      </p>
    </div>
  );
}
