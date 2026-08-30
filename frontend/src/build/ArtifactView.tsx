import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { Failed, Loading } from "../ui/States";

type Artifact = components["schemas"]["Artifact"];

/** The other view of the canvas: **the artifact itself.**
 *
 * `n-bartifact`: *pipeline.yml is the pipeline, so the other view of the canvas is the artifact
 * itself. Every value carries its why: tier, rule, premise. Open values are null and marked.*
 *
 * ═══ IT SHOWS THE FILE, NOT A RENDERING OF THE FILE ═══════════════════════════════════════
 *
 * `CLAUDE.md`: *`pipeline.yml` IS the pipeline* — one artifact carrying the goal, every step and
 * setting with a `why:`, every contract pinned by content digest. So this shows the bytes.
 *
 * A prettier structured view would have to decide what to include, and every such decision is a
 * chance for the screen and the file to disagree — which is exactly the gap a reader opens this
 * view to close. *Every value carries its why* is not a feature this component implements; it is
 * a property of the document, visible because the document is what is on screen.
 *
 * **Section jumps are a row of chips, not another left-hand list** — the canvas is explicit, and
 * a third column is what `impl-settled` spent a phase removing.
 */
export function ArtifactView({ draftId }: { draftId: string | null }) {
  const box = useRef<HTMLPreElement>(null);

  const artifact = useQuery({
    queryKey: ["artifact", draftId],
    queryFn: () => get<Artifact>(`/pipeline/drafts/${draftId}/artifact`),
    enabled: Boolean(draftId),
    retry: false,
  });

  // **A draft with no artifact is not an error and not an empty document.** `keep` is what
  // writes one, and saying so is more useful than either a blank pane or a red message.
  if (!draftId || artifact.error) {
    return (
      <div className="p-6 max-w-[60ch]">
        <p className="text-body text-ink m-0">This pipeline has not been kept yet.</p>
        <p className="text-secondary text-ink-3 mt-2 mb-0">
          <b className="font-normal text-ink-2">Run</b> keeps it, which validates the graph and
          writes the <span className="font-data">pipeline.yml</span> this view shows. Until then
          there is no artifact — a draft is a row, and a pipeline is a file.
        </p>
      </div>
    );
  }

  if (artifact.isLoading) return <Loading what="the artifact" />;
  if (!artifact.data) return <Failed error="nothing came back" />;

  const jump = (section: string) => {
    const pre = box.current;
    if (!pre) return;
    const line = artifact.data.text.split("\n").findIndex((l) => l.startsWith(`${section}:`));
    if (line < 0) return;
    // Scroll proportionally rather than measuring a line box: the content is one `<pre>` with a
    // uniform line height, so the ratio is exact and needs no layout read.
    pre.scrollTop = (line / artifact.data.text.split("\n").length) * pre.scrollHeight;
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-line flex-wrap">
        <span className="text-label uppercase tracking-[.13em] text-ink-3">Jump to</span>
        {artifact.data.sections.map((section) => (
          <button
            key={section}
            type="button"
            data-testid="artifact-jump"
            onClick={() => jump(section)}
            className="px-2 py-0.5 rounded-r border border-line bg-transparent cursor-pointer
                       font-data text-secondary text-ink-2 hover:text-ink lift"
          >
            {section}
          </button>
        ))}
      </div>

      <pre
        ref={box}
        data-testid="artifact"
        className="flex-1 min-h-0 overflow-auto m-0 p-4 font-data text-secondary text-ink-2
                   whitespace-pre"
      >
        {artifact.data.text}
      </pre>
    </div>
  );
}
