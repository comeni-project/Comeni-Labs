import { useCallback } from "react";
import { useSearchParams } from "react-router";

/** One query parameter, read and written as state.
 *
 * **The URL is the state, not a copy of it.** A component holding a `useState` and writing the
 * URL as a side effect has two sources of truth, and the one that loses is the URL — the one a
 * curator pastes into a message to say *look at this*.
 *
 * Setting a value back to its default REMOVES it, so a link says what is unusual about a view
 * rather than restating every default.
 */
export function useUrlState<T extends string = string>(
  key: string,
  // `NoInfer`, or the fallback drives inference and `useUrlState("state", "")` narrows `T` to
  // the empty string — so every `setState("undrafted")` is a type error. `tsc --noEmit` did not
  // catch it and `tsc -b` did, which is why `npm run build` is the frontend gate.
  fallback: NoInfer<T>,
): [T, (next: T) => void] {
  const [params, setParams] = useSearchParams();
  const value = (params.get(key) as T | null) ?? fallback;

  const set = useCallback(
    (next: T) => {
      const copy = new URLSearchParams(params);
      if (next === fallback || next === "") copy.delete(key);
      else copy.set(key, next);
      setParams(copy, { replace: true });
    },
    [params, setParams, key, fallback],
  );

  return [value, set];
}
