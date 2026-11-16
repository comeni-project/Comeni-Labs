import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import type { components } from "../../api/schema";
import type { AnswerValue } from "./AgentQuestion";

import { get, post, put, Refused } from "../../api/client";

/** What Run → Console carries with the person's words: the run, and its last lines. */
export type ConsoleContext = { run: string; console: string; shell: string };
import type {
  AuthoringEdited,
  AuthoringPreview,
  AuthoringSaid,
  AuthoringSession,
  AuthoringVocabulary,
  DraftGraph,
} from "../../api/types";

type Changed = components["schemas"]["AuthoringChanged"];
type Change = Pick<components["schemas"]["DecisionChange"], "kind" | "subject">
  & Partial<Pick<components["schemas"]["DecisionChange"], "value" | "retract">>;

/** How often a page with the agent working asks again. */
export const POLL_MS = 1500;

/** How long the preview waits after the revision moves before asking for the new text. */
export const PREVIEW_DEBOUNCE_MS = 300;


const key = (sessionId: string) => ["authoring", sessionId] as const;

export type ServerNotice = { code: string | null; text: string };

/** `MI0201: …` → `{ code: "MI0201", text: "…" }`. A detail with no code keeps its words. */
export function noticeFrom(error: unknown): ServerNotice {
  const detail = error instanceof Refused ? error.message : String(error);
  const match = /^(M[A-Z]\d{4}):\s*(.*)$/s.exec(detail);
  return match ? { code: match[1], text: match[2].split("\n")[0] } : { code: null, text: detail };
}

/** One builder session (#463): the server's picture, what is happening on the page, and the verbs.
 *
 * **The server's picture is TanStack Query's, and nothing else holds it.** Polling runs only while
 * the agent is working, and stops on its own when its turn ends — or when the page unmounts.
 * What is kept here is only what the server does not know: the open step, the half-typed message,
 * the messages on their way, and the last refusal.
 *
 * **Nothing here touches `localStorage`.** The transcript is durable on the server; a half-typed
 * message is component state and is allowed to vanish on reload.
 */
