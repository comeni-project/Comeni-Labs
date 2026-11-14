import { QueryClientContext, useQuery } from "@tanstack/react-query";
import { useContext } from "react";

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

/** **What a question or an answer is about, in words** (issue 494): a type by its declared name,
 *  a measurement by its id with spaces (`read_length` is *read length*). The walks showed
 *  `assembly.fasta needs you` and `Correct assembly.fasta`. */
export function useSubjectNames(): (subject: string) => string {
  const typeName = useTypeNames();
  return (subject: string) => {
    const named = typeName(subject);
    return named !== subject ? named : subject.replaceAll("_", " ");
  };
}

/** **A type's declared grain**, `study` or `sample` (issue 494), before anything is built: a
 *  reference genome is one file for the run, never one per sample. `null` when undeclared.
 *  Read from the vocabulary the builder already loaded, so a card drawn on its own (a test, a
 *  preview) needs no query client and simply knows nothing. */
export function useGrains(): (typeId: string) => string | null {
  const client = useContext(QueryClientContext);
  const grains = client?.getQueryData<AuthoringVocabulary>(["authoring-vocabulary"])?.grains ?? {};
  return (typeId: string) => grains[typeId] ?? null;
}
