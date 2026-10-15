import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { AiConfigured } from "../api/types";

/** Whether a model is configured: **a settings fact, asked on its own** (issue 268).
 *
 * It decides whether describing an analysis in words is offered. `/health/ai` also answers it,
 * but that is the operator's diagnostic: it asks Redis and probes the model server, which takes
 * seconds exactly when something is down, and the describe box waited on it undrawn while what a
 * person typed went nowhere. One query key, so `Home` can wait for it with the rest of the page
 * and the components that draw the box read it already known.
 */
export function useAiConfigured() {
  const asked = useQuery({
    queryKey: ["settings", "ai"],
    queryFn: () => get<AiConfigured>("/settings/ai"),
    retry: false,
  });
  return { pending: asked.isPending, configured: asked.data?.configured === true };
}
