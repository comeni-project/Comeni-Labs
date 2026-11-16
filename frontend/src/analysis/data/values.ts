/** A measured value as a person reads it: bases by their size (2.84 Mb, 85 kb), counts with
 *  separators (12,065), booleans as yes or no (#532). */
export const plain = (value: unknown, unit?: string | null) => {
  if (value === true) return "yes";
  if (value === false) return "no";
  if (value == null) return "—";
  if (typeof value !== "number") return String(value);
  if (unit === "bp" && value >= 1e6) return `${(value / 1e6).toFixed(2)} Mb`;
  if (unit === "bp" && value >= 1e4) return `${Math.round(value / 1e3).toLocaleString("en-US")} kb`;
  return value.toLocaleString("en-US");
};

/** The same, with its unit when the number does not already say it: *101 bp*, *2.84 Mb*. */
export const withUnit = (value: number, unit?: string | null) => {
  const shown = plain(value, unit);
  return unit && !/ [kM]b$/.test(shown) ? `${shown} ${unit}` : shown;
};
