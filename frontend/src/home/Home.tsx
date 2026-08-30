import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { useTitle } from "../app/useTitle";
import { get } from "../api/client";
import type { components } from "../api/schema";
import { Failed, Loading } from "../ui/States";
import { Artifact } from "./Artifact";
import { StandingBlock } from "./Standing";

type Attention = components["schemas"]["Attention"];
type Call = components["schemas"]["Call"];

const eyebrow = "font-ui text-label uppercase tracking-[.14em] font-semibold text-ink-3";

/** One thing asking for a person: how much, said plainly, and where it lives.
 *
 * **A count and a link, never a row.** Spec §1 — the Queue owns questions and Contracts owns
 * drift; this points at them. An Overview page that listed the items was designed and cut once
 * for answering the Queue's question, and rendering one item here would undo that by
 * forgetting it.
 *
 * Urgency is carried as a left rail rather than a badge, for the same reason the tiers are: the
 * page has one visual language for *how sure / how urgent*, and adding a second vocabulary of
 * coloured pills would mean a reader has two things to learn instead of one.
 */
function CallRow({ call }: { call: Call }) {
  return (
    <Link
      data-testid="call"
      data-urgency={call.urgency}
      to={call.where}
      className="group flex items-center gap-4 px-4 py-3.5 no-underline text-ink
                 border-b border-line last:border-b-0 border-l-2 border-l-transparent
                 transition-colors hover:bg-surface-2
                 data-[urgency=blocking]:border-l-[var(--undecided)]
                 data-[urgency=waiting]:border-l-[var(--measured)]"
    >
      <span className="text-body">{call.what}</span>
      <span
        className="ml-auto shrink-0 text-secondary text-pea opacity-0 translate-x-[-4px]
                   transition group-hover:opacity-100 group-hover:translate-x-0
                   group-focus-visible:opacity-100 motion-reduce:transition-none
                   motion-reduce:opacity-100 motion-reduce:translate-x-0"
        aria-hidden
      >
        open →
      </span>
    </Link>
  );
}

