import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import type { AuthoringSession } from "../../api/types";

export type AlternativePreview = components["schemas"]["AlternativePreview"];
type Context = components["schemas"]["OfferContext"];

/** Which alternative is being looked at, and whether it was pinned (pressed) or only hovered. */
export type PreviewSelection = { option: string; pinned: boolean } | null;

/** How a saved preview is read: the endpoint, or a fixture's lookup when no server is behind it. */
export type ReadPreview = (path: string) => Promise<AlternativePreview>;

const same = (a: Context, b: Context) =>
  a.draft_revision === b.draft_revision && a.decision_revision === b.decision_revision &&
  a.session_version === b.session_version && a.registry === b.registry;

/** The complete pipeline an offered alternative would give, **saved when it was offered and read,
 *  never resolved, here**.
 *
 * **Read once per offer and context.** Hovering, focusing, pinning and reopening reuse the answer;
 * nothing refetches on its own — no mount, focus, reconnect or interval read — and a failed read
 * waits for a deliberate `retry()`. The key carries the context the person is looking at, so a
 * changed draft, decision, session or registry is a different preview, and a snapshot whose
 * observed context is not that one is refused rather than shown.
 */
export function useAlternativePreview(
  session: AuthoringSession, selection: PreviewSelection, read: ReadPreview = get,
) {
  const client = useQueryClient();
  const pending = session.pending_proposal;
  const offered = pending?.kind === "step"
    ? ((pending.envelope as { preview_options?: string[] } | undefined)?.preview_options ?? [])
    : [];
  const context = session.canvas?.context ?? null;
  const option = selection?.option ?? null;
  const available = option !== null && context !== null && offered.includes(option);
  const proposal = pending?.id ?? null;

  const params = context ? new URLSearchParams({
    expected_revision: String(context.draft_revision),
    expected_decision_revision: String(context.decision_revision),
    expected_session_version: String(context.session_version),
    expected_registry: context.registry,
  }) : null;
  const path = `/pipeline/authoring/${session.id}/proposals/${proposal}/alternatives/${option}?${params}`;

  const query = useQuery({
    queryKey: ["alternative-preview", session.id, proposal, option, context?.draft_revision,
               context?.decision_revision, context?.session_version, context?.registry],
    queryFn: async () => {
      const found = await read(path);
      if (!context || found.option_id !== option || !same(found.observed_context, context)) {
        throw new Error("The pipeline changed after this preview was saved.");
      }
      return found;
    },
    enabled: (q) => available && q.state.status !== "error",
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
    retryOnMount: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: false,
  });

  // `gcTime: Infinity` keeps nothing past its offer: a superseded proposal's previews, and a closed
  // session's, are dropped rather than left to accumulate.
  useEffect(() => () => {
    client.removeQueries({ queryKey: ["alternative-preview", session.id, proposal] });
  }, [client, session.id, proposal]);

  return {
    available,
    preview: available ? (query.data ?? null) : null,
    loading: available && query.isFetching && !query.data,
    error: available ? (query.error as Error | null) : null,
    retry: () => query.refetch(),
  };
}
