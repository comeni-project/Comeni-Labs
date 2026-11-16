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

/** A file's size: *1.4 MB*, *2.7 MB*, *980 KB*. */
export const bytes = (n: number) => {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return i === 0 ? `${v} B` : `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
};
