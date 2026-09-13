import type { GraphPort, IoGraph } from "../../api/registry";

/** The semantic input/output graph — §8.5, and it is functional rather than decoration.
 *
 * **Rendered from the candidate contract and from nothing else.** Every port here is a
 * `GraphPort` the server assembled out of the scaffold's filled fields and its open holes; the
 * page holds no second copy of what a port is, so there is no state that can disagree with the
 * fields tab about whether `consumes.reads.type_id` is settled.
 *
 * **Three marks, because there are three states and not two.** Solid is read from the source,
 * outlined blue is a model's proposal, coral dashed is still open — §8.5's own words. Drawing a
 * proposal and a source fact the same way is the single failure a review exists to catch, and
 * collapsing *open* into *proposed* would draw an unanswered question as an answer.
 */

const LOOK: Record<string, { border: string; tint: string; word: string }> = {
  derived: { border: "border-[var(--rail)]", tint: "bg-[var(--node)]", word: "from the source" },
  model: { border: "border-[var(--link)]", tint: "bg-[var(--link-soft)]", word: "AI proposed" },
  human: { border: "border-[var(--pea)]", tint: "bg-[var(--pea-soft)]", word: "answered by hand" },
  open: {
    border: "border-dashed border-[var(--fault)]",
    tint: "bg-[var(--undecided-soft)]",
    word: "unresolved",
  },
};

function Port({
  port,
  onSelect,
  selected,
}: {
  port: GraphPort;
  onSelect: (id: string) => void;
  selected: string;
}) {
  const look = LOOK[port.origin] ?? LOOK.open;
  const target = port.hole_id || port.channel;
  return (
    <button
      type="button"
      onClick={() => onSelect(target)}
      aria-pressed={selected === target}
      title={look.word}
      className={`lift text-left border-l-[3px] border rounded-[var(--r)] px-[13px] py-[11px]
                  min-w-[150px] ${look.border} ${look.tint} ${
                    selected === target ? "shadow-[var(--ring)]" : ""
                  }`}
    >
      <div className="font-data text-[10.5px] text-link">{port.type_id || port.channel}</div>
      <div className="font-data text-[9.5px] text-ink-3 pt-1">
        {/* **States in brackets, and an empty pair is not drawn.** `[]` beside a type reads as
            *no states*, which is a claim; a port whose states were never asked says nothing. */}
        {port.states.length > 0 ? `[${port.states.join(", ")}]` : port.name}
      </div>
    </button>
  );
}

function Wire() {
  return <div className="flex-[0_0_44px] h-px bg-[var(--port-line)]" aria-hidden="true" />;
}

export function ReviewGraph({
  graph,
  selected,
  onSelect,
  onParams,
}: {
  graph: IoGraph;
  selected: string;
  onSelect: (id: string) => void;
  onParams: () => void;
}) {
  return (
    <>
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[13px]">
        Input / output
      </div>
      <div className="border border-line bg-surface rounded-[var(--r)] px-5 py-[22px]">
        <div className="overflow-x-auto">
          <div className="flex items-center gap-4 min-w-[640px]">
            <div className="flex flex-col gap-2">
              {graph.consumes.length === 0 ? (
                <span className="font-data text-label text-ink-3">no inputs declared yet</span>
              ) : (
                graph.consumes.map((port) => (
                  <Port key={port.channel} port={port} selected={selected} onSelect={onSelect} />
                ))
              )}
            </div>
            <Wire />
            <button
              type="button"
              onClick={onParams}
              className="lift text-left border border-[var(--node-line)] border-l-[3px]
                         border-l-[var(--rail)] bg-[var(--node)] rounded-[var(--r)] px-[13px] py-[11px]
                         min-w-[172px]"
            >
              <div className="text-body font-medium">{graph.process || "—"}</div>
              {/* §8.5: *the parameter count on the process node opens the parameter table*. A
                  count that is not a control is a number a reviewer has to go and find. */}
              <div className="font-data text-[9.5px] text-link pt-[5px]">
                {graph.params} parameter{graph.params === 1 ? "" : "s"} ›
              </div>
            </button>
            <Wire />
            <div className="flex flex-col gap-2">
              {graph.produces.length === 0 ? (
                <span className="font-data text-label text-ink-3">no outputs declared yet</span>
              ) : (
                graph.produces.map((port) => (
                  <Port key={port.channel} port={port} selected={selected} onSelect={onSelect} />
                ))
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-5 pt-[18px] mt-[18px] border-t border-line-soft">
          {(["derived", "model", "open"] as const).map((origin) => (
            <span key={origin} className="flex items-center gap-[7px] text-secondary text-ink-3">
              <span
                aria-hidden="true"
                className={`w-[11px] h-[11px] border ${LOOK[origin].border} ${LOOK[origin].tint}`}
              />
              {LOOK[origin].word}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}
