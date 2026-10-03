/** The typed fetch wrapper.
 *
 * One place turns a 422 into a `Refused`, so every caller gets the API's own coded message
 * rather than "Request failed". `mendel_forge.http` answers 422 for a coded refusal and
 * `mendel-api` matches it — spec §4.2, and `Refusal` in the generated schema is its shape.
 */
import type { components } from "./schema";

type Refusal = components["schemas"]["Refusal"];

/** Every path this module is given is relative to the API root.
 *
 * It is `/api` because the frontend owns `/forge/*` in the browser and the API mounts the
 * forge transport at the same prefix — one origin, two namespaces, and the dev proxy resolved
 * it in the API's favour so every deep link 404'd. Callers pass `/questions`; the prefix lives
 * here and nowhere else. */
const ROOT = "/api";

export class Refused extends Error {}

async function body(r: Response): Promise<unknown> {
  try {
    return await r.json();
  } catch {
    return null;
  }
}

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(ROOT + path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}

/** A route that answers with a file rather than JSON — today, only the pipeline bundle.
 *
 * **Separate from `get` rather than a flag on it.** `get` parses JSON and turns a 422 into a
 * `Refused`; this returns bytes and has nothing to parse. One function trying to be both would
 * decide which it was by looking at a header, and get it wrong on the day a route answered
 * `application/zip` with an error body.
 */
export async function blob(path: string): Promise<Blob> {
  const r = await fetch(ROOT + path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return await r.blob();
}

export async function post<T>(path: string, payload: unknown): Promise<T> {
  return send<T>("POST", path, payload);
}

/** `PUT`, for the one route that replaces rather than creates: saving a draft.
 *
 * Shares `send` with `post` so the 422-to-`Refused` contract has one implementation. A second
 * copy is how one of them stops turning a coded refusal into a message. */
export async function put<T>(path: string, payload: unknown): Promise<T> {
  return send<T>("PUT", path, payload);
}

/** A multipart form — today, an uploaded sample (issue 134).
 *
 * **No `Content-Type` header**: the browser writes it, with the boundary the body needs. The
 * answer goes through `answered`, so a coded refusal is a `Refused` here as everywhere. */
export async function postForm<T>(path: string, form: FormData): Promise<T> {
  return answered<T>(path, await fetch(ROOT + path, { method: "POST", body: form }));
}

async function send<T>(method: string, path: string, payload: unknown): Promise<T> {
  const r = await fetch(ROOT + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return answered<T>(path, r);
}

async function answered<T>(path: string, r: Response): Promise<T> {
  // **422, 409 and 403 are refusals with a coded reason**: a setting locked between reading
  // and saving (409, `MI0300`), the protection level refusing an upload (403, `MI0213`). The
  // person needs that sentence, not a status code. **A 403 with no reason is not ours**: a
  // proxy's own page stays an error naming the path (issue 228).
  if (r.status === 422 || r.status === 409 || r.status === 403) {
    const detail = (await body(r)) as Refusal | null;
    if (detail?.detail) throw new Refused(detail.detail);
    if (r.status !== 403) throw new Refused("refused, with no reason given");
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}
