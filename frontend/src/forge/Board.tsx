import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useUrlState } from "../app/useUrlState";
import { STANDING, type Standing } from "./standing";

type Board = components["schemas"]["Board"];
type Strip = components["schemas"]["Strip"];

/** One cell per landed contract, so the whole registry's agreement is one glance.
 *
 * **It stays one glance at any size.** Twelve cells today; at the ~1,600 tools #77 will bring,
 * the strip wraps and the eye still finds the coral one instantly, which a list of 1,600 rows
 * never could. That is the property being bought — not decoration.
 */
function Cells({ counts }: { counts: Record<string, number> }) {
  const order: Standing[] = ["drifted", "unverifiable", "matching"];
  const cells = order.flatMap((standing) =>
    Array.from({ length: counts[standing] ?? 0 }, (_, i) => ({ standing, key: `${standing}${i}` })),
  );
  if (cells.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1 mt-3">
      {cells.map(({ standing, key }) => (
        <span
          key={key}
          data-testid="cell"
          data-standing={standing}
          title={STANDING[standing].title}
          className={`w-3 h-3 rounded-[1px] ${STANDING[standing].cell}`}
        />
      ))}
    </div>
  );
}

/** A figure that is also the filter that produces it. */
function Figure({
  n,
  of,
  active,
  onClick,
}: {
  n: number | string;
  of: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const body = (
    <>
      <b className="font-data text-object text-ink tabular-nums">{n}</b>{" "}
      <span className="text-secondary text-ink-2">{of}</span>
    </>
  );
  return onClick ? (
    <button
      data-active={active || undefined}
      onClick={onClick}
      className="bg-transparent border-0 border-b-2 border-b-transparent p-0 pb-1 cursor-pointer
                 text-left hover:opacity-70 data-[active]:border-b-[var(--pea)]"
    >
      {body}
    </button>
  ) : (
    <span>{body}</span>
  );
}

/** Is everything okay?
 *
 * **The question three screens never answered.** Sources said what could be read, Contracts said
 * what existed and the Queue said what was open, and a person had to hold all three and do the
 * arithmetic. Vercel's pattern, and the reason it is at the top: surface the one metric that
 * answers *is everything okay*, then let people drill in on demand.
 *
 * Nothing here is a list. Every figure is a count that sets the filter which produces it, so
 * reading the board and acting on it are the same gesture.
 */
export function StatusBoard({ board }: { board: Board }) {
  // **The figures are the filters.** They reported the same five numbers the chip row below
  // them reported, adjacent and in a different order — the page said everything twice. A count
  // that sets the filter which produces it is one thing doing one job, so the chips went.
  const [against, setAgainst] = useUrlState("against", "");
  const [state, setState] = useUrlState("state", "");
  const toggleState = (one: string) => () => setState(state === one ? "" : one);
  const toggleAgainst = (one: string) => () => setAgainst(against === one ? "" : one);
  const { data: health } = useQuery({
    // **A second endpoint on purpose.** `checked_at` is `SourceCheck.ran_at` — what the nightly
    // worker wrote — and `/tools` is composed now. One field carrying both would have made the
    // board and the health strip able to disagree about one sentence.
    queryKey: ["health"],
    queryFn: () => get<Strip>("/health/registry"),
  });

  const drifted = board.status_counts.drifted ?? 0;
  const unverifiable = board.status_counts.unverifiable ?? 0;
  const ok = drifted === 0 && unverifiable === 0;

  return (
    <div className="px-6 py-5 border-b border-line-2">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <span
          data-testid="verdict"
          data-ok={ok}
          className="text-body text-ink data-[ok=false]:text-[var(--undecided)]"
        >
          {ok ? (
            "Every contract agrees with its source."
          ) : (
            <>
              {drifted > 0 && (
                <>
                  <b className="font-data">{drifted}</b> no longer{" "}
                  {drifted === 1 ? "agrees" : "agree"} with{" "}
                  {drifted === 1 ? "its" : "their"} source
                </>
              )}
              {drifted > 0 && unverifiable > 0 && " · "}
              {unverifiable > 0 && (
                <span className="text-[var(--measured)]">
                  <b className="font-data">{unverifiable}</b> cannot be re-read
                </span>
              )}
            </>
          )}
        </span>

        <span data-testid="checked" className="ml-auto text-secondary text-ink-3">
          {health?.checked_at
            ? `checked ${new Date(health.checked_at).toLocaleString()}`
            : // **Withheld, not zeroed.** A fresh database has never run a check, and
              // "checked just now" would be the most confident possible lie.
              "never checked"}
        </span>
      </div>

      <Cells counts={board.status_counts} />

      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 mt-4">
        <Figure
          n={board.counts.landed ?? 0}
          of="landed"
          active={state === "landed"}
          onClick={toggleState("landed")}
        />
        <Figure
          n={board.counts.drafted ?? 0}
          of="drafted"
          active={state === "drafted"}
          onClick={toggleState("drafted")}
        />
        <Figure
          n={board.counts.undrafted ?? 0}
          of="nobody has drafted"
          active={state === "undrafted"}
          onClick={toggleState("undrafted")}
        />
        {drifted > 0 && (
          <Figure
            n={drifted}
            of="drifted"
            active={against === "drifted"}
            onClick={toggleAgainst("drifted")}
          />
        )}
        {unverifiable > 0 && (
          <Figure
            n={unverifiable}
            of="unverifiable"
            active={against === "unverifiable"}
            onClick={toggleAgainst("unverifiable")}
          />
        )}
        <span className="ml-auto text-secondary text-ink-3">
          {/* **An absence, not a zero** — #77. Discovery reads `vendor/modules/`, so what it
              sees is the size of what somebody already vendored rather than the size of the
              known world. Expected near 1,600 once #77 closes. */}
          <b data-testid="known" className="font-data text-ink">
            {board.known ?? "—"}
          </b>{" "}
          known to <span className="font-data">{board.sources.join(", ")}</span>
        </span>
      </div>
    </div>
  );
}
