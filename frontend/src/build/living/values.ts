import { open, optionalOpen, type AnsweredStep } from "../useBuilder";

export type Values = {
  total: number; settled: number; measured: number; read: number; open: number; optional: number;
};

/** **How a pipeline's values were decided**, counted: measured from the person's files, read
 *  from a sample by AI, still open (tier 4, not answered, and needed), open but optional
 *  (issue 384), and settled — by a rule, a convention, or the person.
 *  `SettingView` records no model's choice per value, so there is no count of one.
 *
 *  **Measured is the evidence, never the tier** (issue 397, as issue 268): a rule (tier 3) over a
 *  value the person typed was settled on what they said, and is counted as settled. An unknown
 *  evidence is never called measured. */
export function valuesOf(steps: AnsweredStep[]): Values {
  const all = steps.flatMap((step) => step.settings);
  const opened = all.filter(open).length;
  const optional = all.filter(optionalOpen).length;
  const measured = all.filter((setting) => setting.tier === 3 && setting.evidence === "measured").length;
  const read = all.filter((setting) => setting.tier === 3 && setting.evidence === "read_by_ai").length;
  return { total: all.length, settled: all.length - opened - optional - measured - read, measured, read,
           open: opened, optional };
}
