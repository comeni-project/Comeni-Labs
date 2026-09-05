/** The Registry section's queries and mutations, and the generated names they use.
 *
 * **One import site, for the reason `types.ts` records.** FastAPI splits a model into
 * `Foo-Input`/`Foo-Output` when optionality differs between request and response, and qualifies
 * a name two classes share — both are the generator telling the truth about an ambiguous name,
 * and both break every consumer at once when they change. Here they break one file.
 *
 * **Polling lives here, not in the pages.** §7 asks for two-second polling on active states and
 * nothing on terminal ones, and a page that decided its own interval would be a second answer
 * to *is this still moving* — the answer is the adaptation's state, and it is the same answer
 * everywhere.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, post } from "./client";
import type { components } from "./schema";

type S = components["schemas"];

export type Overview = S["Overview"];
export type SourceRow = S["SourceRow"];
export type Stages = S["Stages"];
export type AdaptationRow = S["AdaptationRow"];
export type AdaptationPage = S["Page"];
export type Adaptation = S["Adaptation"];
export type Revision = S["Revision"];
export type AdaptationState = S["AdaptationState"];
export type Event = S["Event"];
export type ReviewCandidate = S["ReviewCandidate"];
export type ContractField = S["ContractField"];
export type OpenHole = S["OpenHole"];
export type GraphPort = S["GraphPort"];
export type FilePane = S["FilePane"];
export type IoGraph = S["IoGraph"];
export type Origins = S["Origins"];
export type NumberedExcerpt = S["NumberedExcerpt"];
export type ApprovalState = S["ApprovalState"];
export type Turn = S["Turn"];
export type Citation = S["Citation"];
export type CatalogueItem = S["CatalogueItem"];
export type CatalogueRow = S["CatalogueRow"];
export type CataloguePage = S["CataloguePage"];
export type Freshness = S["Freshness"];

/** What a catalogue row can be filtered to. `adapted` is the union of the two landed verdicts
 *  and is not a `Freshness`; the route's own `Adapted` literal says why. */
export type Status = Freshness | "adapted";

/** States a worker holds or a queue is about to hand to one.
 *
 * **This is why a page polls, and the only reason.** `published` and `archived` are finished and
 * `review` and `changes_requested` are waiting on a person — refetching any of them every two
 * seconds asks a question whose answer cannot change without the viewer doing something.
 */
export const MOVING: AdaptationState[] = [
  "scaffolding",
  "queued",
  "generating",
  "validating",
  "publishing",
];

export function isMoving(state: AdaptationState | undefined): boolean {
  return state !== undefined && MOVING.includes(state);
}

/** Two seconds, and §7 names the number.
 *
 * It also says *do not add a WebSocket/SSE protocol before polling proves inadequate* — so this
 * is deliberately the whole realtime story, and the thing that would replace it is a
 * measurement rather than a preference.
 */
const TICK = 2_000;

export function useOverview() {
  return useQuery({
    queryKey: ["forge", "overview"],
    queryFn: () => get<Overview>("/forge/overview"),
    // The overview is a count of moving things, so it moves on its own — but nobody is watching
    // one adaptation here, and a two-second tick on eight aggregate queries is a page that
    // costs more than it tells anybody.
    refetchInterval: 10_000,
  });
}

export const PER_PAGE = 25;

export function useCatalogue(params: {
  q: string;
  source: string;
  status: string;
  adaptableOnly: boolean;
  offset: number;
}) {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.source) search.set("source", params.source);
  if (params.status) search.set("status", params.status);
  if (params.adaptableOnly) search.set("adaptable_only", "true");
  if (params.offset) search.set("offset", String(params.offset));
  search.set("limit", String(PER_PAGE));
  const query = search.toString();

  return useQuery({
    queryKey: ["forge", "catalogue", query],
    queryFn: () => get<CataloguePage>(`/forge/catalogue${query ? `?${query}` : ""}`),
    // **The previous page stays on screen while the next one loads.** Without it every
    // keystroke in the search box empties the table and then refills it, which reads as the
    // catalogue being lost rather than as it being filtered.
    placeholderData: (previous) => previous,
  });
}

export function useCatalogueItem(id: string | undefined) {
  return useQuery({
    queryKey: ["forge", "catalogue-item", id],
    queryFn: () => get<CatalogueItem>(`/forge/catalogue/${id}`),
    enabled: Boolean(id),
  });
}

