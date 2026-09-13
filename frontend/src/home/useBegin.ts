import { useMutation } from "@tanstack/react-query";

import { post } from "../api/client";
import type { AuthoringStarted, BeginAuthoring } from "../api/types";

/** Describe an analysis and start a session: door 1's first crossing.
 *
 * Returns the mutation whole, so its `.error` — a coded refusal included — reaches the caller.
 * The payload is `BeginAuthoring` and nothing else: a sentence and a mode.
 */
export function useBegin(onStarted: (started: AuthoringStarted) => void) {
  return useMutation({
    mutationFn: (body: BeginAuthoring) => post<AuthoringStarted>("/pipeline/authoring", body),
    onSuccess: onStarted,
  });
}
