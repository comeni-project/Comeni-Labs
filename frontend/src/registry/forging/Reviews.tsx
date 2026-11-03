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

export function ReviewComment({ review }: { review: Review }) {
  return <aside aria-label="Reviewer comment" className="mt-3 p-3 rounded-control border border-line bg-paper">
    <p className="m-0 text-[12px] text-ink-3">Reviewer AI · a model’s comment, so check it</p>
    <p className="m-0 text-[12px] font-data text-ink-3">{review.model}</p>
    <p className="mt-1 mb-0 whitespace-pre-wrap">{review.comment}</p>
    {review.quote && <blockquote className="mx-0 mb-0 border-l-2 border-line pl-3">
      <cite className="font-data text-[12px]">{review.file}</cite>
      <pre className="font-data text-[12px] whitespace-pre-wrap break-words">{review.quote}</pre>
    </blockquote>}
  </aside>;
}