export function useAuthoringSession(sessionId: string, options: { pollMs?: number } = {}) {
  const pollMs = options.pollMs ?? POLL_MS;
  const client = useQueryClient();
  const [selected, select] = useState<string | null>(null);
  const [composer, compose] = useState("");
  const [sending, setSending] = useState<string[]>([]);
  const [notice, setNotice] = useState<ServerNotice | null>(null);

  const session = useQuery({
    queryKey: key(sessionId),
    queryFn: () => get<AuthoringSession>(`/pipeline/authoring/${sessionId}`),
    refetchInterval: (query) => (query.state.data?.working ? pollMs : false),
  });

  const refresh = useCallback(
    () => client.invalidateQueries({ queryKey: key(sessionId) }),
    [client, sessionId],
  );
  const refused = (error: unknown) => {
    setNotice(noticeFrom(error));
    void refresh();
  };
  const take = (changed: { session: AuthoringSession }) => client.setQueryData(key(sessionId), changed.session);

  // **Debounced on the revision**, which only moves when something is committed.
  const revision = session.data?.revision ?? -1;
  const [settledRevision, setSettledRevision] = useState(revision);
  useEffect(() => {
    const wait = setTimeout(() => setSettledRevision(revision), PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(wait);
  }, [revision]);

  // **The analyses list follows what was committed** (#530): the rail, Home and Run read the
  // analysis's name, step count and kept digest from it, and the agent renames and builds.
  const working = session.data?.working ?? false;
  useEffect(() => {
    if (session.data && !working) void client.invalidateQueries({ queryKey: ["drafts"] });
  }, [client, working, settledRevision, session.data === undefined]); // eslint-disable-line react-hooks/exhaustive-deps

  const preview = useQuery({
    queryKey: [...key(sessionId), "preview", settledRevision],
    queryFn: () => get<AuthoringPreview>(`/pipeline/authoring/${sessionId}/preview`),
    enabled: session.data !== undefined && settledRevision === revision,
    placeholderData: (previous) => previous,
  });

  const vocabulary = useQuery({
    queryKey: ["authoring-vocabulary"],
    queryFn: () => get<AuthoringVocabulary>("/pipeline/authoring/vocabulary"),
    staleTime: Infinity,
  });

  /** Drawn before the request returns, and gone once the transcript holds it. */
  const unsend = (text: string) => setSending((list) => {
    const at = list.indexOf(text);
    return at < 0 ? list : [...list.slice(0, at), ...list.slice(at + 1)];
  });

  const say = useMutation({
    mutationFn: ({ text, console }: { text: string; console?: ConsoleContext }) =>
      post<AuthoringSaid>(`/pipeline/authoring/${sessionId}/messages`, console ? { text, console } : { text }),
    onMutate: ({ text }) => {
      setSending((list) => [...list, text]);
      compose("");
    },
    onSuccess: async (_said, { text }) => {
      await refresh();
      unsend(text);
    },
    onError: (error, { text }) => {
      unsend(text);
      compose(text);
      setNotice(noticeFrom(error));
    },
  });

  const answer = useMutation({
    mutationFn: (input: { questionId: string; value: AnswerValue }) =>
      post<AuthoringSaid>(`/pipeline/authoring/${sessionId}/questions/${input.questionId}`,
        { value: input.value }),
    onSuccess: () => void refresh(),
    onError: refused,
  });

  const retry = useMutation({
    mutationFn: (seq: number) => post<AuthoringSaid>(`/pipeline/authoring/${sessionId}/turns/${seq}/retry`, {}),
    onSuccess: () => void refresh(),
    onError: refused,
  });

  const reviewed = useMutation({
    mutationFn: (nodes: string[] | "all") =>
      post<components["schemas"]["AuthoringReviewed"]>(`/pipeline/authoring/${sessionId}/reviewed`, { nodes }),
    onSuccess: () => void refresh(),
    onError: refused,
  });

  const edit = useMutation({
    mutationFn: (graph: DraftGraph) =>
      post<AuthoringEdited>(`/pipeline/authoring/${sessionId}/edits`, { graph,
        expected_revision: session.data?.revision ?? 0 }),
    onSuccess: take,
    onError: refused,
  });

  const change = useMutation({
    mutationFn: (change: Change) => post<Changed>(`/pipeline/authoring/${sessionId}/changes`, {
      change, expected_decision_revision: session.data?.decision_revision ?? null }),
    onSuccess: take,
    onError: refused,
  });


  return {
    session: session.data ?? null,
    loading: session.isPending,
    error: session.error,
    preview: preview.data ?? null,
    vocabulary: vocabulary.data?.types ?? null,
    measurements: vocabulary.data?.measurements,
    selected,
    select,
    composer,
    compose,
    sending,
    notice,
    dismiss: () => setNotice(null),
    say: (text: string) => say.mutate({ text }),
    /** Words from Run → Console, with what the console showed (#511). */
    sayWith: (text: string, console: ConsoleContext) => say.mutate({ text, console }),
    answer: (questionId: string, value: AnswerValue) => answer.mutate({ questionId, value }),
    retry: (seq: number) => retry.mutate(seq),
    review: (node: string) => reviewed.mutate([node]),
    /** A hand edit: the server reads it as the person's changes (#395). */
    edit: (graph: DraftGraph) => edit.mutate(graph),
    /** **Tidy**: the server lays the drawing out again with the current geometry, and keeps it. */
    tidy: () => void post<AuthoringSession>(`/pipeline/authoring/${sessionId}/tidy`, {})
      .then((next) => client.setQueryData(key(sessionId), next), refused),
    rename: (name: string) => void put(`/pipeline/drafts/${session.data?.draft_id}`, {
      name, expected_revision: session.data?.revision }).then(() => refresh(), refused),
    switchInput: (contract: string, port: string, state: "off" | "optional" | "required") =>
      change.mutate({ kind: "optional_input", subject: `${contract}|${port}`, value: state }),
    keepWhole: (contract: string, whole: boolean) =>
      change.mutate({ kind: "whole", subject: contract, retract: !whole }),
  };
}
