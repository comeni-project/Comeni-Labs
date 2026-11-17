import { NoRail } from "../app/rail/RailContext";
import { Icon } from "../app/rail/icons";
import { painted, useTheme } from "../app/useTheme";
import { Ask } from "./Ask";
import { useAiConfigured } from "./useAiConfigured";
import { useStart } from "./useStart";

const STARTERS = ["Gene counts from RNA-seq", "Assemble and check bacterial isolates",
  "Variants against a reference", "Species in a metagenome"];

/** The first screen, before there is any analysis (board: `Welcome.dc.html`). No rail: there is
 *  nothing yet to move between. */
export function Welcome() {
  const folder = useStart("data");
  const byHand = useStart("build");
  const model = useAiConfigured();
  const [theme, setTheme] = useTheme();
  const dark = painted(theme) === "dark";

  return (
    <div className="welcome relative min-h-full overflow-auto bg-canvas isolate flex flex-col">
      <NoRail />
      <Drawing />
      <button type="button" onClick={() => setTheme(dark ? "light" : "dark")} aria-label="Light or dark theme"
              className="absolute top-5 right-5 p-2 border-0 bg-transparent rounded-control text-ink-2 cursor-pointer hover:bg-hover">
        <Icon name="moon" size={16} />
      </button>
      <main className="relative flex-1 flex flex-col items-center justify-center gap-7 gutter pt-16 pb-9">
        <div className="flex flex-col items-center gap-3 text-center">
          <Mark />
          <h1 className="m-0 text-[44px] leading-none font-bold tracking-[-.03em] text-ink">Comeni</h1>
          <p className="m-0 font-serif italic text-[16px] text-ink-2">Omnes omnia omnino</p>
        </div>
        <div className="w-[min(680px,100%)] flex flex-col gap-5">
          <Ask starters={STARTERS} large />
          <nav aria-label="Other ways to start"
               className="flex flex-wrap justify-center gap-x-7 gap-y-2 pt-4 border-t border-line">
            <button type="button" onClick={() => folder.mutate()} className={LINK}>
              <Icon name="data" size={15} /> Start from a folder of data
            </button>
            <button type="button" onClick={() => byHand.mutate()} className={LINK}>
              <Icon name="build" size={15} /> Build by hand
            </button>
          </nav>
          {byHand.error && <p role="alert" className="m-0 text-center text-[12.5px] text-needs-you-ink">{byHand.error.message}</p>}
        </div>
      </main>
      <p className="relative m-0 px-4 pb-5 flex items-center justify-center gap-2 text-[12.5px] text-ink-3">
        <span aria-hidden className="w-[7px] h-[7px] rounded-full bg-done" />
        Running on this machine · {model.configured ? "a model is set up" : "no model set up"}
      </p>
    </div>
  );
}

const LINK = `flex items-center gap-2 border-0 bg-transparent p-1 text-[14px] text-ink-2 cursor-pointer
              hover:text-ink rounded-control`;

/** Three steps of a pipeline, the last one done: the product's mark. */
function Mark() {
  return (
    <svg width="64" height="22" viewBox="0 0 64 22" aria-hidden className="text-action">
      <circle cx="10" cy="11" r="7.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="32" cy="11" r="7.5" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="54" cy="11" r="7.5" fill="currentColor" />
      <path d="M17.5 11h7M39.5 11h7" stroke="currentColor" strokeWidth="2.5" />
    </svg>
  );
}

/** Fixed-size pipeline fragments frame the question without scaling with a wide monitor. */
function Drawing() {
  return (
    <div aria-hidden className="welcome-drawing">
      {["welcome-pipeline-start", "welcome-pipeline-end"].map((position) => (
        <svg key={position} className={`welcome-pipeline ${position}`} viewBox="0 0 480 240" fill="none">
          <g stroke="var(--line-2)" strokeWidth="1">
            <path d="M0 120h64m88 0c48 0 44-72 92-72m-92 72c48 0 44 72 92 72m88-144c48 0 44 72 92 72m-92 72c48 0 44-72 92-72h56" />
            <rect x="64" y="96" width="88" height="48" rx="10" fill="var(--canvas)" />
            <rect x="244" y="24" width="88" height="48" rx="10" fill="var(--canvas)" />
            <rect x="244" y="168" width="88" height="48" rx="10" fill="var(--canvas)" />
            <path d="M94 114h36m-36 12h22m158-84h36m-36 12h22m-22 132h36m-36 12h22" />
          </g>
          <g fill="var(--now)">
            <circle cx="82" cy="114" r="3" />
            <circle cx="262" cy="42" r="3" />
            <circle cx="262" cy="186" r="3" />
            <circle cx="424" cy="120" r="4" />
          </g>
        </svg>
      ))}
    </div>
  );
}
