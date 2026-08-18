import { useQuery } from "@tanstack/react-query";

import type { components } from "../api/schema";
import { QueueRow } from "./QueueRow";

type QueueResponse = components["schemas"]["QueueResponse"];
type Strip = components["schemas"]["Strip"];

const get = async <T,>(path: string): Promise<T> => {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json() as Promise<T>;
};

/** The health strip. O(1) — it never grows with the registry, which is why it can sit
 *  above everything without becoming a list. */
function Health() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: () => get<Strip>("/health/registry") });
  if (!data) return <div className="h-[34px] border-b border-line bg-surface-2" />;
  // Until a check has run, `matching` and `unverifiable` are 0 because nothing was
  // measured — not because nothing matches. Rendering "0 match their source" on a fresh
  // database reads as catastrophe when the truth is "unknown", so those two are withheld
  // rather than shown as zeroes. Found by running against an empty database.
  const checked = data.checked_at !== null;
  return (
    <div className="flex items-center gap-6 px-6 h-[34px] bg-surface-2 border-b border-line
                    text-secondary text-ink-2">
      <span><b className="font-data text-ink">{data.contracts}</b> contracts</span>
      {checked && <span><b className="font-data text-ink">{data.matching}</b> match their source</span>}
      {checked && data.unverifiable > 0 && (
        // Reported rather than folded into `matching`: a contract nothing checks looks
        // exactly like a contract that agrees.
        <span><b className="font-data text-ink">{data.unverifiable}</b> unverifiable</span>
      )}
      <span><b className="font-data text-ink">{data.types}</b> declared types</span>
      <span className="ml-auto text-ink-3">
        {data.checked_at
          ? <>sources checked <span className="font-data">{new Date(data.checked_at).toLocaleString()}</span></>
          : "sources not checked yet"}
      </span>
    </div>
  );
}

/** The facet rail. SIX kinds of work, fixed — this is the part that must not grow with
 *  the registry, and it is why one page is enough. */
function Facets({ questions }: { questions: QueueResponse["questions"] }) {
  const count = (band: string) => questions.filter((q) => q.band === band).length;
  const rows: [string, number, string][] = [
    ["Needs you", count("routing"), "text-ink"],
    ["Cosmetic", count("cosmetic"), "text-ink-2"],
    ["Prose", count("prose"), "text-ink-2"],
  ];
  return (
    <div className="border-r border-line p-6 flex flex-col">
      <div className="text-label uppercase tracking-[.13em] font-semibold text-ink-3 mb-3">
        Needs a human
      </div>
      {rows.map(([label, n, tone]) => (
        <div key={label} className="flex items-baseline gap-4 py-2 text-body">
          <span className={tone}>{label}</span>
          <b className="ml-auto font-data text-secondary font-semibold">{n}</b>
        </div>
      ))}
      <div className="mt-auto text-label text-ink-3 leading-7">
        <div><span className="font-data">J</span> / <span className="font-data">K</span> move</div>
        <div><span className="font-data">A</span> accept · <span className="font-data">E</span> evidence</div>
      </div>
    </div>
  );
}

export { Health };

export function Queue() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["questions"],
    queryFn: () => get<QueueResponse>("/questions"),
  });

  return (
    <div className="grid grid-rows-[34px_1fr] overflow-hidden">
      <Health />
      <div className="grid grid-cols-[216px_1fr] overflow-hidden">
        <Facets questions={data?.questions ?? []} />
        <div className="overflow-auto">
          <div className="flex items-center gap-5 px-6 py-4 border-b border-line-2">
            <span className="text-body text-ink-2">Sorted by</span>
            <span className="text-body font-semibold border border-line-2 bg-surface rounded-r px-3 py-1">
              consequence
            </span>
            <span className="ml-auto text-secondary text-ink-3">
              <span className="font-data">{data?.questions.length ?? 0}</span> rows ·{" "}
              <span className="font-data">{data?.total ?? 0}</span> questions
            </span>
          </div>

          {isLoading && <p className="p-6 text-ink-3">Reading the workspace…</p>}
          {error && <p className="p-6 text-fault">{String(error)}</p>}
          {data?.questions.length === 0 && (
            <p className="p-6 text-ink-3">Nothing open. Draft a module to give the queue work.</p>
          )}
          {data?.questions.map((q) => <QueueRow key={`${q.subject}:${q.suggested}`} q={q} />)}
        </div>
      </div>
    </div>
  );
}
