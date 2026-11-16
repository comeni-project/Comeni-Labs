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
    <div className="relative min-h-full overflow-auto bg-canvas">
      <NoRail />
      <Drawing />
      <button type="button" onClick={() => setTheme(dark ? "light" : "dark")} aria-label="Light or dark theme"
              className="absolute top-5 right-5 p-2 border-0 bg-transparent rounded-control text-ink-2 cursor-pointer hover:bg-hover">
        <Icon name="moon" size={16} />
      </button>
      <main className="relative min-h-screen flex flex-col items-center justify-center gap-6 gutter py-16">
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
      <p className="absolute bottom-5 inset-x-0 m-0 flex items-center justify-center gap-2 text-[12.5px] text-ink-3">
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

/** A faint pipeline behind the page, in the line colour; decoration only. */
function Drawing() {
  const box = (x: number, y: number, w = 90) =>
    <rect key={`${x}-${y}`} x={x} y={y} width={w} height={40} rx={10} className="fill-surface stroke-line" />;
  return (
    <svg aria-hidden className="absolute inset-0 w-full h-full pointer-events-none opacity-70" preserveAspectRatio="xMidYMid slice"
         viewBox="0 0 1440 900">
      <g fill="none" className="stroke-line" strokeWidth="1.5">
        <path d="M150 170C230 170 240 120 310 120M150 170C230 170 240 230 310 230M410 120H520M410 230C470 230 460 120 520 120" />
        <path d="M1060 150H1170M1270 150C1310 150 1310 220 1350 220" />
        <path d="M120 690H230M330 690C380 690 380 760 430 760" />
        <path d="M1040 690C1110 690 1110 640 1180 640M1040 690L1180 750M1280 640H1340" />
      </g>
      {[box(70, 150), box(310, 100, 100), box(310, 210, 100), box(520, 100), box(970, 130), box(1170, 130, 100),
        box(40, 670, 80), box(230, 670, 100), box(430, 740), box(950, 670), box(1180, 620, 100), box(1180, 730, 100)]}
      <circle cx="360" cy="170" r="4" className="fill-measured" />
      <circle cx="1230" cy="690" r="4" className="fill-measured" />
    </svg>
  );
}
