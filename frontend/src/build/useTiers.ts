import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { components } from "../api/schema";

export type TierCard = components["schemas"]["TierCard"];

/** The tier vocabulary, read from the API rather than typed here.
 *
 * **It was hardcoded in two places and the operator caught it.** `Standard practice`,
 * `Check the premise` and the rest lived in a React file, with a second copy in
 * `docs/design/dashboard.html` and nothing holding the two together. Nothing in the repository
 * agreed that tier 2 should be called that — which made a reasonable person ask whether the
 * whole bar was invented.
 *
 * `comeni_core.plan.tiers.TIER_VOCABULARY` is the one declaration now, `GET /api/registry/tiers`
 * serves it, and this reads it. Same shape as `diagnostics.yml`: declare once, generate
 * consumers. A tier is at least as load-bearing as a diagnostic code.
 *
 * **The colour is a token name, never a hex.** `tokens.css` owns the palette; a value coming
 * over the wire would be a second palette able to disagree with it.
 */
export function useTiers() {
  const { data } = useQuery({
    queryKey: ["tiers"],
    queryFn: () => get<TierCard[]>("/registry/tiers"),
    staleTime: Infinity,
  });

  const by = new Map((data ?? []).map((card) => [card.tier, card]));

  return {
    tiers: data ?? [],
    /** The band's noun. Falls back to the number rather than to a guess: an interface that
     *  invents a word when the vocabulary has not loaded is how the hardcoding started. */
    name: (tier: number) => by.get(tier)?.name ?? `tier ${tier}`,
    group: (tier: number) => by.get(tier)?.group ?? `tier ${tier}`,
    what: (tier: number) => by.get(tier)?.what ?? "",
    colour: (tier: number) => by.get(tier)?.colour ?? "line-2",
  };
}
