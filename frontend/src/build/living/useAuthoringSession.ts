import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import type { components } from "../../api/schema";
import type { AnswerValue } from "./AgentQuestion";

import { get, post, postForm, put, Refused } from "../../api/client";
import type {
  AuthoringEdited,
  AuthoringPreview,
  AuthoringSaid,
  AuthoringSession,
  AuthoringVocabulary,
  DraftGraph,
  SampleInspected,
} from "../../api/types";

type Changed = components["schemas"]["AuthoringChanged"];
type Change = Pick<components["schemas"]["DecisionChange"], "kind" | "subject">
  & Partial<Pick<components["schemas"]["DecisionChange"], "value" | "retract">>;

/** How often a page with the agent working asks again. */
export const POLL_MS = 1500;

/** How long the preview waits after the revision moves before asking for the new text. */
export const PREVIEW_DEBOUNCE_MS = 300;

/** What the server reads of each uploaded file (`mendel_api.services.inspect.HEAD_BYTES`). */
export const HEAD_BYTES = 4 * 2 ** 20;

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
    mutationFn: (text: string) =>
      post<AuthoringSaid>(`/pipeline/authoring/${sessionId}/messages`, { text }),
    onMutate: (text) => {
      setSending((list) => [...list, text]);
      compose("");
    },
    onSuccess: async (_said, text) => {
      await refresh();
      unsend(text);
    },
    onError: (error, text) => {
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

  const upload = useMutation({
    mutationFn: (input: { questionId: string | null; files: File[] }) => {
      const form = new FormData();
      if (input.questionId) form.append("question_id", input.questionId);
      // **Only the head leaves the browser**: the server reads the first 4 MB and no more.
      for (const file of input.files) {
        form.append("files", new File([file.slice(0, HEAD_BYTES)], file.name, { type: file.type }));
      }
      // Each file's real size, so the server can tell a whole small file from a head (#465).
      form.append("sizes", JSON.stringify(input.files.map((file) => file.size)));
      return postForm<SampleInspected>(`/pipeline/authoring/${sessionId}/samples`, form);
    },
    onSettled: () => void refresh(),
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
    say: (text: string) => say.mutate(text),
    answer: (questionId: string, value: AnswerValue) => answer.mutate({ questionId, value }),
    retry: (seq: number) => retry.mutate(seq),
    review: (node: string) => reviewed.mutate([node]),
    /** Samples measured by this server, as an answer to the agent's question or on their own. */
    upload: (questionId: string | null, files: File[]) => upload.mutateAsync({ questionId, files }),
    /** A hand edit: the server reads it as the person's changes (#395). */
    edit: (graph: DraftGraph) => edit.mutate(graph),
    rename: (name: string) => void put(`/pipeline/drafts/${session.data?.draft_id}`, {
      name, expected_revision: session.data?.revision }).then(() => refresh(), refused),
    switchInput: (contract: string, port: string, state: "off" | "optional" | "required") =>
      change.mutate({ kind: "optional_input", subject: `${contract}|${port}`, value: state }),
    keepWhole: (contract: string, whole: boolean) =>
      change.mutate({ kind: "whole", subject: contract, retract: !whole }),
  };
}
