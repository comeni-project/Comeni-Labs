import { useState } from "react";
import { useNavigate } from "react-router";

import { useAiConfigured } from "./useAiConfigured";
import { useBegin } from "./useBegin";

/** Describe a new analysis, once the lab already has work (issue 229).
 *
 * `First` is the whole page when a lab has nothing; this is the same door on a page that has
 * something, so it is one line above the work rather than a composition. It sends what `First`
 * sends — a sentence and the default mode, `build` — and the mode choice stays on the first page
 * and in the session. **Absence is absence**: without a model there is no bar here at all, and
 * *New pipeline* is still the canvas.
 */
export function Describe() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const model = useAiConfigured();
  const begin = useBegin((started) => navigate(`/build?session=${started.session.id}`));
  if (!model.configured) return null;
  const ready = prompt.trim().length > 0 && !begin.isPending;

  return (
    <form
      aria-label="describe a new analysis"
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) begin.mutate({ prompt: prompt.trim() });
      }}
      className="flex flex-col gap-2"
    >
      <div className="flex flex-wrap items-stretch gap-3">
        <label
          className="grow min-w-[240px] flex items-center gap-3 px-[16px] py-[12px] rounded-panel cursor-text"
          style={{ background: "var(--paper-2)", border: "1px solid var(--now-line)" }}
        >
          <span aria-hidden className="font-data text-[13px]" style={{ color: "var(--now-ink)" }}>
            &rsaquo;
          </span>
          <input
            value={prompt}
            disabled={begin.isPending}
            onChange={(e) => setPrompt(e.target.value)}
            aria-label="describe a new analysis"
            className="grow bg-transparent border-0 outline-none text-[15px] text-ink
                       placeholder:text-[color:var(--ink-3)]"
            placeholder="describe a new analysis — e.g. variants from whole-genome sequencing"
          />
        </label>
        <button
          type="submit"
          disabled={!ready}
          className="px-[20px] py-[10px] border-0 rounded-button cursor-pointer font-semibold text-[13.5px]
                     bg-action text-on-action shadow-raise disabled:cursor-not-allowed disabled:opacity-40"
        >
          {begin.isPending ? "Starting…" : "Start"}
        </button>
      </div>
      {begin.error && (
        <p role="alert" className="m-0 text-[12px] text-needs-you-ink">{begin.error.message}</p>
      )}
    </form>
  );
}
