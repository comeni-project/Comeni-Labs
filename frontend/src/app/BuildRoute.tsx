import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { post } from "../api/client";
import { LivingBuilder } from "../build/living/LivingBuilder";
import { Failed, Loading } from "../ui/States";

/** **One builder** (#395): every pipeline is a conversation and a canvas at `/build?session=`.
 *
 * `?draft=<id>` opens that pipeline's conversation — one drawn by hand gets an empty one that
 * reads the drawing back — and a bare `/build` starts a new pipeline; both then land on
 * `?session=`, replacing the address they came by. `?fake=` opens the static sessions the
 * artboards are compared against.
 */
export function BuildRoute() {
  const [params] = useSearchParams();
  if (params.get("session") || params.get("fake")) return <LivingBuilder />;
  return <Opening draft={params.get("draft")} />;
}

function Opening({ draft }: { draft: string | null }) {
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>(null);
  // **Once per address**, so a re-render (or React's development double effect) never opens a
  // second new pipeline.
  const opened = useRef<string | null>(null);

  useEffect(() => {
    const key = draft ?? "";
    if (opened.current === key) return;
    opened.current = key;
    (async () => {
      const id = draft
        ?? (await post<{ id: string }>("/pipeline/drafts", { graph: { nodes: [], edges: [] } })).id;
      const { session_id } = await post<{ session_id: string }>(
        `/pipeline/drafts/${encodeURIComponent(id)}/session`, {});
      navigate(`/build?session=${encodeURIComponent(session_id)}`, { replace: true });
    })().catch(setError);
  }, [draft, navigate]);

  return error ? <Failed error={error} /> : <Loading what="the pipeline" />;
}
