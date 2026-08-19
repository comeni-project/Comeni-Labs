import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { Canvas } from "./Canvas";
import { Grip, RAIL, useWidth } from "./Panels";
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
  const { view, onWheel, onPointerDown, reset, nudge } = useView();

  const { data, isLoading, error } = useQuery({
    queryKey: ["pipeline", "example"],
    queryFn: () => get<Built>("/pipeline/example"),
  });

  const blocking = data?.needs_review.length ?? 0;

  return (
    <div data-testid="builder" className="grid grid-cols-[auto_5px_1fr_5px_auto] h-full">
      <Side
        side="left"
        title="Modules"
        width={left.width}
        collapsed={left.collapsed}
        onExpand={() => left.setCollapsed(false)}
      >
        <p className="px-4 py-3 text-secondary text-ink-3">
          The module picker arrives with phase 8.
        </p>
      </Side>
      <Grip
        side="left"
        onPointerDown={(e) => left.onPointerDown(e, "left")}
        onCollapse={() => left.setCollapsed(true)}
        onNudge={() => {}}
      />

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
          </div>
        }
      >
        {isLoading && <Loading what="the pipeline" />}
        {error && <Failed error={error} />}
        {/* Phase 4 fills this. An empty canvas here is the phase-3 deliverable. */}
      </Canvas>

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
        <p className="px-4 py-3 text-secondary text-ink-3">
          Step details and review arrive with phase 7.
        </p>
        <button
          data-testid="collapse-right"
          onClick={() => right.setCollapsed(true)}
          className="mx-4 text-secondary text-ink-3 bg-transparent border-0 cursor-pointer p-0"
        >
          collapse
        </button>
      </Side>
    </div>
  );
}

const zoomBtn =
  "px-2 py-1 rounded-r bg-transparent border-0 cursor-pointer text-secondary text-ink-2 " +
  "hover:text-ink hover:bg-surface-2";
