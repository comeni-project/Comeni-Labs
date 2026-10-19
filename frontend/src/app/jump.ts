import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";

type DraftRow = components["schemas"]["DraftRow"];
type RunRow = wiener["schemas"]["RunRow"];

/** Somewhere the jump search can take you: a saved pipeline or a run. */
export type Target = {
  kind: "pipeline" | "run";
  id: string;
  label: string;
  detail: string;
  to: string;
  phase?: string;
  /** When a run was submitted (ISO 8601). */
  when?: string;
};

const EACH = 8;

/** The pipelines and runs that match what was typed, at most eight of each.
 *
 * Case-insensitive; a pipeline matches on its name, a run on its name or the start of its id.
 * Pipelines come newest first; runs keep the order Wiener gives (newest first). Nothing typed
 * lists the first eight of each. The addresses are the ones Home's links use. */
export function jumpTargets(query: string, drafts: DraftRow[], runs: RunRow[]): {
  pipelines: Target[];
  runs: Target[];
} {
  const q = query.trim().toLowerCase();
  const pipelines = [...drafts]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .filter((d) => !q || d.name.toLowerCase().includes(q))
    .slice(0, EACH)
    .map((d): Target => ({
      kind: "pipeline", id: d.id, label: d.name, detail: `${d.steps} steps`, to: `/build?draft=${d.id}`,
    }));
  const found = runs
    .filter((r) => !q || r.name.toLowerCase().includes(q) || r.id.toLowerCase().startsWith(q))
    .slice(0, EACH)
    .map((r): Target => ({
      kind: "run", id: r.id, label: r.name || `run ${r.id.slice(0, 8)}`, detail: r.phase,
      to: `/runs/${r.id}`, phase: r.phase, when: r.submitted_at,
    }));
  return { pipelines, runs: found };
}
