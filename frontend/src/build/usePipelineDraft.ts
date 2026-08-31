/** The draft a person is editing: which one, what it is called, and when it was last saved.
 *
 * ═══ THREE THINGS THAT DID NOT EXIST BEFORE PLAN 4 PHASE 3a ═══════════════════════════════
 *
 * **1. The builder always opened the example.** `Builder` called `useExample()` unconditionally,
 * so `/build?draft=<id>` — which phase 2's Overview links to from every pipeline row — opened
 * the canonical spine instead of your pipeline. Every link on the front door went somewhere else.
 *
 * **2. The autosave had never fired.** `useGraph` takes an optional `save` callback and debounces
 * it at 5s; **nothing ever passed one.** `useKeep`'s docstring said so in 3E and it stayed true
 * for a week. That matters beyond a missing feature: the argument for collapsing Draw → Keep →
 * Gate → Run into one *Run* action is *drafts already autosave, so Keep is an implementation
 * detail wearing a button* — and the premise was **false**. It is true now because this makes it
 * true, which is the right order.
 *
 * **3. The name was a hard-coded string.** `Builder.tsx` rendered `RNA-seq spine` in the header,
 * which is why the 2026-08-29 walk deleted every step, replaced them, and still had the old name
 * on screen. `PipelineDraft.name` has existed since 3E and nothing in the browser ever set it.
 *
 * ═══ WHAT `keep` STILL MEANS ══════════════════════════════════════════════════════════════
 *
 * Autosaving is not keeping. A save writes the **graph** into a row; `keep` validates it, refuses
 * anything illegal, and writes the **`pipeline.yml`** that is the actual artifact —
 * `services/drafts.py` calls that boundary out in its header. So `keep` stays a distinct server
 * verb. What it stops being is a button somebody has to know to press.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { get, post, put } from "../api/client";
import type { DraftGraph, DraftOut } from "../api/types";

export type DraftState = {
  /** The row's id, or `null` until the first save creates one. */
  draftId: string | null;
  name: string;
  rename: (to: string, graph: DraftGraph) => void;
  /** When the graph was last written, as a wall clock. `null` before the first save. */
  savedAt: Date | null;
  saving: boolean;
  /** What went wrong writing it, or `null`.
   *
   *  **Required reading, not optional.** Phase 0's rule and the 2026-08-29 walk's worst defect:
   *  a mutation that fails silently is a lie by omission. `useGraph` keeps `dirty` set on a
   *  failure so the work is not lost — but the person still has to be told it has not landed. */
  error: string | null;
  /** Handed to `useGraph`, which debounces it at 5s of idleness. */
  save: (graph: DraftGraph) => Promise<unknown>;
  /** The graph this draft opened on. `null` when there is no `?draft=` — the caller falls back
   *  to the example, which is what a *New pipeline* click gets. */
  opened: DraftGraph | null;
  loading: boolean;
  /** Why the draft named in the URL could not be opened. Never silently the example instead. */
  openError: string | null;
};

export function usePipelineDraft(): DraftState {
  const [params] = useSearchParams();
  const fromUrl = params.get("draft");
  const client = useQueryClient();

  // **The id lives in a ref, not in state.** The next save has to read it *synchronously* or a
  // second autosave would POST a second draft; `setState` cannot promise that, and the bug it
  // produces — a new pipeline row per edit — is invisible until somebody opens the front door.
  const created = useRef<string | null>(null);
  const draftId = fromUrl ?? created.current;

  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");

  const loaded = useQuery({
    queryKey: ["pipeline-draft", fromUrl],
    queryFn: () => get<DraftOut>(`/pipeline/drafts/${fromUrl}`),
    enabled: Boolean(fromUrl),
    retry: false,
  });

  // The server's name wins on open, and only on open — after that the field a person is typing
  // in is the truth, or their edit would be overwritten by every refetch.
  const adopted = useRef(false);
  useEffect(() => {
    if (loaded.data && !adopted.current) {
      adopted.current = true;
      setName(loaded.data.name);
    }
  }, [loaded.data]);

  const write = useMutation({
    mutationFn: async ({ graph, as }: { graph: DraftGraph; as: string }) => {
      const body = { graph, name: as };
      if (draftId === null) {
        const made = await post<DraftOut>("/pipeline/drafts", body);
        created.current = made.id;
        return made;
      }
      return await put<DraftOut>(`/pipeline/drafts/${draftId}`, body);
    },
    onSuccess: () => {
      setSavedAt(new Date());
      setError(null);
      // The front door reads this listing; a rename or a new pipeline shows there without a
      // reload, and the *by pipeline* table is where somebody goes looking for it.
      void client.invalidateQueries({ queryKey: ["drafts"] });
    },
    onError: (failed) => setError(failed instanceof Error ? failed.message : String(failed)),
  });

  const save = useCallback(
    (graph: DraftGraph) => write.mutateAsync({ graph, as: name }),
    // `name` is a dependency on purpose: a save that captured a stale name would quietly undo
    // a rename that happened between two keystrokes.
    [write, name],
  );

  const rename = useCallback(
    (to: string, graph: DraftGraph) => {
      setName(to);
      // **Renaming carries the graph, and that is not incidental.** `PUT /drafts/{id}` writes
      // `{graph, name}` as one document, so a rename that sent an empty graph would SAVE an
      // empty graph — deleting the pipeline while appearing to relabel it. The first version of
      // this function did exactly that, and it is the sort of defect no test would have been
      // written for because nobody expects a rename to be destructive.
      //
      // It saves immediately rather than waiting for the graph to go idle: the graph may never
      // change again, and a name that only lands if you also move a node is a name that looks
      // saved and is not.
      write.mutate({ graph, as: to });
    },
    [write],
  );

  return {
    draftId,
    name,
    rename,
    savedAt,
    saving: write.isPending,
    error,
    save,
    opened: loaded.data?.graph ?? null,
    loading: Boolean(fromUrl) && loaded.isLoading,
    openError: loaded.error
      ? `this pipeline could not be opened: ${
        loaded.error instanceof Error ? loaded.error.message : String(loaded.error)
      }`
      : null,
  };
}
