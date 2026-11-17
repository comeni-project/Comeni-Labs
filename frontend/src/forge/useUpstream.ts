import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { components } from "../api/schema";
import type { AdaptationView } from "./useAdaptation";

type ModuleDetail = components["schemas"]["ModuleDetail"];

/** What upstream says the tool does, for the header line; absent when the catalogue is down. */
export function useUpstream(view: Pick<AdaptationView, "source" | "path"> | undefined) {
  return useQuery({
    queryKey: ["catalogue-module", view?.source, view?.path],
    queryFn: () => get<ModuleDetail>(`/forge/catalogue/${view?.source}/${view?.path}`),
    enabled: !!view,
    retry: false,
  });
}
