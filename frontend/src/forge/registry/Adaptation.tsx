import { Link, useParams } from "react-router";

import {
  isMoving,
  useAdaptation,
  useApproval,
  useArchive,
  useCandidate,
  useRetryAdaptation,
  type AdaptationRow,
  type ContractField,
  type Event,
  type OpenHole,
  type ReviewCandidate,
  type Revision,
} from "../../api/registry";
import { useTitle } from "../../app/useTitle";
import { useUrlState } from "../../app/useUrlState";
import { Failed, Loading } from "../../ui/States";
import { Approve, RequestChanges, WhyBlocked } from "./Approval";
import { ReasonButton } from "./ReasonButton";
import { ContractPane, CodePane, OriginKey } from "./ReviewDiff";
import { ReviewChat } from "./ReviewChat";
import { ReviewGraph } from "./ReviewGraph";
import { LOOK, Mark, Status, RegistrySection } from "./Status";
import { Provenance, Validation } from "./Validation";

/** `/forge/adaptations/:id` — **one route owns every state** (§8.4).
 *
 * A refresh never sends the reviewer to a different page, and neither does the adaptation
 * moving under them: a candidate that finishes generating while somebody is reading the
 * scaffold summary turns the same URL into the review screen. Two routes would mean a redirect
 * at exactly the moment somebody is mid-sentence.
 *
 * **The tabs, the selection and the dialogs are query parameters.** A curator who has found the
 * port that is wrong can paste the URL; state held in `useState` is a view nobody can be sent
 * to. The dialogs are the exception in one direction — they are transient by nature — and they
 * are still URL-backed, because *I pressed approve and the page reloaded* should not lose the
 * form.
 */

/** Six stages, in the order a tool passes through them — §8.4's track.
 *
 * `queued` sits between scaffolding and the model because that is where the wait actually is,
 * and drawing it as a stage rather than as a gap is what makes *position 3* mean something.
 */
const TRACK: { label: string; states: string[] }[] = [
  { label: "Scaffold", states: ["scaffolding"] },
  { label: "Queued", states: ["queued"] },
  { label: "Analyse", states: ["generating"] },
  { label: "Implement", states: ["generating"] },
  { label: "Validate", states: ["validating"] },
  { label: "Review", states: ["review", "changes_requested", "publishing", "published"] },
];

function reached(state: string): number {
  const at = TRACK.findIndex((stage) => stage.states.includes(state));
  // A failed or archived adaptation stopped somewhere the track cannot name; showing it as
  // stage 0 would say it never started. `failed_stage` is what the header reports instead.
  return at === -1 ? TRACK.length : at;
}

