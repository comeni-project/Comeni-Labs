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

/** Several query parameters in ONE write.
 *
 * **Two `useUrlState` setters called from one handler clobber each other**, and that is not a
 * subtle race: both close over the same `params` from the render they were created in, so the
 * second builds its copy from a `URLSearchParams` that never saw the first. Setting a filter
 * and resetting the page number is exactly that shape, and the symptom is the filter silently
 * not applying — found by a test asserting the URL rather than the rendered table, because the
 * table looked plausible either way.
 *
 * An empty string REMOVES the key, the same rule `useUrlState` uses: a link says what is
 * unusual about a view rather than restating every default.
 */
export function useUrlPatch(): (patch: Record<string, string>) => void {
  const [params, setParams] = useSearchParams();
  return useCallback(
    (patch: Record<string, string>) => {
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(patch)) {
        if (value === "") next.delete(key);
        else next.set(key, value);
      }
      setParams(next, { replace: true });
    },
    [params, setParams],
  );
}
