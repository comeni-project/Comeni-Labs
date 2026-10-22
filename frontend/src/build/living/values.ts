import { open, optionalOpen, type AnsweredStep } from "../useBuilder";

export type Values = { total: number; settled: number; measured: number; open: number; optional: number };

/** **How a pipeline's values were decided**, counted: measured from the person's files (tier 3),
 *  still open (tier 4, not answered, and needed), open but optional (issue 384), and settled — by a
 *  rule, a convention, or the person.
 *  `SettingView` records no model's choice per value, so there is no count of one. */
export function valuesOf(steps: AnsweredStep[]): Values {
  const all = steps.flatMap((step) => step.settings);
  const opened = all.filter(open).length;
  const optional = all.filter(optionalOpen).length;
  const measured = all.filter((setting) => setting.tier === 3).length;
  return { total: all.length, settled: all.length - opened - optional - measured, measured, open: opened, optional };
}