function Track({ row }: { row: AdaptationRow }) {
  const at = reached(row.state);
  return (
    <div className="overflow-x-auto py-5">
      <div className="flex items-center gap-[9px] min-w-[760px]">
        {TRACK.map((stage, i) => (
          <div key={stage.label} className="flex items-center gap-[9px] flex-1">
            {i > 0 && (
              <div
                aria-hidden="true"
                className={`flex-1 h-px bg-line-2 min-w-4 ${i === at ? "flow" : ""}`}
              />
            )}
            <span className="flex items-center gap-[7px] whitespace-nowrap">
              <Mark shape={i < at ? "done" : i === at ? "run" : "open"} />
              <span
                className={`text-[12px] ${
                  i < at ? "text-ink-2" : i === at ? "text-ink font-medium" : "text-ink-4"
                }`}
              >
                {stage.label}
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Durable events only — §8.4 says so, and the reason is on the next line.
 *
 * **The model's intermediate reasoning is not streamed here.** What is recorded is what
 * happened; a live thought log would be a picture of a call nobody can replay, sitting beside
 * an audit trail that can be.
 */
function Activity({ events }: { events: readonly Event[] }) {
  return (
    <>
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[11px]">
        Activity
      </div>
      <div className="border border-line bg-surface rounded-[var(--r)] px-3.5 pt-1.5 pb-2.5">
        {events.length === 0 && (
          <p className="text-body text-ink-3 py-2 m-0">Nothing has happened yet.</p>
        )}
        {[...events].reverse().map((event, i) => (
          <div
            key={`${event.at}-${i}`}
            className="flex gap-[11px] py-2 border-b border-line-soft last:border-0"
          >
            <span className="font-data text-[10.5px] text-ink-3 flex-[0_0_44px]">
              {new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
            <span className="text-[12px] flex-1">
              {event.kind}
              {event.detail && (
                <span className="font-data block text-[10.5px] text-ink-3 pt-0.5">
                  {event.detail}
                </span>
              )}
            </span>
            <span className="font-data text-[10px] text-ink-3">{event.actor}</span>
          </div>
        ))}
      </div>
      <p className="font-data text-label text-ink-3 pt-2.5 leading-[1.5] m-0">
        Durable events only. The model's intermediate reasoning is not streamed here — what is
        recorded is what happened.
      </p>
    </>
  );
}

/** The scaffold summary — §8.4, and *each hole links to its evidence and prompt hint*. */
function Scaffold({
  candidate,
  onSelect,
}: {
  candidate: ReviewCandidate;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="border border-line bg-surface rounded-[var(--r)] px-5 py-[18px] mt-[18px]">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-3">
        Deterministic scaffold
      </div>
      <div className="flex gap-[34px] pb-4">
        <Figure n={candidate.fields.length} what="facts read" />
        <Figure n={candidate.holes.length} what="holes open" tone="var(--fault)" />
        <Figure n={candidate.evidence.length} what="evidence excerpts" />
      </div>
      <div className="flex flex-col gap-[9px]">
        {candidate.holes.map((hole) => (
          <button
            key={hole.id}
            type="button"
            onClick={() => onSelect(hole.id)}
            className="lift flex gap-2.5 items-baseline text-left px-2.5 py-[7px]
                       border-l-2 border-fault w-full"
          >
            <span className="font-data text-[10.5px] text-ink-3 flex-[0_0_168px] truncate">
              {hole.id}
            </span>
            <span className="text-[12px] flex-1">{hole.question}</span>
            <span className="font-data text-[10px] text-link whitespace-nowrap">
              {hole.evidence_ids.slice(0, 1).join("") || "no evidence"}
              {hole.hint && ` · ${hole.hint}`}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Figure({ n, what, tone }: { n: number; what: string; tone?: string }) {
  return (
    <div>
      <div className="text-[22px] font-semibold tnum" style={tone ? { color: tone } : undefined}>
        {n}
      </div>
      <div className="font-data text-label text-ink-3">{what}</div>
    </div>
  );
}

/** The selected thing, whatever it is — a port, a field or a hole.
 *
 * §8.5: *selecting a port opens the exact contract field, evidence, rationale, and source
 * locator*. One panel for all three, because they are one question — *why does this say what it
 * says* — and three panels would be three places for the answer to be missing.
 */
function Inspector({
  candidate,
  selected,
  onClose,
}: {
  candidate: ReviewCandidate;
  selected: string;
  onClose: () => void;
}) {
  const hole: OpenHole | undefined = candidate.holes.find((h) => h.id === selected);
  const fields: ContractField[] = candidate.fields.filter(
    (field) => field.hole_id === selected || field.field === selected,
  );
  const ids = new Set([
    ...(hole?.evidence_ids ?? []),
    ...fields.flatMap((field) => field.evidence_ids),
    ...(candidate.evidence.some((e) => e.id === selected) ? [selected] : []),
  ]);
  const cited = candidate.evidence.filter((excerpt) => ids.has(excerpt.id));

  if (!hole && fields.length === 0 && cited.length === 0) return null;

  return (
    <div className="border border-link bg-[var(--link-soft)] rounded-[var(--r)] px-5 py-4 mt-[22px]">
      <div className="flex items-baseline justify-between pb-2.5">
        <span className="font-data text-[11px] text-ink">{selected}</span>
        <button
          type="button"
          onClick={onClose}
          className="font-data text-label tracking-[.08em] uppercase text-ink-3 hover:text-ink
                     bg-transparent border-0 cursor-pointer"
        >
          Close
        </button>
      </div>

      {hole && (
        <>
          <p className="text-body text-ink m-0">{hole.question}</p>
          <p className="text-secondary text-ink-2 m-0 pt-1">{hole.why_open}</p>
          {hole.legal_values.length > 0 && (
            <p className="font-data text-[10.5px] text-ink-2 m-0 pt-2">
              {/* **Exhaustive and not-exhaustive are different sentences.** *We listed
                  everything* and *we listed what we found* are the two answers a reviewer most
                  needs told apart, and `Question.closed` already draws that line. */}
              {hole.exhaustive ? "legal values" : "suggested"}: {hole.legal_values.join(", ")}
            </p>
          )}
        </>
      )}

      {fields.map((field) => (
        <div key={field.field} className="pt-2">
          <p className="font-data text-[11px] text-ink m-0">
            {field.field}: {field.value}
          </p>
          <p className="text-secondary text-ink-2 m-0 pt-1">
            {field.why} — {field.how} · {field.by}
          </p>
        </div>
      ))}

      {cited.map((excerpt) => (
        <div key={excerpt.id} className="pt-3 border-t border-line-soft mt-3">
          <p className="font-data text-[10px] text-link m-0">
            {excerpt.id} · {excerpt.excerpt.locator}
          </p>
          <p className="font-data text-[10.5px] text-ink-2 m-0 pt-1.5 whitespace-pre-wrap">
            {excerpt.excerpt.text}
          </p>
        </div>
      ))}
    </div>
  );
}

const TABS = ["Overview", "Files", "Fields", "Evidence"] as const;

export function Adaptation() {
  const id = useParams().id ?? "";
  const { data, isPending, error } = useAdaptation(id);
  const row = data?.adaptation;
  const moving = isMoving(row?.state);

  useTitle(row ? `${row.display_name || row.ref}` : "Adaptation");

  const candidate = useCandidate(id, moving);
  const reviewing = row?.state === "review" || row?.state === "changes_requested";
  const approval = useApproval(id, reviewing);
  const archive = useArchive(id);
  const retry = useRetryAdaptation();

  const [tab, setTab] = useUrlState("tab", "Overview");
  const [selected, setSelected] = useUrlState("at", "");
  const [dialog, setDialog] = useUrlState("do", "");

  const current: Revision | undefined = data?.revisions.find(
    (revision) => revision.id === row?.current_revision_id,
  );

  return (
    <RegistrySection>
      <div className="gutter pb-10 overflow-y-auto">
        {isPending && <Loading what="this adaptation" />}
        {error && <Failed error={error} />}

        {row && (
          <>
            <header className="settle pt-[22px] pb-4 border-b border-line">
              <div className="flex items-baseline justify-between gap-4 flex-wrap">
                <div className="flex items-baseline gap-3.5 flex-wrap">
                  <Link
                    to="/forge/work"
                    className="text-[22px] font-semibold tracking-[-.025em] no-underline text-ink"
                  >
                    {row.display_name || row.ref}
                  </Link>
                  <Status state={row.state} />
                  <span className="font-data text-[11px] text-ink-3">
                    revision {current?.ordinal ?? data?.revisions.length ?? 0}
                  </span>
                </div>

                <div className="flex gap-2.5">
                  {row.state === "failed" && (
                    <ReasonButton
                      label={`Retry at ${row.failed_stage ?? "the start"}`}
                      placeholder="Why retry?"
                      busy={retry.isPending}
                      onSend={(reason) => retry.mutate({ id, reason })}
                    />
                  )}
                  {reviewing && (
                    <>
                      <button
                        type="button"
                        onClick={() => setDialog("changes")}
                        className="border border-line-2 bg-transparent text-ink text-[12px]
                                   rounded-[var(--r)] px-3.5 py-[7px] hover:bg-surface-2"
                      >
                        Request changes
                      </button>
                      <button
                        type="button"
                        onClick={() => setDialog("approve")}
                        disabled={!approval.data?.can_approve}
                        title={
                          approval.data?.can_approve
                            ? undefined
                            : approval.data?.refusals.map((r) => r.split("\n")[0]).join("; ")
                        }
                        className="border border-pea text-pea bg-transparent text-[12px]
                                   rounded-[var(--r)] px-3.5 py-[7px] hover:bg-pea-soft
                                   disabled:border-line disabled:text-ink-3
                                   disabled:cursor-not-allowed"
                      >
                        Approve and publish
                      </button>
                    </>
                  )}
                  {/* Archiving is legal from any state a worker is not holding; `ALLOWED`
                      refuses the rest with `MF0300`, so the button follows that rule rather
                      than a second copy of it. */}
                  {!moving && row.state !== "published" && row.state !== "archived" && (
                    <ReasonButton
                      label="Archive"
                      placeholder="Why archive?"
                      busy={archive.isPending}
                      onSend={(reason) => archive.mutate(reason)}
                    />
                  )}
                </div>
              </div>

              <div className="font-data text-[10.5px] text-ink-3 pt-2">
                {row.source} · {row.ref}
                {candidate.data?.source_digest && (
                  <> · source digest {candidate.data.source_digest.slice(0, 8)}…</>
                )}
                {row.failed_stage && (
                  <span className="text-fault"> · failed at {LOOK[row.failed_stage].label}</span>
                )}
              </div>

              {reviewing && current && (
                <div className="text-body text-ink-2 pt-2">
                  {candidate.data?.files.length ?? 0} file
                  {candidate.data?.files.length === 1 ? "" : "s"} ·{" "}
                  <span className={current.green ? "text-pea" : "text-measured"}>
                    {current.green ? "checks pass" : "checks have not passed"}
                  </span>{" "}
                  · {current.unresolved_required} unresolved
                </div>
              )}
              {(archive.error || retry.error) && (
                <div className="pt-2.5">
                  <Failed error={archive.error ?? retry.error} padded={false} />
                </div>
              )}
            </header>

            {!reviewing && <Track row={row} />}

            {reviewing && (
              <div className="flex gap-0.5 pt-3 border-b border-line-soft">
                {TABS.map((name) => (
                  <button
                    key={name}
                    type="button"
                    aria-current={tab === name}
                    onClick={() => setTab(name)}
                    className={`font-data text-label tracking-[.08em] uppercase px-[13px] py-1.5
                                border-0 ${
                                  tab === name
                                    ? "bg-surface text-ink"
                                    : "bg-transparent text-ink-3 hover:text-ink"
                                }`}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}

            {/* **The chat rail is 372px above 1180 and stacks below content under it** — §8.5,
                and it is part of review rather than a floating widget. It is absent while the
                adaptation is still being built, because there is no revision to ground an
                answer on. */}
            <div
              className={`pt-[22px] ${
                reviewing
                  ? "grid gap-[26px] items-start grid-cols-1 min-[1180px]:grid-cols-[minmax(0,1fr)_372px]"
                  : "grid gap-[26px] items-start grid-cols-1 min-[1180px]:grid-cols-[minmax(0,1fr)_320px]"
              }`}
            >
              <div className="min-w-0">
                {candidate.isPending && moving && <Loading what="the scaffold" />}
                {candidate.error && !candidate.data && (
                  <div className="border border-line bg-surface rounded-[var(--r)] p-6">
                    <p className="text-body text-ink m-0">Nothing has been scaffolded yet.</p>
                    <p className="text-secondary text-ink-3 m-0 pt-1">
                      The deterministic half reads the source first; there is nothing to review
                      until it has.
                    </p>
                  </div>
                )}

                {candidate.data && !reviewing && (
                  <>
                    <div className="border border-running bg-surface rounded-[var(--r)] px-5 py-[18px]">
                      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-2.5">
                        Current stage
                      </div>
                      <div className="text-[15px] font-medium">{LOOK[row.state].label}</div>
                      <p className="text-body text-ink-2 m-0 pt-1.5">
                        Grounded on {candidate.data.evidence.length} evidence excerpts. Nothing
                        is written until the proposal validates.
                      </p>
                    </div>
                    <Scaffold candidate={candidate.data} onSelect={setSelected} />
                  </>
                )}

                {candidate.data && reviewing && (
                  <>
                    {tab === "Overview" && (
                      <>
                        <ReviewGraph
                          graph={candidate.data.graph}
                          selected={selected}
                          onSelect={setSelected}
                          onParams={() => setTab("Fields")}
                        />
                        <div className="grid gap-5 pt-[22px] grid-cols-1 min-[1180px]:grid-cols-2">
                          <Validation revision={current} />
                          <Provenance origins={candidate.data.origins} />
                        </div>
                        <div className="pt-[22px]">
                          <WhyBlocked approval={approval.data} />
                        </div>
                      </>
                    )}

                    {tab === "Files" && (
                      <>
                        <OriginKey />
                        <div className="grid gap-5 grid-cols-1 min-[1180px]:grid-cols-2">
                          <ContractPane
                            fields={[...candidate.data.fields]}
                            selected={selected}
                            onSelect={setSelected}
                          />
                          {candidate.data.files.map((file) => (
                            <CodePane key={file.path} file={file} />
                          ))}
                        </div>
                      </>
                    )}

                    {tab === "Fields" && (
                      <>
                        <OriginKey />
                        <ContractPane
                          fields={[...candidate.data.fields]}
                          selected={selected}
                          onSelect={setSelected}
                        />
                        {candidate.data.holes.length > 0 && (
                          <Scaffold candidate={candidate.data} onSelect={setSelected} />
                        )}
                      </>
                    )}

                    {tab === "Evidence" && (
                      <div className="flex flex-col gap-3">
                        {candidate.data.evidence.length === 0 && (
                          <p className="text-body text-ink-3">
                            The source supplied no quotable evidence.
                          </p>
                        )}
                        {candidate.data.evidence.map((excerpt) => (
                          <button
                            key={excerpt.id}
                            type="button"
                            onClick={() => setSelected(excerpt.id)}
                            className={`lift text-left border border-line bg-surface
                                        rounded-[var(--r)] px-4 py-3 ${
                                          selected === excerpt.id ? "border-link" : ""
                                        }`}
                          >
                            <div className="font-data text-[10px] text-link">
                              {excerpt.id} · {excerpt.kind} · {excerpt.excerpt.locator}
                            </div>
                            <div className="font-data text-[10.5px] text-ink-2 pt-1.5 whitespace-pre-wrap">
                              {excerpt.excerpt.text}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}

                    {selected && (
                      <Inspector
                        candidate={candidate.data}
                        selected={selected}
                        onClose={() => setSelected("")}
                      />
                    )}
                  </>
                )}
              </div>

              <div className="min-w-0">
                {reviewing ? (
                  <ReviewChat adaptationId={id} onEvidence={setSelected} />
                ) : (
                  <Activity events={data?.events ?? []} />
                )}
              </div>
            </div>

            {reviewing && (
              <div className="pt-[26px]">
                <Activity events={data?.events ?? []} />
              </div>
            )}
          </>
        )}
      </div>

      {dialog === "changes" && row && (
        <RequestChanges
          adaptationId={id}
          revision={current?.ordinal ?? 0}
          onClose={() => setDialog("")}
        />
      )}
      {dialog === "approve" && row && (
        <Approve
          adaptationId={id}
          files={[...(candidate.data?.files ?? [])]}
          approval={approval.data}
          who={row.who}
          onClose={() => setDialog("")}
        />
      )}
    </RegistrySection>
  );
}
