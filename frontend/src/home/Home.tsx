import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { Failed, Loading } from "../ui/States";
import { StandingBlock } from "./Standing";

type Attention = components["schemas"]["Attention"];
type Call = components["schemas"]["Call"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** One thing asking for a person: how much, said plainly, and where it lives.
 *
 * **A count and a link, never a row.** Spec §1 — the Queue owns questions and Contracts owns
 * drift; this points at them. An Overview page that listed the items was designed and cut once
 * for answering the Queue's question, and rendering one item here would undo that by
 * forgetting it.
 */
function CallRow({ call }: { call: Call }) {
  return (
    <Link
      data-testid="call"
      data-urgency={call.urgency}
      to={call.where}
      className="flex items-baseline gap-4 py-3 border-b border-line no-underline
                 text-ink hover:bg-surface-2
                 data-[urgency=blocking]:border-l-2 data-[urgency=blocking]:border-l-[var(--undecided)]
                 data-[urgency=blocking]:pl-4"
    >
      <span className="text-body">{call.what}</span>
      <span className="ml-auto text-secondary text-pea">open →</span>
    </Link>
  );
}

/** Where to go, named for the work each one holds rather than for its contents. */
function Way({ to, name, holds }: { to: string; name: string; holds: string }) {
  return (
    <Link to={to} className="block py-3 border-b border-line no-underline">
      <div className="text-body text-pea">{name}</div>
      <div className="text-secondary text-ink-3">{holds}</div>
    </Link>
  );
}

/** The front door.
 *
 * **Four blocks, in the order of a person's questions**: what is this, what needs me, what is
 * here, where do I go. The third is the one a dashboard usually omits and the one that makes
 * this a place rather than an inbox.
 *
 * **`/` redirected to the queue for the whole of 3A**, marked temporary in writing since phase
 * 0. This is what it was waiting for.
 */
export function Home() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["attention"],
    queryFn: () => get<Attention>("/attention"),
  });

  if (isLoading) return <Loading what="what needs you" />;
  if (error) return <Failed error={error} />;
  if (!data) return <Failed error="nothing came back" />;

  const waiting = data.forge.filter((call) => call.urgency !== "idle");
  const available = data.forge.filter((call) => call.urgency === "idle");

  return (
    <div className="overflow-auto">
      <div className="max-w-[760px] mx-auto px-6 py-16">
        <h1 className="font-display text-title text-ink">Mendel</h1>
        <p className="text-body text-ink-2 mt-3 max-w-[58ch]">
          Deterministic pipeline construction. Describe an analysis, and every decision in the
          Nextflow that comes out traces to a constraint, a convention, a measurement, or a
          judgement somebody was asked to make.
        </p>

        <section className="mt-14">
          <div className={label}>What needs you</div>
          {waiting.length > 0 ? (
            <div className="mt-3">
              {waiting.map((call) => (
                <CallRow key={call.where} call={call} />
              ))}
            </div>
          ) : (
            // `dashboard.md` §7: an empty state directs rather than apologises. This is the
            // largest empty state in the product, and today it is the screen that ships.
            <p className="text-body text-ink mt-3">
              Nothing is waiting on you.{" "}
              {available.length > 0 && (
                <>
                  There{" "}
                  {available[0].count === 1 ? "is" : "are"} {available[0].what.replace(/^\d+ /, "")}
                  , if you want somewhere to start.
                </>
              )}
            </p>
          )}
          {waiting.length > 0 &&
            available.map((call) => <CallRow key={call.where} call={call} />)}
        </section>

        <section className="mt-14">
          <div className={label}>What is here</div>
          <p className="text-secondary text-ink-3 mt-1 max-w-[58ch]">
            How each line is drawn says how well-founded it is — the same language the pipeline
            canvas uses for a decision that was forced, measured or guessed.
          </p>
          <div className="mt-3">
            <StandingBlock standing={data.standing} />
          </div>
          <p className="text-secondary text-ink-3 mt-3">
            Read from <span className="font-data">{data.standing.sources.join(", ")}</span>.
          </p>
        </section>

        <section className="mt-14">
          <div className={label}>Where to go</div>
          <div className="mt-3">
            <Way to="/forge/queue" name="Queue" holds="Work that needs deciding" />
            <Way
              to="/forge/contracts"
              name="Contracts"
              holds="What exists — browse one against the tool it describes"
            />
            <Way to="/forge/sources" name="Sources" holds="What could exist — start a draft" />
          </div>
          <p className="text-secondary text-ink-3 mt-4 max-w-[58ch]">
            {/* An absence, not a zero. Nothing stores pipelines, so there is no Mendel
                section — `0 pipelines need review` would claim that pipelines were looked
                at. The same discipline as `pipeline_pins: None` on the module page. */}
            The pipeline builder is <b className="font-normal text-ink-2">not built yet</b>. When
            it is, what it needs from you appears here beside the forge's work.
          </p>
        </section>
      </div>
    </div>
  );
}
