import { useId, useState } from "react";

import type { AuthoringBlock } from "../../api/types";
import { Primary, Secondary } from "./blocks/parts";

type Ask = Extract<AuthoringBlock, { kind: "ask" }>;
export type AnswerValue = string | number | boolean;

/** **A question the agent put to the person** (#463), drawn in the shape of answer it takes:
 *  options as buttons, a number with its unit, yes or no, an upload, or words. Answering sends
 *  the answer as the person's next turn; typing in the composer instead is always fine too. */
export function AgentQuestion({ question, onAnswer, onUpload, disabled = false }: {
  question: Ask;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  /** Sends the picked files' heads; absent where nothing can be uploaded. */
  onUpload?: (questionId: string, files: File[]) => Promise<unknown>;
  disabled?: boolean;
}) {
  const answer = (value: AnswerValue) => onAnswer(question.question_id, value);
  return (
    <fieldset aria-label={question.question} disabled={disabled}
              className="m-0 px-[14px] py-[12px] rounded-panel border flex flex-col gap-[10px] min-w-0"
              style={{ borderColor: "var(--now-line)", background: "var(--surface)" }}>
      <legend className="sr-only">{question.question}</legend>
      <p aria-hidden className="m-0 text-[13.5px] font-semibold text-ink">{question.question}</p>
      {question.shape === "options" && (
        <div className="flex flex-wrap gap-2">
          {question.options.map((option) => (
            <Secondary key={option} onClick={() => answer(option)}>{option}</Secondary>
          ))}
        </div>
      )}
      {question.shape === "yes_no" && (
        <div className="flex gap-2">
          <Secondary onClick={() => answer(true)}>Yes</Secondary>
          <Secondary onClick={() => answer(false)}>No</Secondary>
        </div>
      )}
      {question.shape === "number" && <NumberAnswer unit={question.unit} onAnswer={answer} />}
      {question.shape === "text" && <TextAnswer onAnswer={answer} />}
      {question.shape === "upload" && onUpload && (
        <UploadAnswer onUpload={(files) => onUpload(question.question_id, files)} />
      )}
    </fieldset>
  );
}

const FIELD = "px-[10px] py-[6px] rounded-control border text-[13px] text-ink bg-transparent min-w-0";

function NumberAnswer({ unit, onAnswer }: { unit: string; onAnswer: (value: number) => void }) {
  const [text, setText] = useState("");
  const value = Number(text);
  const ok = text.trim() !== "" && Number.isFinite(value);
  return (
    <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (ok) onAnswer(value); }}>
      <input type="number" inputMode="decimal" aria-label="your answer" value={text}
             onChange={(e) => setText(e.target.value)} className={`${FIELD} w-[120px]`}
             style={{ borderColor: "var(--line-2)" }} />
      {unit && <span className="text-[12.5px] text-ink-2">{unit}</span>}
      <Primary type="submit" disabled={!ok}>Answer</Primary>
    </form>
  );
}

function TextAnswer({ onAnswer }: { onAnswer: (value: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (text.trim()) onAnswer(text.trim()); }}>
      <input aria-label="your answer" value={text} onChange={(e) => setText(e.target.value)}
             className={`${FIELD} flex-1`} style={{ borderColor: "var(--line-2)" }} />
      <Primary type="submit" disabled={!text.trim()}>Answer</Primary>
    </form>
  );
}

/** Any number of files: a study's every sample at once; the server pairs the mates. **Nothing
 *  leaves before Measure**, and then only each file's head (`useAuthoringSession.upload`). */
function UploadAnswer({ onUpload }: { onUpload: (files: File[]) => Promise<unknown> }) {
  const field = useId();
  const [files, setFiles] = useState<File[]>([]);
  const [state, setState] = useState<"picking" | "measuring" | "failed">("picking");
  const measure = async () => {
    setState("measuring");
    try {
      await onUpload(files);
      setFiles([]);
      setState("picking");
    } catch {
      setState("failed");
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={field}
             onDragOver={(e) => e.preventDefault()}
             onDrop={(e) => { e.preventDefault(); setFiles(Array.from(e.dataTransfer.files)); }}
             className="self-start px-[14px] py-[7px] text-[12.5px] font-semibold border border-dashed rounded-button
                        text-now-ink cursor-pointer has-[:focus-visible]:shadow-[var(--ring)]"
             style={{ borderColor: "var(--now)", background: "var(--now-soft)" }}>
        Choose files
        <input id={field} type="file" multiple className="sr-only"
               onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
      </label>
      {files.length > 0 && (
        <p className="m-0 text-[12px] text-ink-2 break-all">
          {files.length === 1 ? files[0].name : `${files.length} files`}
        </p>
      )}
      {state === "failed" && <p role="alert" className="m-0 text-[12px] text-needs-you-ink">The files could not be sent. Try again.</p>}
      <span className="self-start">
        <Primary disabled={files.length === 0 || state === "measuring"} onClick={() => void measure()}>
          {state === "measuring" ? "Measuring…" : "Measure"}
        </Primary>
      </span>
      <p className="m-0 text-[11.5px] text-ink-3">Only the start of each file is read.</p>
    </div>
  );
}
