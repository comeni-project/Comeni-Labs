import { useUrlState } from "../../app/useUrlState";
import { Console } from "./Console";
import { TERMINAL } from "./model";
import { useRunStream } from "./useRunStream";

/** Run's Console: the run's events in order, live, filtered to a step from the address
 *  (`?process=`, which Steps' *Log* sets). */
export function ConsolePage({ runId, phase }: { runId: string; phase: string }) {
  const stream = useRunStream(runId);
  const [process, setProcess] = useUrlState("process", "");
  return (
    <section aria-label="Console" className="flex flex-col min-h-[520px] bg-surface border border-line rounded-panel overflow-hidden">
      <header className="flex items-center gap-3 px-5 py-3 border-b border-line-soft">
        <h2 className="m-0 text-[15.5px] font-semibold text-ink">Console</h2>
        <span className="ml-auto text-[12.5px] text-ink-3">
          {TERMINAL.has(phase) ? "the run is over" : stream.following ? "following" : "not following"}
        </span>
      </header>
      {stream.error ? <p className="m-0 px-5 py-3 text-[13px] text-ink-3">{stream.error}</p> : (
        <Console events={stream.events} following={stream.following} process={process}
                 onClearProcess={() => setProcess("")} onFilter={setProcess} />
      )}
    </section>
  );
}
