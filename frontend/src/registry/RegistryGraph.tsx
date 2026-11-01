import { Failed, Loading } from "../ui/States";
import { graphLayout } from "./graphLayout";
import { useChoices } from "./parts/useChoices";
import { useFilters } from "./useCatalogue";

const WIDTH = 190;
const HEIGHT = 44;
const GAP_X = 56;
const GAP_Y = 12;

/** What the registry can do today: its tools, joined by what the router would connect. Picking
 *  one selects it in the list below. */
export function RegistryGraph({ states }: { states: Record<string, string> }) {
  const filters = useFilters();
  const choices = useChoices(true);
  if (choices.isPending) return <Loading what="the registry" />;
  if (choices.isError) return <Failed error={choices.error} />;
  const { nodes, edges } = graphLayout(choices.data.tools);
  const at = new Map(nodes.map((n) => [n.id, n]));
  const left = (column: number) => column * (WIDTH + GAP_X);
  const top = (row: number) => row * (HEIGHT + GAP_Y);
  const width = left(Math.max(0, ...nodes.map((n) => n.column))) + WIDTH;
  const height = top(Math.max(0, ...nodes.map((n) => n.row))) + HEIGHT;

  return (
    <section aria-labelledby="graph-title" className="bg-surface border border-line rounded-panel px-[16px] py-[12px] flex flex-col gap-2">
      <div className="flex flex-wrap justify-between items-baseline gap-x-[14px]">
        <h2 id="graph-title" className="m-0 text-[15px] font-semibold">What your registry can do today</h2>
        <span className="text-[12.5px] text-ink-2">{nodes.length} tools, joined by what connects. Pick one to see it.</span>
      </div>
      <div className="overflow-x-auto [contain:inline-size]">
        <div className="relative" style={{ width, height }}>
          <svg aria-hidden="true" className="graph-lines" width={width} height={height}>
            {edges.map(({ from, to }) => {
              const a = at.get(from);
              const b = at.get(to);
              if (!a || !b) return null;
              const x1 = left(a.column) + WIDTH;
              const y1 = top(a.row) + HEIGHT / 2;
              const x2 = left(b.column);
              const y2 = top(b.row) + HEIGHT / 2;
              return <path key={`${from}>${to}`} d={`M ${x1} ${y1} C ${x1 + 28} ${y1}, ${x2 - 28} ${y2}, ${x2} ${y2}`} />;
            })}
          </svg>
          {nodes.map((node) => (
            <button key={node.id} type="button" className="graph-node" aria-pressed={filters.module === node.path}
                    style={{ left: left(node.column), top: top(node.row), width: WIDTH, height: HEIGHT }}
                    onClick={() => filters.set("module", [node.path])}>
              <span className="flex items-center gap-[6px] font-data text-[12px] whitespace-nowrap overflow-hidden">
                <span className="dot" data-state={states[node.path] ?? "imported"} aria-hidden="true" />{node.path}
              </span>
              <span className="block truncate text-[11px] text-ink-3">{node.job}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
