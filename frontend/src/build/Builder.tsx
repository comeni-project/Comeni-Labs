import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { Canvas } from "./Canvas";
import { Node } from "./Node";
import { LeftPanel } from "./LeftPanel";
import { Settings } from "./Settings";
import { Grip, RAIL, useWidth } from "./Panels";
import { Provenance } from "./Provenance";
import { Rail } from "./Rail";
import { Wires } from "./Wires";
import { useView } from "./useView";

type Built = components["schemas"]["BuiltPipeline"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** A panel that collapses to a 42px stub with a vertical label — and keeps its count. */
function Side({
  side,
  title,
  width,
  collapsed,
  onExpand,
  badge,
  children,
}: {
  side: "left" | "right";
  title: string;
  width: number;
  collapsed: boolean;
  onExpand: () => void;
  badge?: number;
  children?: React.ReactNode;
}) {
  const testid = side === "left" ? "modules" : "rail";
  if (collapsed) {
    return (
      <button
        data-testid={testid}
        data-collapsed="true"
        onClick={onExpand}
        style={{ width: RAIL }}
        className="shrink-0 flex flex-col items-center gap-3 py-4 bg-surface cursor-pointer
                   border-0 border-l border-line text-ink-3 hover:text-ink"
      >
        <span className="[writing-mode:vertical-rl] text-label uppercase tracking-[.13em]">
          {title}
        </span>
        {/* **The count survives the collapse.** `dashboard.md` §4: hiding the panel must never
            hide what is blocking your run. */}
        {badge !== undefined && badge > 0 && (
          <span className="font-data text-secondary text-[var(--undecided)]">{badge}</span>
        )}
      </button>
    );
  }
  return (
    <div
      data-testid={testid}
      data-collapsed="false"
      style={{ width }}
      className="shrink-0 flex flex-col bg-surface overflow-hidden"
    >
      <div className="flex items-baseline gap-3 px-4 py-3 border-b border-line">
        <span className={label}>{title}</span>
        {badge !== undefined && badge > 0 && (
          <span className="ml-auto font-data text-secondary text-[var(--undecided)]">{badge}</span>
        )}
      </div>
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}

/** Mendel — the pipeline builder.
 *
 * **Phase 3 is the shell and nothing in it**, deliberately: three columns that resize and
 * collapse, and a canvas that pans and zooms over an empty surface. Getting the frame wrong and
 * then building five phases on top of it is the failure this plan's checkpoints exist to stop.
 *
 * Every measurement here is `docs/design/dashboard.md` §4's — 190–430 left, 280–560 right, a
 * 42px collapsed rail, a 22px grid, zoom clamped 0.3–2.2 — and the pan/zoom maths is ported from
 * `dashboard.html` rather than reinvented.
 */
export function Builder() {
  useTitle("Builder");
  const left = useWidth(232, 190, 430);
  const right = useWidth(320, 280, 560);
  const { view, onWheel, onPointerDown, reset, nudge, fit } = useView();
  const box = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [isolated, setIsolated] = useState<string | null>(null);
  const [carded, setCarded] = useState<string | null>(null);
  // **Node offsets live here, not in each node.** They were local state, which meant a dragged
  // node left its wires behind — the graph broke the moment you touched it. The wires read them
  // too, so both ends of a line move with the box they belong to.
  const [offsets, setOffsets] = useState<Record<string, { x: number; y: number }>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ["pipeline", "example"],
    queryFn: () => get<Built>("/pipeline/example"),
  });

  const blocking = data?.needs_review.length ?? 0;

  return (
    <div className="grid grid-rows-[38px_1fr] h-full overflow-hidden">
      <div className="flex items-center gap-4 px-6 border-b border-line bg-surface">
        <span className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
          RNA-seq spine
        </span>
        {/* **One Run button, in the nav.** `dashboard.md` §6 records that there were two — one
            here and one in the review strip — and both were disabled by the same condition, so
            the second said nothing the first had not. The blocking count beside it is the part
            that was load-bearing. */}
        <button
          disabled
          title="Running a pipeline is Wiener's job, and Wiener is not built."
          className="ml-auto px-3 py-1 rounded-r text-body font-semibold bg-pea
                     text-[var(--on-pea)] border-0 opacity-40 cursor-not-allowed"
        >
          Run pipeline
        </button>
        {blocking > 0 && (
          <span data-testid="blocking" className="text-secondary text-[var(--undecided)]">
            <b className="font-data">{blocking}</b> to decide
          </span>
        )}
      </div>
      <div
        ref={box}
        data-testid="builder"
        className="grid grid-cols-[auto_5px_1fr_5px_auto] overflow-hidden"
      >
      <Side
        side="left"
        title="Modules"
        width={left.width}
        collapsed={left.collapsed}
        onExpand={() => left.setCollapsed(false)}
      >
        {data && <LeftPanel data={data} selected={selected} onSelect={setSelected} />}
      </Side>
      <Grip
        side="left"
        onPointerDown={(e) => left.onPointerDown(e, "left")}
        onCollapse={() => left.setCollapsed(true)}
        onNudge={() => {}}
      />

      <div className="flex flex-col overflow-hidden">
        {data && (
          <Provenance data={data} isolated={isolated} onIsolate={setIsolated} />
        )}
        <Canvas
        view={view}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        footer={
          <div
            data-zoomer
            className="absolute right-4 bottom-4 flex items-center gap-1 rounded-r
                       border border-line bg-surface px-1 py-1 shadow-[0_1px_2px_var(--shadow)]"
          >
            <button onClick={() => nudge(-0.1)} aria-label="zoom out" className={zoomBtn}>
              −
            </button>
            <span
              data-testid="zoom"
              data-k={view.k}
              className="font-data text-secondary text-ink-3 w-11 text-center tabular-nums"
            >
              {Math.round(view.k * 100)}%
            </span>
            <button onClick={() => nudge(0.1)} aria-label="zoom in" className={zoomBtn}>
              +
            </button>
            <button onClick={reset} aria-label="reset the view" className={zoomBtn}>
              reset
            </button>
            <button
              aria-label="fit the pipeline"
              className={zoomBtn}
              onClick={() => {
                const r = box.current?.getBoundingClientRect();
                if (data && r) fit(data.layout.width, data.layout.height, r.width, r.height);
              }}
            >
              fit
            </button>
          </div>
        }
      >
        {isLoading && <Loading what="the pipeline" />}
        {error && <Failed error={error} />}
        {data && (
          <>
            {/* Wires first, so a node draws over the line that reaches it rather than under. */}
            <Wires
              wires={data.layout.wires}
              tierOf={(id) => data.layout.nodes.find((n) => n.id === id)?.tier ?? 2}
              offsets={offsets}
              width={data.layout.width}
              height={data.layout.height}
            />
            {data.layout.nodes.map((placed) => (
              <Node
                key={placed.id}
                placed={placed}
                step={data.steps.find((s) => s.id === placed.id)}
                zoom={view.k}
                dim={isolated !== null && String(placed.tier) !== isolated}
                selected={selected === placed.id}
                onSelect={() => setSelected(placed.id)}
                onOpenSettings={() => setCarded(placed.id)}
                offset={offsets[placed.id] ?? { x: 0, y: 0 }}
                onDrag={(by) => setOffsets((all) => ({ ...all, [placed.id]: by }))}
              />
            ))}
          </>
        )}
        </Canvas>
      </div>

      <Grip
        side="right"
        onPointerDown={(e) => right.onPointerDown(e, "right")}
        onCollapse={() => right.setCollapsed(true)}
        onNudge={() => {}}
      />
      <Side
        side="right"
        title="Review"
        width={right.width}
        collapsed={right.collapsed}
        onExpand={() => right.setCollapsed(false)}
        badge={blocking}
      >
        {data && (
          <Rail
            data={data}
            selected={selected}
            onSelect={setSelected}
            onCollapse={() => right.setCollapsed(true)}
          />
        )}
      </Side>
      </div>

      {/* **A modal, opened from the node's own button** — `dashboard.md` §5. The rail's Step tab
          shows the same card for the selected step; this is the path from the canvas, which is
          where a person is when they wonder what a step is set to. */}
      {carded && data && (
        <div
          className="fixed inset-0 z-40 flex items-start justify-center pt-[10vh] px-6
                     bg-[color-mix(in_srgb,var(--ink)_35%,transparent)]"
          onClick={() => setCarded(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[560px] max-h-[70vh] overflow-auto rounded-r border
                       border-line bg-surface shadow-[0_4px_16px_var(--shadow)]"
          >
            <Settings
              step={data.steps.find((s) => s.id === carded)!}
              onClose={() => setCarded(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

const zoomBtn =
  "px-2 py-1 rounded-r bg-transparent border-0 cursor-pointer text-secondary text-ink-2 " +
  "hover:text-ink hover:bg-surface-2";
