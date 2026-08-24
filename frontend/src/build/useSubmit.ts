/** The courier: a kept pipeline from Mendel, into Wiener, and a run.
 *
 * **This hook is the only place in the product that touches both halves** — A179, and
 * `docs/design/wiener.md` §12 is why it is here rather than on either server. The browser
 * fetches the artifact from `mendel-api` and posts it to `wiener-api`, so neither learns the
 * other exists and `execution-boundary.md` §9's rejection of a Mendel→Wiener API stays intact
 * rather than quietly bending into an environment variable.
 *
 * **Two steps, not one.** Uploading is what discovers the parameters — Wiener reads the nulls
 * out of the artifact and answers with them (`declared`), because the artifact is the schema
 * for a submission. A single button would have to guess the fields before it had the artifact
 * that declares them, or provoke a 422 to find out.
 */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { blob } from "../api/client";
import { post, Unauthorized, upload } from "../wiener/api/client";
import type { components } from "../wiener/api/schema";

type ArtifactStored = components["schemas"]["ArtifactStored"];
type RunAccepted = components["schemas"]["RunAccepted"];

export function useSubmit(draftId: string | null) {
  const [artifact, setArtifact] = useState<ArtifactStored | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});

  const send = useMutation({
    mutationFn: async () => {
      const archive = await blob(`/pipeline/drafts/${draftId}/bundle`);
      return await upload<ArtifactStored>(
        "/api/artifacts", "bundle", archive, `pipeline-${draftId}.zip`,
      );
    },
    onSuccess: (stored) => {
      setArtifact(stored);
      // Seed one empty field per declared hole, so the form is the artifact's own shape and
      // a person can see what is missing before they start typing.
      setValues(Object.fromEntries(stored.declared.map((name) => [name, ""])));
    },
  });

  const start = useMutation({
    mutationFn: () =>
      post<RunAccepted>("/api/runs", {
        artifact_id: artifact?.artifact_id,
        params: values,
        executor: "local",
      }),
  });

  const unfilled = Object.entries(values)
    .filter(([, value]) => value.trim() === "")
    .map(([name]) => name);

  return {
    artifact,
    values,
    set: (name: string, value: string) => setValues((v) => ({ ...v, [name]: value })),
    send: () => send.mutate(),
    sending: send.isPending,
    start: () => start.mutate(),
    starting: start.isPending,
    runId: start.data?.run_id ?? null,
    /** **Every declared parameter, or none of them.** Wiener refuses a partial map and says so;
     *  the button says it first, because a refusal that a disabled button could have prevented
     *  is a round trip a person had to make to learn something the page knew. */
    unfilled,
    /** **The class, not the message.** Both screens that meet a 401 offer the same thing — a
     *  field to paste the token into — and deciding that by matching on a message string is
     *  how one of them stops recognising it. */
    unauthorized: send.error instanceof Unauthorized || start.error instanceof Unauthorized,
    error: send.error
      ? String(send.error.message)
      : start.error
        ? String(start.error.message)
        : null,
  };
}
