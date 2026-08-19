import type { components } from "../api/schema";
import { Term } from "../ui/Term";

type Built = components["schemas"]["BuiltPipeline"];

const TIER: Record<number, string> = {
  1: "bg-pea",
  2: "bg-pea opacity-[.42]",
  3: "bg-[var(--measured)]",
  4: "bg-[var(--undecided)]",
};

/** What is in this pipeline, in the order it runs.
 *
 * **Not a picker of every module in the registry.** `dashboard.md` §4 designs the left panel as a
 * catalogue you drag from, which belongs with drag-to-connect — and that is `dashboard.md` §9's
 * own gap list, not built here. What a person needs on a canvas they cannot yet edit is a way to
 * find a step without hunting for its box, and that is this.
 *
 * Browsing the registry already has a home: `Tools`. A second catalogue here would be the
 * duplication 3D spent a phase removing.
 */
export function Steps({
  data,
  selected,
  onSelect,
}: {
  data: Built;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const order = data.layout.nodes
    .slice()
    .sort((a, b) => a.rank - b.rank || a.x - b.x)
    .map((node) => data.steps.find((step) => step.id === node.id))
    .filter((step): step is NonNullable<typeof step> => Boolean(step));

  if (order.length === 0) {
    return (
      <p className="px-4 py-3 text-body text-ink-2 m-0">
        This goal resolved to no steps. Nothing in the registry produces what it asks for.
      </p>
    );
  }

  return (
    <div>
      <p className="px-4 pt-3 pb-2 text-secondary text-ink-3 m-0">
        In the order they run. Each carries the <Term of="contract">contract</Term> that fills it.
      </p>
      {order.map((step) => (
        <button
          key={step.id}
          data-testid="step-row"
          data-selected={selected === step.id || undefined}
          onClick={() => onSelect(step.id)}
          className="w-full text-left px-4 py-2 flex items-baseline gap-3 bg-transparent
                     border-0 border-b border-line cursor-pointer hover:bg-surface-2
                     data-[selected]:bg-surface-2 data-[selected]:font-semibold"
        >
          <span
            aria-hidden
            className={`w-1 h-4 self-center shrink-0 rounded-[1px] ${TIER[step.tier] ?? ""}`}
          />
          <span className="font-data text-body text-ink truncate">{step.process}</span>
          {step.settings.some((s) => s.tier === 4) && (
            <span className="ml-auto shrink-0 text-label text-[var(--undecided)]">!</span>
          )}
        </button>
      ))}
    </div>
  );
}
