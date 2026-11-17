import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { forgeName, ForgeSlot } from "./ForgeSlot";
import { PublishPage } from "./PublishPage";
import { TestsPage } from "./TestsPage";
import { ToolPage } from "./ToolPage";
import { useAdaptation, type AdaptationView } from "./useAdaptation";

type ModuleDetail = components["schemas"]["ModuleDetail"];
export type ForgingPageName = "tool" | "tests" | "publish";

const TITLE: Record<ForgingPageName, string> = { tool: "Tool", tests: "Tests", publish: "Publish" };

/** What upstream says the tool does, for the header line; absent when the catalogue is down. */
export function useUpstream(view: AdaptationView | undefined) {
  return useQuery({
    queryKey: ["catalogue-module", view?.source, view?.path],
    queryFn: () => get<ModuleDetail>(`/forge/catalogue/${view?.source}/${view?.path}`),
    enabled: !!view,
    retry: false,
  });
}

/** `/forge/:id`, `/forge/:id/tests`, `/forge/:id/publish` · **A forging** (board "6 · Forging"):
 *  the rail's three pages and Review, the page's header, and the page. */
export function Forging({ page }: { page: ForgingPageName }) {
  const id = useParams().id ?? "";
  const adaptation = useAdaptation(id);
  const view = adaptation.data;
  const upstream = useUpstream(view);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  useTitle(view ? `${TITLE[page]} · ${forgeName(view.path, view.version)}` : "Forging");

  if (adaptation.isPending) return <Loading what="the forging" />;
  if (adaptation.isError || !view) return <Failed error={adaptation.error} />;

  const description = upstream.data?.row?.description;
  return (
    <div className="overflow-y-auto h-full">
      <ForgeSlot view={view} onReview={(key) => navigate(`/forge/${encodeURIComponent(id)}?part=${encodeURIComponent(key)}`)} />
      <div className="page">
        <header className="flex flex-col gap-1">
          <h1 className="m-0 text-[22px] font-semibold">{TITLE[page]}</h1>
          <p className="m-0 text-[13px] text-ink-2">
            {forgeName(view.path, view.version)} from {view.source} <span className="font-data">modules/{view.source}/{view.path}</span>
            {description ? ` · ${description}` : ""}
          </p>
        </header>
        {page === "tool" && <ToolPage view={view} part={params.get("part")} />}
        {page === "tests" && <TestsPage view={view} />}
        {page === "publish" && <PublishPage view={view} />}
      </div>
    </div>
  );
}