/** Where to go, named for the work each one holds rather than for its contents. */
function Way({ to, name, holds }: { to: string; name: string; holds: string }) {
  return (
    <Link
      to={to}
      className="group block p-4 no-underline rounded-r border border-line bg-surface
                 transition-colors hover:border-line-2 hover:bg-surface-2"
    >
      <div className="font-display text-object text-ink group-hover:text-pea transition-colors">
        {name}
      </div>
      <div className="text-secondary text-ink-3 mt-1">{holds}</div>
    </Link>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-9">
      <div className="flex items-baseline gap-4 border-b border-line pb-2">
        <h2 className={`${eyebrow} m-0`}>{title}</h2>
        {note && <span className="ml-auto text-secondary text-ink-3">{note}</span>}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

/** The front door.
 *
 * **Four blocks, in the order of a person's questions**: what is this, what needs me, what is
 * here, where do I go. The third is the one a dashboard usually omits and the one that makes
 * this a place rather than an inbox.
 *
 * **The hero is a thesis, not a banner.** Left, the claim in one sentence; right, the file that
 * makes the claim checkable. `Artifact` says why it is quoted rather than fetched.
 *
 * **`/` redirected to the queue for the whole of 3A**, marked temporary in writing since phase
 * 0. This is what it was waiting for.
 */
export function Home() {
  useTitle(); // the front door is the product
  const { data, isLoading, error } = useQuery({
    queryKey: ["attention"],
    queryFn: () => get<Attention>("/attention"),
  });

  const waiting = data ? data.forge.filter((c) => c.urgency !== "idle") : [];
  const available = data ? data.forge.filter((c) => c.urgency === "idle") : [];

  return (
    <div className="overflow-auto">
      <div className="max-w-[1040px] mx-auto px-6 pb-16">
        <header
          className="grid gap-9 items-center py-12 md:py-16
                     md:grid-cols-[minmax(0,1fr)_minmax(0,420px)] settle"
        >
          <div>
            <p className={eyebrow}>Mendel · pipeline construction</p>
            <h1
              className="font-display text-hero leading-[1.08] tracking-[-.02em]
                         text-ink mt-3 mb-0 text-balance"
            >
              Every decision in the pipeline says who made it.
            </h1>
            <p className="text-lede text-ink-2 mt-5 max-w-[52ch] leading-[1.6]">
              Describe an analysis, and every decision in the Nextflow that comes out traces to a
              constraint, a convention, a measurement, or a judgement somebody was asked to make.
            </p>

            <p className="font-data text-secondary text-ink-3 mt-6 mb-0">
              Same goal in <span className="text-pea">→</span> same pipeline out.
              <br />
              Nothing was guessed silently.
            </p>

            <div className="flex flex-wrap items-center gap-3 mt-7">
              <Link
                to="/forge/queue"
                className="px-4 py-2 rounded-r no-underline text-body font-semibold
                           bg-pea text-[var(--on-pea)] transition-opacity hover:opacity-90"
              >
                Open the forge
              </Link>
              <Link
                to="/forge/tools"
                className="px-4 py-2 rounded-r no-underline text-body text-ink-2
                           border border-line-2 transition-colors
                           hover:text-ink hover:bg-surface-2"
              >
                Browse the tools
              </Link>
            </div>
          </div>

          <Artifact />
        </header>

        {isLoading && <Loading what="what needs you" />}
        {error && <Failed error={error} />}
        {!isLoading && !error && !data && <Failed error="nothing came back" />}

        {data && (
          <>
            <Section title="What needs you">
              {waiting.length > 0 ? (
                <div className="rounded-r border border-line bg-surface overflow-hidden">
                  {waiting.map((call) => (
                    <CallRow key={call.where} call={call} />
                  ))}
                  {available.map((call) => (
                    <CallRow key={call.where} call={call} />
                  ))}
                </div>
              ) : (
                // `dashboard.md` §7: an empty state directs rather than apologises. This is the
                // largest empty state in the product, and today it is the screen that ships.
                <p className="text-body text-ink m-0">
                  Nothing is waiting on you.{" "}
                  {available.length > 0 && (
                    <>
                      There {available[0].count === 1 ? "is" : "are"}{" "}
                      <Link to={available[0].where} className="text-pea">
                        {available[0].what.replace(/^\d+ /, "")}
                      </Link>
                      , if you want somewhere to start.
                    </>
                  )}
                </p>
              )}
            </Section>

            <Section
              title="What is here"
              note={`read from ${data.standing.sources.join(", ")}`}
            >
              <p className="text-secondary text-ink-3 mt-0 mb-5 max-w-[58ch]">
                How each line is drawn says how well-founded it is — the same language the
                pipeline canvas uses for a decision that was forced, measured or guessed.
              </p>
              <StandingBlock standing={data.standing} />
            </Section>
          </>
        )}

        <Section title="Where to go">
          <div className="grid gap-3 sm:grid-cols-2">
            {/* **Two, not three.** `Contracts` and `Sources` were the same list at two stages
                of one tool's life and became `Tools` in phase 3. They still resolve as
                redirects so old links survive — but naming a redirect on the front door would
                be teaching a stranger a route that exists only for people who learned the old
                one. */}
            <Way to="/forge/queue" name="Queue" holds="Questions waiting on a decision" />
            <Way
              to="/forge/tools"
              name="Tools"
              holds="Every tool — what has landed, what is being drafted, what nobody has started"
            />
          </div>
          <p className="text-secondary text-ink-3 mt-5 mb-0 max-w-[58ch]">
            {/* An absence, not a zero. Nothing stores pipelines, so there is no Mendel
                section — `0 pipelines need review` would claim that pipelines were looked
                at. The same discipline as `pipeline_pins: None` on the module page. */}
            The pipeline builder is <b className="font-normal text-ink-2">not built yet</b>. When
            it is, what it needs from you appears here beside the forge's work.
          </p>
        </Section>
      </div>
    </div>
  );
}
