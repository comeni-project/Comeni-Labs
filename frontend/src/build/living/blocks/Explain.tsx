import { useState, type ReactNode } from "react";

import type { Explanation } from "../../../api/types";
import { useBrowserSetting } from "../../../preferences/useBrowserSetting";

/** What a question is about and why it is asked (Part I.1).
 *
 * `what` is the registry's own words, marked *curated*; why it is needed is the engine's, from
 * the steps that can read the thing or the rule a measurement decides, marked *engine*. Open or
 * collapsed as Settings → Building → *Explain each question* says; each one can still be folded
 * by hand, and that choice is this card's alone.
 */
export function Explain({ explanation }: { explanation: Explanation }) {
  const [start] = useBrowserSetting("building.explain", "open");
  const [open, setOpen] = useState(start !== "collapsed");
  const { what, needed, reads } = explanation;
  if (!what && needed.length === 0) return null;
  return (
    <div data-testid="explain" className="mb-3 border-l pl-[10px]"
         style={{ borderColor: "var(--line-2)" }}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="text-[11.5px] text-link bg-transparent border-0 p-0 cursor-pointer">
        What is this? {open ? "▾" : "›"}
      </button>
      {open && (
        <div className="mt-1 flex flex-col gap-2">
          {what && <Half mark="curated"><p className="m-0">{what}</p></Half>}
          {needed.length > 0 && (
            <Half mark="engine">
              <p className="m-0">
                {reads === "rule" ? "It decides: " : "Steps that can read it: "}
                {needed.map((reason, i) => (
                  <span key={reason.text}>
                    {i > 0 && (reads === "rule" ? "; " : ", ")}
                    <span title={reason.detail ?? undefined}>{reason.text}</span>
                    {reads === "rule" && reason.detail && (
                      <span className="text-ink-3"> ({reason.detail})</span>
                    )}
                  </span>
                ))}
                {reads === "steps" && needed.length > 1
                  ? ". Which of them run depends on choices still to come."
                  : "."}
              </p>
            </Half>
          )}
        </div>
      )}
    </div>
  );
}

function Half({ mark, children }: { mark: "curated" | "engine"; children: ReactNode }) {
  return (
    <div className="text-[12px] text-ink-2">
      {children}
      <span className="font-data text-[9.5px] text-ink-4">{mark}</span>
    </div>
  );
}

const and = (items: string[]) =>
  items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")}, and ${items.at(-1)}`;

/** The line above the upload: what a sample answers, never how it is read (Part I.1 §5). */
export function uploadHeadline(e: Explanation): string | null {
  if (e.read_by === "ai") {
    return "Have a sample to hand? Upload it and the AI will read it for you. It shows you what "
      + "it found, and nothing is used until you've confirmed it.";
  }
  if (e.read_by !== "inspector") return null;
  if (e.settles.length === 0) return "Have a sample to hand? Upload it and we'll measure it.";
  return `Have a sample to hand? Upload it and we'll measure the rest: ${and(e.settles)}. `
    + `You won't need to answer ${e.settles.length === 1 ? "that" : "those"} yourself.`;
}
