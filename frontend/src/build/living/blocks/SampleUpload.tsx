import { useEffect, useId, useRef, useState } from "react";

import { Refused } from "../../../api/client";
import type { InspectedFact, SampleInspected, SampleReading } from "../../../api/types";
import { bytes } from "../../../runs/units";
import { Primary, Secondary } from "./parts";
import { piece } from "./piece";

/** Answering a gap with a sample: one file, or a pair (issue 134, the canvas *Uploading a sample*).
 *
 * **Nothing leaves before the person presses Measure**, and nothing but the files and the
 * question's id leaves then: the names are shown back here, in this browser, and never written
 * into a fact. Three files are refused on the card, before any request. Every way the request
 * can end leaves the card usable: a refusal shows its own sentence, a network failure says so,
 * and neither leaves it stuck on *measuring*.
 */

type Stage =
  | { at: "offered" }
  | { at: "picked"; files: File[] }
  | { at: "measuring"; files: File[] }
  | { at: "reading"; files: File[] }
  | { at: "done"; files: File[]; result: SampleInspected }
  | { at: "failed"; files: File[]; why: string };

const PAIR = "one file, or a pair (R1 and R2)";
/** What may leave, said before anything does (issue 135): a sample nothing here reads goes, as
 *  about 8 KB of its text, to the AI. */
const TO_AI = "if nothing here reads its type, about 8 KB of its text goes to the AI to read";

