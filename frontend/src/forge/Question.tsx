import { useTitle } from "../app/useTitle";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useAnswer } from "../api/useAnswer";
import { useAnswerAll } from "../api/useAnswerAll";
import { useKeys } from "../app/useKeys";
import { useUrlState } from "../app/useUrlState";
import { Refusal } from "../ui/Refusal";
import { Failed, Loading } from "../ui/States";
import { Decide } from "./Decide";
import { Evidence } from "./Evidence";
import { NothingFits } from "./NothingFits";

type QueueResponse = components["schemas"]["QueueResponse"];

/** Who is asking, as **prose rather than cards** — design §5.
 *
 * *"Asked by `samtools/index` and `samtools/sort` — answering once settles both."* That
 * sentence is the throughput move made visible, and it is what `answer-all` exists to honour.
 * The first design draft put the same information in a bordered card and it read as clutter.
 */
function AskedBy({ drafts }: { drafts: string[] }) {
  const names = drafts.map((d) => (
    <span key={d} className="font-data">
      {d}
    </span>
  ));
  const joined = names.flatMap((n, i) =>
    i === 0 ? [n] : [<span key={`${i}s`}>{i === names.length - 1 ? " and " : ", "}</span>, n],
  );
  return (
    <p className="text-body text-ink-2 mt-3">
      Asked by {joined}
      {drafts.length > 1 && (
        <> — answering once settles {drafts.length === 2 ? "both" : `all ${drafts.length}`}.</>
      )}
      {drafts.length === 1 && <>.</>}
    </p>
  );
}

/** One question, answered.
 *
 * It reads the `["questions"]` query rather than fetching its own: the queue has already
 * loaded it, and a second endpoint for one question would be a second projection of the
 * same holes.
 */
export function Question() {
  const { subject = "" } = useParams();
  // The subject IS the tab's identity — a curator with three questions open needs to see which
  // is which, and `Question` in all three says nothing.
  useTitle(subject ? `${subject} · Queue` : "Queue");
  const navigate = useNavigate();
  const [value, setValue] = useState<string | null>(null);
  const [why, setWhy] = useState("");
  const [evidenceOpen, setEvidenceOpen] = useUrlState("evidence", "");

  const { data, isLoading, error } = useQuery({
    queryKey: ["questions"],
    queryFn: () => get<QueueResponse>("/questions"),
  });
  const answer = useAnswer();
  const batch = useAnswerAll();

  const q = data?.questions.find((each) => each.subject === subject);
  // Every value carries a reason a reader can act on. This is the last place that could
  // quietly break it, so neither button is reachable until both halves exist.
  const ready = value !== null && why.trim().length > 0;

  function submitOne() {
    if (!ready || !q) return;
    answer.mutate(
      { draft: q.asked_by[0], subject, value, why },
      { onSuccess: () => navigate("/forge/queue") },
    );
  }

  function submitAll() {
    if (!ready || !q) return;
    batch.mutate({ subject, value, why });
  }

  useKeys({
    a: submitOne,
    e: () => setEvidenceOpen(evidenceOpen === "open" ? "" : "open"),
  });

  if (isLoading) return <Loading what="the queue" />;
  if (error) return <Failed error={error} />;
  if (!q) return <Failed error={`no open question called ${subject}`} />;

  const many = q.asked_by.length > 1;

  return (
    <div className="overflow-auto p-6 max-w-[720px]">
      <Link to="/forge/queue" className="text-secondary text-ink-3 no-underline">
        ← queue
      </Link>

      <h1 className="font-data text-title mt-4">{q.subject}</h1>
      <p className="text-body text-ink-2 mt-1">{q.what}</p>
      <p className="text-secondary text-ink-3 mt-1">{q.why_open}</p>

      <AskedBy drafts={q.asked_by} />

      {q.proposed && (
        // A declined question must not look like one nobody has reached — that is the whole
        // point of declining. Phase 3 makes the same block actionable.
        <Decide draft={q.asked_by[0]} subject={subject} proposal={q.proposed} />
      )}

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
            {q.suggested === c.value && (
              // Who answered is what a reviewer needs: a model suggestion and a human answer
              // oblige different amounts of trust — design §5.
              <span
                className="text-label uppercase tracking-[.13em] font-semibold text-ink-3
                           border border-line-2 rounded-r px-2"
              >
                MODEL
              </span>
            )}
          </label>
        ))}
      </fieldset>

      <Evidence excerpts={q.evidence} />

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

      {batch.data && (
        // **A partial batch is not a success.** The settled drafts are a sentence; every
        // refusal is rendered with its code, because the whole reason answer-all is
        // best-effort is that the odd draft gets handled individually.
        <div className="mt-4">
          {batch.data.settled.length > 0 && (
            <p className="text-body text-ink">
              Settled on <span className="font-data">{batch.data.settled.join(", ")}</span>.
            </p>
          )}
          {batch.data.refused.map((r) => (
            <div key={r.draft} className="mt-2">
              <p className="text-secondary text-ink-2">
                <span className="font-data">{r.draft}</span> refused it:
              </p>
              <Refusal message={r.detail} />
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-3 mt-6">
        <button
          onClick={submitOne}
          disabled={!ready || answer.isPending}
          className="px-4 py-2 text-body font-semibold rounded-r border border-line-2
                     bg-surface cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {answer.isPending ? "Accepting…" : many ? `Accept for ${q.asked_by[0]}` : "Accept"}
        </button>

        {many && (
          <button
            onClick={submitAll}
            disabled={!ready || batch.isPending}
            className="px-4 py-2 text-body font-semibold rounded-r border border-line-2
                       bg-surface cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {batch.isPending ? "Accepting…" : `Accept for all ${q.asked_by.length} drafts`}
          </button>
        )}
      </div>

      <NothingFits draft={q.asked_by[0]} subject={subject} />
    </div>
  );
}
