import { useState } from "react";
import { Link, useParams } from "react-router";

import type { AuthoringBlock } from "../../api/types";
import { analysisAddress } from "../../app/address";
import { Primary, Secondary } from "./blocks/parts";

type Ask = Extract<AuthoringBlock, { kind: "ask" }>;
export type AnswerValue = string | number | boolean;

/** **A question the agent put to the person** (#463), drawn in the shape of answer it takes:
 *  options as buttons, a number with its unit, yes or no, a pointer to Data, or words. Answering sends
 *  the answer as the person's next turn; typing in the composer instead is always fine too. */
export function AgentQuestion({ question, onAnswer, disabled = false }: {
  question: Ask;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  disabled?: boolean;
}) {
  const answer = (value: AnswerValue) => onAnswer(question.question_id, value);
  const { draft } = useParams();
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
      {/* **Data is where samples come from** (#511): ticked in its folders, never uploaded here. */}
      {question.shape === "data" && draft && (
        <Link to={analysisAddress(draft, "data")}
              className="self-start px-[14px] py-[7px] text-[12.5px] font-semibold rounded-button no-underline
                         text-now-ink bg-now-soft border border-now-line">
          Open Data
        </Link>
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