export function SampleUpload({
  proposalId,
  label,
  busy,
  onUpload,
  onAnswered,
  onMeasuring = () => {},
  onPicked = () => {},
  reading = null,
}: {
  proposalId: string;
  label: string;
  busy: boolean;
  onUpload: (files: File[]) => Promise<SampleInspected>;
  /** The sample answered this question: the log keeps the result above the next one. */
  onAnswered: (result: SampleInspected, files: string[]) => void;
  /** While a sample is out, the question's other answers wait: two answers must not race. */
  onMeasuring?: (measuring: boolean) => void;
  /** Files are picked or out: *Measure* is the card's one primary action (issue 231). */
  onPicked?: (picked: boolean) => void;
  /** The AI reading this question's sample (issue 135), as the server keeps it. */
  reading?: SampleReading | null;
}) {
  const field = useId();
  const [stage, setStageOnly] = useState<Stage>({ at: "offered" });
  const setStage = (next: Stage) => {
    setStageOnly(next);
    onPicked(next.at === "picked" || next.at === "measuring" || next.at === "reading");
  };
  const [refusal, setRefusal] = useState<string | null>(null);

  const pick = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (files.length === 0) return;
    if (files.length > 2) {
      setRefusal(`${files.length} files: upload ${PAIR}.`);
      setStage({ at: "offered" });
      return;
    }
    setRefusal(null);
    setStage({ at: "picked", files });
  };

  const measure = async (files: File[]) => {
    setStage({ at: "measuring", files });
    onMeasuring(true);
    try {
      const result = await onUpload(files);
      const names = files.map((f) => f.name);
      if (result.outcome === "reading") setStage({ at: "reading", files });
      else if (result.session.pending_proposal?.id !== proposalId) onAnswered(result, names);
      else setStage({ at: "done", files, result });
    } catch (error) {
      setStage({
        at: "failed",
        files,
        why: error instanceof Refused ? error.message : "The sample could not be sent. Try again.",
      });
    } finally {
      onMeasuring(false);
    }
  };

  // **The AI's reading drives the card** (issue 135). A type the engine reads comes back as
  // `hand_back`: the files this card still holds are sent again, once per attempt.
  const held = "files" in stage ? stage.files : null;
  const resent = useRef<number | null>(null);
  useEffect(() => {
    if (reading?.state !== "hand_back" || !held || resent.current === reading.attempt) return;
    resent.current = reading.attempt ?? 1;
    void measure(held);
    // Keyed on the reading alone, on purpose: once per attempt, whatever else re-renders.
  }, [reading?.state, reading?.attempt]);
  const handBackGone = reading?.state === "hand_back" && !held;
  const pickLabel = handBackGone ? `Measure as ${reading?.type_id}` : label;

  const picker = (
    <>
      <label
        htmlFor={field}
        aria-disabled={busy || undefined}
        // **A drop is a pick** at any width: without it a file dropped on this dashed control is
        // opened by the browser, which leaves the builder (review of issue 134).
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!busy) pick(e.dataTransfer.files);
        }}
        // **Busy looks busy** (issue 228): the input is disabled, so the label must not invite a
        // click it cannot take.
        className={`inline-flex items-center justify-center gap-[8px] min-h-[44px] md:min-h-0
                   px-[14px] py-[7px] text-[12.5px] font-semibold border border-dashed
                   text-link bg-[var(--link-soft)] has-[:focus-visible]:shadow-[var(--ring)]
                   ${busy ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
        style={{ borderColor: "var(--link)" }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="square" aria-hidden="true">
          <path d="M12 16V4M6 10l6-6 6 6M4 20h16" />
        </svg>
        {pickLabel}
        <input
          id={field}
          type="file"
          multiple
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            pick(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
    </>
  );

  return (
    <div className="flex flex-col gap-[10px] w-full">
      {reading?.state === "pending" ? (
        <Reading files={held} />
      ) : reading?.state === "hand_back" && held ? (
        <p className="m-0 font-data text-[11.5px] text-ink-2" aria-live="polite">
          read by AI: {reading.type_id}{" "}
          <span className="text-[var(--measured)] animate-pulse motion-reduce:animate-none">→</span>{" "}
          measuring…
        </p>
      ) : (
        <ReadingSaid reading={reading} />
      )}
      {reading?.state !== "pending" && !(reading?.state === "hand_back" && held) &&
        (stage.at === "offered" || stage.at === "done" || stage.at === "failed" ||
          (stage.at === "reading" && reading?.state !== undefined)) && (
        <div className="flex flex-col gap-[6px] md:items-start">
          {picker}
          <p className="m-0 font-data text-[10px] text-ink-3">
            {handBackGone
              ? "only the first 4 MB is read, on this server"
              : `${PAIR} · only the first 4 MB is read, on this server · ${TO_AI}`}
          </p>
        </div>
      )}
      {refusal && <p role="alert" className="m-0 text-[11.5px] text-[var(--undecided)]">{refusal}</p>}

      {(stage.at === "picked" || stage.at === "measuring") && (
        <div className="flex flex-col gap-[10px]">
          <Picked files={stage.files} />
          {stage.at === "picked" ? (
            <>
              <p className="m-0 font-data text-[10px] text-ink-3">
                only the first 4 MB of each is read, on this server · the rest never leaves your
                computer · {TO_AI.replace(" to read", "")}
              </p>
              <div className="flex items-center gap-[8px]">
                <Primary disabled={busy} onClick={() => void measure(stage.files)}>Measure</Primary>
                <Secondary onClick={() => setStage({ at: "offered" })}>Change</Secondary>
              </div>
            </>
          ) : (
            <p className="m-0 font-data text-[11.5px] text-ink-2" aria-live="polite">
              <span className="text-[var(--measured)] animate-pulse motion-reduce:animate-none">●</span>{" "}
              reading the first 4 MB, then measuring…
            </p>
          )}
        </div>
      )}

      {stage.at === "done" && (reading?.state === "hand_back" || reading?.state === "handed") &&
        stage.result.outcome === "measured" && (
        <p className="m-0 font-data text-[12px]">
          <span className="text-ink">{stage.result.type_id ?? reading.type_id}</span>{" "}
          <span className="text-[var(--measured)]">· type read by AI</span>
        </p>
      )}
      {stage.at === "done" && (
        <Outcome result={stage.result} files={stage.files.map((f) => f.name)} />
      )}
      {stage.at === "reading" && held && (reading?.state === "no_answer" ||
        reading?.state === "refused") && (
        <div className="flex md:items-start">
          <Secondary disabled={busy} onClick={() => void measure(held)}>Measure again</Secondary>
        </div>
      )}
      {stage.at === "failed" && (
        <div className="flex flex-col gap-[8px] md:items-start">
          <p role="alert" className="m-0 text-[11.5px] text-[var(--undecided)]">{stage.why}</p>
          {/* The same files, again: the sentence says *try again* (issue 228). A sample the
              server did record answers with its own refusal, which says so. */}
          <Secondary disabled={busy} onClick={() => void measure(stage.files)}>
            Measure again
          </Secondary>
        </div>
      )}
    </div>
  );
}

/** The AI is reading the sample (issue 135): the card waits, and says what went where. */
function Reading({ files }: { files: File[] | null }) {
  return (
    <div className="flex flex-col gap-[6px]">
      {files && (
        <p className="m-0 font-data text-[11px] text-ink-2">{files.map((f) => f.name).join(" + ")}</p>
      )}
      <p className="m-0 font-data text-[11.5px] text-ink" aria-live="polite">
        <span className="text-[var(--measured)] animate-pulse motion-reduce:animate-none">●</span>{" "}
        being read by AI…
      </p>
      <p className="m-0 text-[11.5px] text-ink-3">
        About 8 KB of its text went to the AI. It names a type and facts from this registry only.
      </p>
    </div>
  );
}

/** What the AI's reading said, once it is over: what it read, or why nothing was recorded. */
function ReadingSaid({ reading }: { reading: SampleReading | null }) {
  if (!reading) return null;
  if (reading.state === "read") {
    const lines = [reading.type_id, ...(reading.states ?? [])].filter(Boolean) as string[];
    return (
      <div className="flex flex-col gap-[8px]">
        <ul className="m-0 p-0 list-none flex flex-col gap-[7px] font-data text-[12px]">
          {lines.map((line) => (
            <li key={line}>
              <span className="text-ink">{line}</span>{" "}
              <span className="text-[var(--measured)]">· read by AI</span>
            </li>
          ))}
        </ul>
        {(reading.disagreed ?? []).map((subject) => (
          <p key={subject} className="m-0 px-[10px] py-[9px] text-[11px] text-ink-2 border"
            style={{ borderColor: "var(--line-2)" }}>
            {subject} — you said otherwise. What you said stands.
          </p>
        ))}
      </div>
    );
  }
  if (reading.state === "hand_back")
    return (
      <Said head={<>looks like {reading.type_id} <span className="text-[var(--measured)]">· read by AI</span></>}
        sub="This server measures that type. Pick the same files again and it measures them; nothing else is sent to the AI." />
    );
  const said: Record<string, [string, string]> = {
    could_not_tell: ["the AI couldn't tell what this file is", "Nothing was recorded. Answer below, or try another file."],
    refused: ["the AI's answer named something this registry doesn't declare · nothing was recorded",
      reading.code ?? ""],
    no_answer: ["the AI didn't answer", "No model answered in time. Nothing was recorded; the same file can be read again."],
  };
  const found = said[reading.state];
  return found ? <Said head={found[0]} sub={found[1]} alert={reading.state === "refused"} /> : null;
}

function Said({ head, sub, alert = false }: { head: React.ReactNode; sub: string; alert?: boolean }) {
  return (
    <div className="px-[10px] py-[9px] border" role={alert ? "alert" : undefined}
      style={{ borderColor: "var(--line-2)", background: alert ? "var(--undecided-soft)" : "var(--surface)" }}>
      <p className="m-0 font-data text-[12px] text-ink">{head}</p>
      {sub && <p className="m-0 mt-[6px] text-[11px] text-ink-2">{sub}</p>}
    </div>
  );
}

function Picked({ files }: { files: File[] }) {
  return (
    <ul className="m-0 p-0 list-none border" style={{ borderColor: "var(--line)" }}>
      {files.map((file, i) => (
        <li
          key={file.name}
          className="flex items-center gap-[10px] px-[10px] py-[8px]"
          style={i > 0 ? { borderTop: "1px solid var(--line)" } : undefined}
        >
          {files.length === 2 && (
            <span className="font-data text-[9.5px] text-ink-3 w-[22px]">R{i + 1}</span>
          )}
          <span className="font-data text-[12px] text-ink grow">{file.name}</span>
          <span className="font-data text-[11px] text-ink-2">{bytes(file.size)}</span>
        </li>
      ))}
    </ul>
  );
}

/** What a sample said when the question stays: why not, and what it recorded meanwhile. */
function Outcome({ result, files }: { result: SampleInspected; files: string[] }) {
  if (result.outcome === "measured") return <SampleResult result={result} files={files} />;
  const said =
    result.outcome === "no_inspector"
      ? `nothing reads ${extension(files[0])} files yet`
      : result.reason ?? "it could not be read";
  return (
    <div className="px-[10px] py-[9px] border"
      style={{ borderColor: "var(--line-2)", background: "var(--undecided-soft)" }}>
      <p className="m-0 font-data text-[12px] text-ink">
        {result.outcome === "unreadable" && (
          <span className="text-[var(--undecided)]">couldn't read it — </span>
        )}
        {said}
      </p>
      <p className="m-0 mt-[6px] text-[11px] text-ink-2">
        {result.outcome === "no_inspector"
          ? "Nothing was read. This server can measure FASTQ files, plain or gzipped."
          : "Nothing was recorded."}
      </p>
    </div>
  );
}

/** The facts a sample measured, one line each, and any difference from what was said. */
export function SampleResult({ result, files }: { result: SampleInspected; files: string[] }) {
  const open = result.facts.filter((f) => f.undetermined !== null && f.undetermined !== undefined);
  const decided = result.facts.filter((f) => !open.includes(f));
  return (
    <div className="flex flex-col gap-[8px]">
      <p className="m-0 font-data text-[10px] text-ink-3">from {files.join(" + ")}</p>
      {open.map((f) => (
        <p key={f.measurement} className="m-0 px-[10px] py-[9px] font-data text-[12px] border"
          style={{ borderColor: "var(--line-2)", background: "var(--undecided-soft)" }}>
          <span className="text-ink">{f.measurement.replace(/_/g, " ")}:</span>{" "}
          <span className="text-[var(--undecided)]">undetermined</span>{" "}
          <span className="text-ink">— {f.undetermined}</span>
        </p>
      ))}
      {decided.length > 0 && (
        <ul className="m-0 p-0 list-none flex flex-col gap-[7px] font-data text-[12px]">
          {decided.map((f) => (
            <li key={f.measurement}>
              <span className="text-ink">{f.measurement} {shown(f.value)}</span>{" "}
              <span className="text-[var(--measured)]">· measured</span>
              {how(f) && <span className="text-ink-2"> · {how(f)}</span>}
            </li>
          ))}
        </ul>
      )}
      {result.disagreed.map((subject) => {
        const fact = result.facts.find((f) => f.measurement === subject);
        return (
          <div key={subject} className="px-[10px] py-[9px] border"
            style={{ borderColor: "var(--line-2)", background: "var(--surface)" }}>
            <p className="m-0 font-data text-[12px] text-ink">
              {subject} <span className="text-ink-2">— you said otherwise; the sample reads it as
              {" "}{shown(fact?.value)}</span>
            </p>
            <p className="m-0 mt-[6px] text-[11px] text-ink-2">
              What you said stands. If the sample is right, change it on the goal card before you
              build.
            </p>
          </div>
        );
      })}
    </div>
  );
}

const shown = (value: InspectedFact["value"] | undefined) =>
  value === true ? "yes" : value === false ? "no" : String(value ?? "");


/** How much was read, from the counts the measure reported; each part only when it is there. */
function how(f: InspectedFact): string {
  const e = f.evidence ?? {};
  const parts: string[] = [];
  if (f.pieces?.length) parts.push(piece(f.pieces[0]));
  const said: string[] = [];
  if (typeof e.records === "number") said.push(`${e.records.toLocaleString("en")} reads`);
  if (typeof e.share === "number" && typeof f.value === "number")
    said.push(`${Math.round(e.share * 100)}% at ${f.value}`);
  if (typeof e.pairs === "number") {
    said.push(`${e.pairs.toLocaleString("en")} pairs`);
    if (e.agreeing === e.pairs) said.push("every name agrees");
  }
  if (said.length) parts.push(said.join(", "));
  return parts.join(" · ");
}

/** `reads.bam` → `.bam`, and `reads.bam.gz` → `.bam`: the type a person named the file as. */
const extension = (name: string | undefined) => {
  const stem = (name ?? "").replace(/\.gz$/i, "");
  const dot = stem.lastIndexOf(".");
  return dot >= 0 ? stem.slice(dot) : "these";
};