export function useAdaptations(params: { state?: string; source?: string; cursor?: string }) {
  const search = new URLSearchParams();
  if (params.state) search.set("state", params.state);
  if (params.source) search.set("source", params.source);
  if (params.cursor) search.set("cursor", params.cursor);
  const query = search.toString();

  return useQuery({
    queryKey: ["forge", "adaptations", query],
    queryFn: () => get<AdaptationPage>(`/forge/adaptations${query ? `?${query}` : ""}`),
    // The work queue is a list of things in flight by definition, so it ticks. A page showing
    // only `review` still ticks: a generation finishing *adds* a row to it.
    refetchInterval: TICK,
  });
}

export function useAdaptation(id: string | undefined) {
  return useQuery({
    queryKey: ["forge", "adaptation", id],
    queryFn: () => get<Adaptation>(`/forge/adaptations/${id}`),
    enabled: Boolean(id),
    // **Stops when the adaptation stops.** A published one is never going to change again, and
    // a page that keeps asking is a page that keeps a worker busy answering *still published*.
    refetchInterval: (query) =>
      isMoving(query.state.data?.adaptation.state) ? TICK : false,
  });
}

/** The candidate a reviewer reads — read out of the workspace, so it changes only when a job
 *  writes one. It follows the adaptation's own tick rather than having a second answer to
 *  *is this still moving*. */
export function useCandidate(id: string | undefined, moving: boolean) {
  return useQuery({
    queryKey: ["forge", "candidate", id],
    queryFn: () => get<ReviewCandidate>(`/forge/adaptations/${id}/candidate`),
    enabled: Boolean(id),
    refetchInterval: moving ? TICK : false,
    // **A 404 here is an ordinary state, not a failure.** An adaptation still scaffolding has
    // no candidate yet, and retrying three times with backoff would make the page spin on the
    // one state where it has something useful to say.
    retry: false,
  });
}

/** Why Approve is disabled, before anybody presses it. Recomputed against the registry as it
 *  is *now*, which is the one condition that can go stale while nobody touches the page. */
export function useApproval(id: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["forge", "approval", id],
    queryFn: () => get<ApprovalState>(`/forge/adaptations/${id}/approval`),
    enabled: Boolean(id) && enabled,
  });
}

/** The whole thread, oldest first. Ticks while a turn is pending, and stops when none is. */
export function useConversation(id: string | undefined) {
  return useQuery({
    queryKey: ["forge", "messages", id],
    queryFn: () => get<Turn[]>(`/forge/adaptations/${id}/messages`),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      query.state.data?.some((turn) => turn.state === "pending") ? TICK : false,
  });
}

function useForgeMutation<T>(run: (body: T) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    // Every forge write moves an adaptation or the catalogue, and both are read by the overview
    // and the queue. Invalidating the section rather than one key is what stops a page showing
    // a count that the row beneath it disagrees with.
    onSuccess: () => client.invalidateQueries({ queryKey: ["forge"] }),
  });
}

export function useSyncSources() {
  return useForgeMutation<string>((source) =>
    post<{ source: string; queued: boolean }>("/forge/sources/sync", { source }),
  );
}

export function useStartAdaptation() {
  return useForgeMutation<string>((catalogueItemId) =>
    post<{ adaptation: AdaptationRow; queued: boolean }>("/forge/adaptations", {
      catalogue_item_id: catalogueItemId,
    }),
  );
}

export function useRetryAdaptation() {
  return useForgeMutation<{ id: string; reason: string }>(({ id, reason }) =>
    post<unknown>(`/forge/adaptations/${id}/retry`, { reason }),
  );
}

export function useAsk(id: string) {
  return useForgeMutation<string>((message) =>
    post<{ message: Turn; queued: boolean }>(`/forge/adaptations/${id}/messages`, { message }),
  );
}

/** **Not `reject`** — §1.6's word, and the reason is that a terminal word makes an ordinary
 *  correction feel destructive. The candidate being corrected is kept. */
export function useRequestChanges(id: string) {
  return useForgeMutation<string>((reason) =>
    post<unknown>(`/forge/adaptations/${id}/changes`, { reason }),
  );
}

export function useApprove(id: string) {
  return useForgeMutation<{ reason: string; rule_candidate_ids: string[] }>((body) =>
    post<unknown>(`/forge/adaptations/${id}/approve`, body),
  );
}

export function useArchive(id: string) {
  return useForgeMutation<string>((reason) =>
    post<unknown>(`/forge/adaptations/${id}/archive`, { reason }),
  );
}
