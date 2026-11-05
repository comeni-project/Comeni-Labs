import { useQuery } from "@tanstack/react-query";

import { get } from "../../api/client";
import type { components } from "../../api/schema";

export type Review = components["schemas"]["ReviewView"];

export function useReviews(id: string, working: boolean, revisions: string) {
  return useQuery({
    queryKey: ["forge-reviews", id, working, revisions],
    queryFn: () => get<Review[]>(`/forge/adaptations/${id}/reviews`),
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: working ? 2_000 : false,
  });
}

/** A model's second opinion on one revision, labelled as a model's; never the engine's. An
 *  empty comment means the reviewer read the revision and raised no concern. */
export function ReviewComment({ review }: { review: Review }) {
  const label = <>Second opinion · <span className="font-data">{review.model}</span> · a model’s comment, check it</>;
  if (!review.comment) return <p className="m-0 text-[12px] text-ink-3">Second opinion · <span className="font-data">{review.model}</span> · no concern raised</p>;
  return <aside aria-label="Reviewer comment" className="border-l-2 border-now-line pl-3 text-[13px]">
    <p className="m-0 text-[12px] text-now-ink">{label}</p>
    <p className="mt-1 mb-0 whitespace-pre-wrap text-ink-2">{review.comment}</p>
    {review.quote && <blockquote className="mx-0 mt-2 mb-0 border-l-2 border-line pl-3">
      <cite className="font-data text-[12px] not-italic text-ink-3">{review.file}</cite>
      <pre className="font-data text-[12px] whitespace-pre-wrap break-words m-0">{review.quote}</pre>
    </blockquote>}
  </aside>;
}
