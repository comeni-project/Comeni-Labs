import { Link } from "react-router";

import { Failed } from "../../ui/States";
import type { AdaptationView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

const STATE: Record<string, { label: string; tone: string }> = {
  running: { label: "running in Wiener", tone: "text-action" },
  passed: { label: "passed", tone: "text-done-ink" },
  failed: { label: "failed", tone: "text-needs-you-ink" },
};

/** Running an assembled draft's tests in Wiener. Green is only what it is: each run succeeded and
 *  every declared output exists. A failure is shown, with the run to read its logs in. */
export function TestsPanel({ view, actions }: {
  view: AdaptationView;
  actions: ReturnType<typeof useForgeActions>;
}) {
  const unavailable = view.tests_unavailable;
  const canRun = view.phase === "assembled" && !unavailable;
  return (
    <div className="flex flex-col gap-3 pt-4 border-t border-line-soft">
      <h3 className="m-0 text-[14px] font-semibold">Tests</h3>
      {unavailable && <p className="m-0 text-[13px] text-needs-you-ink">{unavailable}</p>}
      {view.phase === "tested" && (
        <p className="m-0 text-[13px] text-done-ink">
          Green: each run succeeded and every declared output exists. This shows the tool runs, not that its results are correct.
        </p>
      )}
      {view.tests.length > 0 && (
        <ul className="m-0 p-0 list-none border border-line rounded-control">
          {view.tests.map((test) => (
            <li key={test.name} className="px-3 py-2 border-b border-line-soft last:border-b-0 flex flex-col gap-1 text-[13px]">
              <span className="flex flex-wrap gap-x-3">
                <span className="font-data">{test.name}</span>
                <span className={STATE[test.state]?.tone ?? ""}>{STATE[test.state]?.label ?? test.state}</span>
                {test.run_id && <Link to={`/runs/${test.run_id}`}>Open the run</Link>}
              </span>
              {test.says && <span className="text-needs-you-ink break-words">{test.says}</span>}
            </li>
          ))}
        </ul>
      )}
      {canRun && (
        <button type="button" onClick={() => actions.runTests.mutate()} disabled={actions.runTests.isPending}
                className="self-start px-5 py-[10px] rounded-button bg-action text-on-action font-semibold shadow-raise">
          Run its tests
        </button>
      )}
      {actions.runTests.isError && <Failed error={actions.runTests.error} padded={false} />}
    </div>
  );
}
