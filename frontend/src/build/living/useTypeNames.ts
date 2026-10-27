import { useQuery } from "@tanstack/react-query";

import { get } from "../../api/client";
import type { AuthoringVocabulary } from "../../api/types";

/** **A type's name as the registry declares it** (Part I.2, issue 306), from the vocabulary the
 *  builder already loads (same query). A type with no declared name is shown as its id: never
 *  an invented name. */
export function useTypeNames(): (typeId: string) => string {
  const vocabulary = useQuery({
    queryKey: ["authoring-vocabulary"],
    queryFn: () => get<AuthoringVocabulary>("/pipeline/authoring/vocabulary"),
    staleTime: Infinity,
  });
  const names = vocabulary.data?.names ?? {};
  return (typeId: string) => names[typeId] ?? typeId;
}
