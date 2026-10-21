import { useId, useState } from "react";

import type { Answered } from "../../useBuilder";
import { Primary, Secondary } from "./parts";

const COUNT = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

/** One open value of an opened step, asked as a question (the *Question* board).
 *
 * **Only what the setting carries**: its name, why it is open, and its declared domain. The board's
 * notes under each answer have no source (a domain is a list of values), so none are drawn; a
 * setting with no domain is a typed field, and a range says its bounds. The answer and the
 * person's reason go through the draft's setting write, where the server stamps the tier and keeps
 * the reason as the value's recorded one — so the card says the reason is saved, and nothing more.
 */
export function QuestionCard({
  setting,
  onSave,
  onCancel,
}: {
  setting: Answered;
  onSave: (value: string, why: string) => void;
  onCancel: () => void;
}) {
  const group = useId();
  const values = setting.domain?.values ?? [];
  const [value, setValue] = useState(setting.value !== null && values.includes(setting.value) ? setting.value : "");
  const [why, setWhy] = useState("");
  const { minimum, maximum } = setting.domain ?? {};

  return (
    <section aria-label={`a value for ${setting.name}`} className="rounded-panel border px-[16px] pt-[14px] pb-[16px]"
             style={{ borderColor: "var(--needs-you)", background: "var(--surface)" }}>
      <header className="flex items-baseline gap-[10px] mb-[6px]">
        <h3 className="m-0 text-[15px] font-semibold text-ink min-w-0">What should <span className="font-data">{setting.name}</span> be?</h3>
        <span className="ml-auto shrink-0 rounded-full px-[9px] py-[1px] text-[11.5px] font-semibold"
              style={{ background: "var(--needs-you-soft)", color: "var(--needs-you-ink)" }}>
          needs you
        </span>
      </header>
      <p className="m-0 mb-[10px] font-data text-[11.5px] text-ink-3">settings.{setting.name}</p>
      {setting.reason && (
        <p className="m-0 mb-[12px] pl-[10px] text-[13px] leading-[1.55] text-ink-2"
           style={{ borderLeft: "2px solid var(--needs-you)" }}>
          {setting.reason}
        </p>
      )}
      {values.length > 0 ? (
        <>
          <p className="m-0 mb-[8px] text-[12.5px] text-ink-2">
            <span className="font-semibold text-ink">Answer from what you know</span>
            {" · "}these {COUNT[values.length] ?? values.length} are all the answers there are
          </p>
          <div role="radiogroup" aria-label={`values for ${setting.name}`}>
            {values.map((option) => {
              const picked = value === option;
              return (
                <label key={option}
                       className="flex items-center gap-[10px] px-[12px] py-[9px] mb-[8px] border rounded-button
                                  cursor-pointer focus-within:shadow-[var(--ring)]"
                       style={{ borderColor: picked ? "var(--now)" : "var(--line-2)",
                                background: picked ? "var(--now-soft)" : "var(--surface)" }}>
                  <input type="radio" name={group} value={option} checked={picked}
                         onChange={() => setValue(option)} className="sr-only" />
                  <span aria-hidden className="shrink-0 w-[16px] h-[16px] rounded-full border"
                        style={{ borderColor: picked ? "var(--now)" : "var(--line-2)",
                                 background: picked ? "radial-gradient(circle, var(--now) 0 4px, var(--surface) 4.5px)"
                                   : "var(--surface)" }} />
                  <span className="font-data text-[12.5px] font-semibold text-ink">{option}</span>
                </label>
              );
            })}
          </div>
        </>
      ) : (
        <label className="block mb-[8px]">
          <span className="block mb-[4px] text-[12.5px] text-ink-2">
            <span className="font-semibold text-ink">Answer from what you know</span>
            {minimum != null && maximum != null ? ` · a value from ${minimum} to ${maximum}` : ""}
          </span>
          <input aria-label={setting.name} value={value} onChange={(e) => setValue(e.target.value)}
                 className="w-full px-[12px] py-[8px] rounded-button border bg-[var(--surface)] font-data text-[13px]
                            text-ink focus-visible:shadow-[var(--ring)]"
                 style={{ borderColor: "var(--line-2)" }} />
        </label>
      )}
      <textarea aria-label="Your reason" rows={2} value={why} onChange={(e) => setWhy(e.target.value)}
                placeholder="Why this value — a kit, a report, a colleague"
                className="block w-full mt-[4px] px-[12px] py-[8px] rounded-button border bg-[var(--surface)]
                           text-[13px] text-ink placeholder:text-ink-3 resize-y focus-visible:shadow-[var(--ring)]"
                style={{ borderColor: "var(--line-2)" }} />
      <p className="m-0 mt-[8px] text-[12px] text-ink-3">Your reason is saved beside the value in the pipeline file.</p>
      <div className="flex flex-wrap items-center gap-[8px] mt-[12px]">
        <Primary disabled={value.trim() === ""} onClick={() => onSave(value.trim(), why.trim())}>Save answer</Primary>
        <Secondary onClick={onCancel}>Cancel</Secondary>
      </div>
    </section>
  );
}
