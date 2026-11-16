import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { analysisAddress } from "../app/address";
import { Icon } from "../app/rail/icons";
import { useAiConfigured } from "./useAiConfigured";
import { useBegin } from "./useBegin";
import { useStart } from "./useStart";

const QUESTION = "What do you want to find out?";

/** The question box (board: Welcome, Home): a sentence, *Add a folder*, *Start*, and starters
 *  under it. A starter fills the box rather than starting, so the person can still say more.
 *
 *  The model writes a goal from the sentence, never a pipeline (door 1). Without a model the box
 *  says so and *Add a folder* still starts an analysis: Data and Build by hand need no model. */
export function Ask({ starters, large = false }: { starters: string[]; large?: boolean }) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const model = useAiConfigured();
  // The analysis opens on Data: the files come first, then the pipeline (demo walk, beat 1).
  const begin = useBegin((started) => navigate(analysisAddress(started.session.draft_id, "data")));
  const folder = useStart("data");
  const ready = model.configured && prompt.trim().length > 0 && !begin.isPending;
  const error = begin.error ?? folder.error;

  return (
    <div className={`flex flex-col ${large ? "gap-4" : "gap-3"}`}>
      <form aria-label="describe a new analysis"
            onSubmit={(e) => { e.preventDefault(); if (ready) begin.mutate({ prompt: prompt.trim() }); }}
            className={`bg-surface border border-line rounded-panel flex gap-3
                        focus-within:border-now-line focus-within:shadow-[var(--ring)]
                        ${large ? "flex-col px-[18px] pt-4 pb-3 shadow-e2" : "flex-wrap items-center pl-4 pr-2 py-2"}`}>
        <input ref={input} value={prompt} onChange={(e) => setPrompt(e.target.value)}
               disabled={begin.isPending} aria-label={QUESTION} placeholder={QUESTION}
               className={`min-w-0 grow basis-[200px] bg-transparent border-0 outline-none text-ink placeholder:text-ink-3
                           ${large ? "text-[17px]" : "text-[15px]"}`} />
        <div className="flex items-center gap-2 shrink-0 ml-auto">
          <button type="button" onClick={() => folder.mutate()} disabled={folder.isPending}
                  className={`flex items-center gap-2 px-2 py-[6px] border-0 bg-transparent rounded-control
                              text-[13px] text-ink-2 cursor-pointer hover:bg-hover ${large ? "order-first mr-auto" : ""}`}>
            <Icon name="data" size={15} /> Add a folder
          </button>
          <button type="submit" disabled={!ready}
                  className="px-[16px] py-[7px] border-0 rounded-button font-semibold text-[13.5px] cursor-pointer
                             bg-action text-on-action shadow-raise disabled:cursor-not-allowed disabled:opacity-40">
            {begin.isPending ? "Starting…" : "Start"}
          </button>
        </div>
      </form>
      {!model.pending && !model.configured && (
        <p className="m-0 text-[12.5px] text-ink-3">
          <Link to="?settings=models" className="text-now-ink">Set up a model</Link> to describe an
          analysis in words. <em>Add a folder</em> works without one.
        </p>
      )}
      {error && <p role="alert" className="m-0 text-[12.5px] text-needs-you-ink">{error.message}</p>}
      <ul aria-label="Starters" className={`list-none m-0 p-0 flex flex-wrap gap-2 ${large ? "justify-center" : ""}`}>
        {starters.map((s) => (
          <li key={s}>
            <button type="button" onClick={() => { setPrompt(s); input.current?.focus(); }}
                    className="px-[14px] py-[6px] rounded-full border border-line bg-surface text-[13px] text-ink-2
                               cursor-pointer hover:bg-hover hover:text-ink">
              {s}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
