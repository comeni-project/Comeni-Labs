import type { AnalysisPage } from "./rail/AnalysisSlot";

/** **Where an analysis opens.** An analysis is a pipeline draft (#511), at `/a/<draft>/<page>`.
 *  Home, the jump dialog and the cards link through this, so the address changes in one place. */
export function analysisAddress(draftId: string, page: AnalysisPage = "data", rest = ""): string {
  return `/a/${encodeURIComponent(draftId)}/${page}${rest ? `/${rest}` : ""}`;
}

/** Where a pipeline opens to be worked on: its Build page. */
export function pipelineAddress(pipeline: { id: string }): string {
  return analysisAddress(pipeline.id, "build");
}

/** Where the rail's `?` goes. One constant, so the address changes in one place when a docs site
 *  is published; until then the index in the public repository. */
export const DOCS_URL = "https://github.com/comeni-project/Comeni-Labs/blob/main/docs/index.md";
