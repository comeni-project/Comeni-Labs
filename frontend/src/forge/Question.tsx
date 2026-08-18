import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useAnswer } from "../api/useAnswer";
import { useKeys } from "../app/useKeys";
import { Refusal } from "../ui/Refusal";
import { Failed, Loading } from "../ui/States";

type QueueResponse = components["schemas"]["QueueResponse"];

/** One question, answered.
 *
 * **Minimal on purpose.** The designed answer screen is phase 2 — prose context, collapsed
 * evidence, the MODEL marker, answer-all. What is here is what proves the patterns: the
 * candidates the API said were legal, a reason, and Accept.
 *
 * It reads the `["questions"]` query rather than fetching its own: the queue has already
 * loaded it, and a second endpoint for one question would be a second projection of the
 * same holes.
 */
export function Question() {
  const { subject = "" } = useParams();
  const navigate = useNavigate();
  const [value, setValue] = useState<string | null>(null);
  const [why, setWhy] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["questions"],
    queryFn: () => get<QueueResponse>("/questions"),
  });
  const answer = useAnswer();

  const q = data?.questions.find((each) => each.subject === subject);
  // Every value carries a reason a reader can act on. This is the last place that could
  // quietly break it, so Accept is unreachable until both halves exist.
  const ready = value !== null && why.trim().length > 0;

  function submit() {
    if (!ready || !q) return;
    answer.mutate(
      { draft: q.asked_by[0], subject, value, why },
      { onSuccess: () => navigate("/forge/queue") },
    );
  }

  useKeys({ a: submit });

  if (isLoading) return <Loading what="the queue" />;
  if (error) return <Failed error={error} />;
  if (!q) return <Failed error={`no open question called ${subject}`} />;

  return (
    <div className="overflow-auto p-6 max-w-[720px]">
      <Link to="/forge/queue" className="text-secondary text-ink-3 no-underline">
        ← queue
      </Link>

      <h1 className="font-data text-title mt-4">{q.subject}</h1>
      <p className="text-body text-ink-2 mt-1">{q.what}</p>
      <p className="text-secondary text-ink-3 mt-1">{q.why_open}</p>
      <p className="text-secondary text-ink-3 mt-1">
        asked by <span className="font-data">{q.asked_by.join(", ")}</span>
      </p>

      <fieldset className="mt-6 border-0 p-0">
        <legend className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
          {q.closed ? "One of these" : "Anything, these are precedents"}
        </legend>
        {q.candidates.map((c) => (
          <label key={c.value} className="flex items-baseline gap-3 py-2 cursor-pointer">
            <input
              type="radio"
              name="value"
              id={c.value}
              aria-label={c.value}
              checked={value === c.value}
              onChange={() => setValue(c.value)}
            />
            <span className="font-data text-body">{c.value}</span>
            {c.note && <span className="text-secondary text-ink-3">{c.note}</span>}
          </label>
        ))}
      </fieldset>

      <label className="block mt-6">
        <span className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
          Reason
        </span>
        <textarea
          aria-label="reason"
          value={why}
          onChange={(e) => setWhy(e.target.value)}
          rows={3}
          className="block w-full mt-2 p-3 text-body border border-line-2 rounded-r bg-surface"
        />
      </label>

      {answer.error && (
        <div className="mt-4">
          <Refusal message={String((answer.error as Error).message)} />
        </div>
      )}

      <button
        onClick={submit}
        disabled={!ready || answer.isPending}
        className="mt-6 px-4 py-2 text-body font-semibold rounded-r border border-line-2
                   bg-surface cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {answer.isPending ? "Accepting…" : "Accept"}
      </button>
    </div>
  );
}
