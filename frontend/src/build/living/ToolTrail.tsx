import { useState } from "react";

import type { AuthoringBlock } from "../../api/types";

type ToolLine = Extract<AuthoringBlock, { kind: "tool" }>;

/** **What the agent did, as it did it** (#463): one line per tool call while the turn runs, so the
 *  person sees it working rather than a spinner; folded into *How I got here · N steps* once the
 *  turn has said something, so the answer leads and the trail stays one click away. */
export function ToolTrail({ tools, live }: { tools: ToolLine[]; live: boolean }) {
  const [open, setOpen] = useState(false);
  if (tools.length === 0 && !live) return null;
  if (!live) {
    return (
      <div className="flex flex-col gap-1">
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
                className="self-start bg-transparent border-0 p-0 text-[12px] text-ink-3 cursor-pointer
                           hover:text-ink-2 focus-visible:shadow-[var(--ring)]">
          <span aria-hidden className="inline-block w-[10px]">{open ? "▾" : "▸"}</span>
          How I got here · {tools.length} {tools.length === 1 ? "step" : "steps"}
        </button>
        {open && <Lines tools={tools} />}
      </div>
    );
  }
  return (
    <div role="status" aria-label="working" className="flex flex-col gap-1">
      <Lines tools={tools} />
      <p className="m-0 flex items-center gap-2 text-[12px] text-ink-2">
        <span aria-hidden className="agent-pulse w-[6px] h-[6px] rounded-full" style={{ background: "var(--now)" }} />
        {tools.length === 0 ? "Reading what you said…" : "Working…"}
      </p>
    </div>
  );
}

function Lines({ tools }: { tools: ToolLine[] }) {
  return (
    <ol className="m-0 p-0 pl-[10px] flex flex-col gap-[3px] border-l" style={{ borderColor: "var(--line)" }}>
      {tools.map((t) => (
        <li key={t.id} className="list-none text-[12px] leading-[1.45]">
          <span className={t.ok ? "text-ink-2" : "text-needs-you-ink"}>{t.label}</span>
          {t.summary && <span className="text-ink-3"> — {t.summary}</span>}
        </li>
      ))}
    </ol>
  );
}
