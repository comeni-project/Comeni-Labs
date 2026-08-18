/** The typed fetch wrapper.
 *
 * One place turns a 422 into a `Refused`, so every caller gets the API's own coded message
 * rather than "Request failed". `mendel_forge.http` answers 422 for a coded refusal and
 * `mendel-api` matches it — spec §4.2, and `Refusal` in the generated schema is its shape.
 */
import type { components } from "./schema";

type Refusal = components["schemas"]["Refusal"];

export class Refused extends Error {}

async function body(r: Response): Promise<unknown> {
  try {
    return await r.json();
  } catch {
    return null;
  }
}

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}

export async function post<T>(path: string, payload: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (r.status === 422) {
    const detail = (await body(r)) as Refusal | null;
    throw new Refused(detail?.detail ?? "refused, with no reason given");
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}
