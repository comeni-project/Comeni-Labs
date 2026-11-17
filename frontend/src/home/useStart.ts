import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { post } from "../api/client";
import { analysisAddress } from "../app/address";
import type { AnalysisPage } from "../app/rail/AnalysisSlot";

/** A new, empty analysis, opened on `page`: *Add a folder* opens its Data, *Build by hand* its
 *  Build. Nothing is asked first; an empty analysis is deleted from Home like any other. */
export function useStart(page: AnalysisPage) {
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () => post<{ id: string }>("/pipeline/drafts", { graph: { nodes: [], edges: [] } }),
    onSuccess: ({ id }) => navigate(analysisAddress(id, page)),
  });
}
