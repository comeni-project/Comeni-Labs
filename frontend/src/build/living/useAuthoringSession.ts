import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer } from "react";

import { get, post, Refused } from "../../api/client";
import type {
  AuthoringDecided,
  AuthoringPreview,
  AuthoringProposal,
  AuthoringRetried,
  AuthoringSaid,
  AuthoringSession,
} from "../../api/types";
import {
  authoringReducer,
  initialAuthoring,
  isWaiting,
  visibleGraph,
  type MotionEvent,
} from "./authoringReducer";

/** How often a page with something on its way asks again. Seconds, not milliseconds: the answer
 *  is a model call, and a second's latency on seeing it costs nothing a person can perceive. */
export const POLL_MS = 1500;

const key = (sessionId: string) => ["authoring", sessionId] as const;

/** One authoring session: the server's picture, what is happening on the page, and the verbs.
 *
 * **The server's picture is TanStack Query's, and nothing else holds it.** The reducer receives
 * each snapshot and keeps only what the server does not know. Polling runs only while a turn is
 * pending or a Spawn blueprint is resolving, and stops on its own on an answer, a refusal, a
 * failure — or when the page unmounts, because the query does.
 *
 * **Nothing here touches `localStorage`.** The transcript and the prompt are durable on the
 * server; a half-typed message is component state and is allowed to vanish on reload.
 */
export function useAuthoringSession(sessionId: string, options: { pollMs?: number } = {}) {
  const pollMs = options.pollMs ?? POLL_MS;
  const client = useQueryClient();
  const [state, dispatch] = useReducer(authoringReducer, initialAuthoring);

  const session = useQuery({
    queryKey: key(sessionId),
    queryFn: () => get<AuthoringSession>(`/pipeline/authoring/${sessionId}`),
    refetchInterval: (query) => (isWaiting(query.state.data) ? pollMs : false),
  });

  useEffect(() => {
    if (session.data) dispatch({ type: "snapshot", session: session.data });
  }, [session.data]);

  const refresh = useCallback(
    () => client.invalidateQueries({ queryKey: key(sessionId) }),
    [client, sessionId],
  );

  const preview = useQuery({
    queryKey: [...key(sessionId), "preview", session.data?.revision ?? -1],
    queryFn: () => get<AuthoringPreview>(`/pipeline/authoring/${sessionId}/preview`),
    enabled: session.data !== undefined,
  });

  const say = useMutation({
    mutationFn: (text: string) =>
      post<AuthoringSaid>(`/pipeline/authoring/${sessionId}/messages`, { text }),
    onSuccess: () => {
      dispatch({ type: "sent" });
      void refresh();
    },
  });

  const decide = useMutation({
    mutationFn: (input: {
      proposal: AuthoringProposal;
      decision: "accepted" | "rejected";
      option: string;
      expectedRevision: number;
    }) =>
      post<AuthoringDecided>(
        `/pipeline/authoring/${sessionId}/proposals/${input.proposal.id}/decide`,
        {
          decision: input.decision,
          expected_revision: input.expectedRevision,
          option: input.proposal.kind === "step" ? input.option : null,
        },
      ),
    onMutate: (input) => {
      dispatch(
        input.decision === "accepted"
          ? {
              type: "accept",
              proposal: input.proposal,
              option: input.option,
              expectedRevision: input.expectedRevision,
            }
          : { type: "reject", proposalId: input.proposal.id },
      );
    },
    onSuccess: (answer, input) => {
      dispatch({ type: "decided", proposalId: input.proposal.id, answer });
      void refresh();
    },
    onError: (error, input) => {
      // A stale revision or a moved registry has already changed the session on the server — a
      // proposal marked stale, a fresh one offered — so the notice is shown and the page re-reads
      // rather than retrying the same request against a picture that is known to be old.
      dispatch({
        type: "refused",
        proposalId: input.proposal.id,
        detail: error instanceof Refused ? error.message : String(error),
      });
      void refresh();
    },
  });

  const retry = useMutation({
    mutationFn: () => post<AuthoringRetried>(`/pipeline/authoring/${sessionId}/retry`, {}),
    onSuccess: () => void refresh(),
  });

  const accept = useCallback(
    (proposal: AuthoringProposal, option = "keep") =>
      decide.mutate({
        proposal,
        decision: "accepted",
        option,
        expectedRevision: session.data?.revision ?? 0,
      }),
    [decide, session.data?.revision],
  );

  const reject = useCallback(
    (proposal: AuthoringProposal) =>
      decide.mutate({
        proposal,
        decision: "rejected",
        option: "keep",
        expectedRevision: session.data?.revision ?? 0,
      }),
    [decide, session.data?.revision],
  );

  return {
    session: session.data ?? null,
    loading: session.isPending,
    error: session.error,
    waiting: isWaiting(session.data),
    graph: visibleGraph(state),
    preview: preview.data ?? null,
    state,
    /** Whether one proposal's request is in flight — the only control that is disabled. */
    busy: (proposalId: string) => state.inFlight === proposalId,
    accept,
    reject,
    say: (text: string) => say.mutate(text),
    retry: () => retry.mutate(),
    previewOption: (option: string | null) => dispatch({ type: "preview", option }),
    select: (node: string | null) => dispatch({ type: "select", node }),
    compose: (text: string) => dispatch({ type: "compose", text }),
    dismiss: () => dispatch({ type: "dismiss" }),
    consumed: (event: MotionEvent) => dispatch({ type: "consumed", seq: event.seq }),
  };
}
