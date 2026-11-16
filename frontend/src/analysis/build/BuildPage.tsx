import { useEffect, useRef, useState } from "react";

import { post } from "../../api/client";
import { useAnalysis } from "../../app/AnalysisFrame";
import { LiveLiving } from "../../build/living/LivingBuilder";
import { Failed, Loading } from "../../ui/States";

/** Build, at `/a/:draft/build`: the draft's conversation and canvas. Every draft has one
 *  conversation (#395), opened once per draft, so the address never carries the session. */
export function BuildPage() {
  const { draftId } = useAnalysis();
  const [session, setSession] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  // **Once per draft**, so a re-render (or React's development double effect) never asks twice.
  const opened = useRef<string | null>(null);
  useEffect(() => {
    if (opened.current === draftId) return;
    opened.current = draftId;
    setSession(null);
    post<{ session_id: string }>(`/pipeline/drafts/${encodeURIComponent(draftId)}/session`, {})
      .then(({ session_id }) => setSession(session_id), setError);
  }, [draftId]);
  if (error) return <Failed error={error} />;
  if (!session) return <Loading what="the pipeline" />;
  return <LiveLiving key={session} sessionId={session} />;
}
