import { useState } from "react";

import type { AuthoringBlock } from "../../api/types";

type ToolLine = Extract<AuthoringBlock, { kind: "tool" }>;
type Message = Extract<AuthoringBlock, { kind: "message" }>;
/** A line of the trail: a tool the agent used, or what it said beside one (#504). */
export type TrailStep = ToolLine | Message;

/** **What the agent is doing, as it does it** (#463, #504): what it says before each round of
 *  tools and each tool in order, the one running now marked live, and *Thinking…* while the model
 *  itself is answering. Once the turn has answered, all of it folds into *How I got here · N
 *  steps*, so the answer leads and the trail stays one click away. */
export function ToolTrail({ steps, live }: { steps: TrailStep[]; live: boolean }) {
  const [open, setOpen] = useState(false);
  const tools = steps.filter((s) => s.kind === "tool").length;
  if (steps.length === 0 && !live) return null;
  if (!live) {
    if (tools === 0) return null;
    return (
      <div className="flex flex-col gap-1">
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
                className="self-start bg-transparent border-0 p-0 text-[12px] text-ink-3 cursor-pointer
                           hover:text-ink-2 focus-visible:shadow-[var(--ring)]">
          <span aria-hidden className="inline-block w-[10px]">{open ? "▾" : "▸"}</span>
          How I got here · {tools} {tools === 1 ? "step" : "steps"}
        </button>
        {open && <Lines steps={steps} />}
      </div>
    );
  }
  const running = steps.at(-1)?.kind === "tool" && (steps.at(-1) as ToolLine).running;
  return (
    <div role="status" aria-label="working" className="flex flex-col gap-1">
      <Lines steps={steps} />
      {!running && (
        <p className="m-0 flex items-center gap-2 text-[12px] text-ink-2">
          <Dot />
          Thinking…
        </p>
      )}
    </div>
  );
}

function Dot() {
  return <span aria-hidden className="agent-pulse shrink-0 w-[6px] h-[6px] rounded-full" style={{ background: "var(--now)" }} />;
}

function Lines({ steps }: { steps: TrailStep[] }) {
  if (steps.length === 0) return null;
  return (
    <ol className="m-0 p-0 pl-[10px] flex flex-col gap-[3px] border-l" style={{ borderColor: "var(--line)" }}>
      {steps.map((s) => s.kind === "message" ? (
        <li key={s.id} className="list-none text-[12.5px] leading-[1.5] text-ink-2 whitespace-pre-wrap">{s.text}</li>
      ) : s.running ? (
        <li key={s.id} data-testid="running" className="list-none flex items-center gap-2 text-[12px] text-ink">
          <Dot />
          {s.label}…
        </li>
      ) : (
        <li key={s.id} className="list-none text-[12px] leading-[1.45]">
          <span className={s.ok ? "text-ink-3" : "text-needs-you-ink"}>{s.label}</span>
          {s.summary && <span className="text-ink-3"> — {s.summary}</span>}
        </li>
      ))}
    </ol>
  );
}
