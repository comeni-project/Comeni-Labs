/** Mendel HTTP wrapper. Paths are relative to /api.
 * JSON mutations and form uploads preserve coded refusals; reads report HTTP errors directly. */
import type { components } from "./schema";

type Refusal = components["schemas"]["Refusal"];

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
/** Read a successful response as bytes, for routes such as pipeline bundle downloads. */
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

/** `DELETE`, for what a person deletes (Part H). Answers nothing on success (204); a refusal is
 *  a `Refused` with its coded sentence, as everywhere. */
/** Delete a resource. A 204 returns no body; other responses use the JSON/refusal handler. */
export async function remove(path: string): Promise<void> {
  const r = await fetch(ROOT + path, { method: "DELETE" });
  if (r.status === 204) return;
  await answered<unknown>(path, r);
}

/** A multipart form — today, an uploaded sample (issue 134).
 *
 * **No `Content-Type` header**: the browser writes it, with the boundary the body needs. The
 * answer goes through `answered`, so a coded refusal is a `Refused` here as everywhere. */
/** Send FormData using the browser-generated Content-Type and multipart boundary. */
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
  // Preserve application refusal sentences. A 403 without one remains a path/status error.
  if (r.status === 422 || r.status === 409 || r.status === 403) {
    const detail = (await body(r)) as Refusal | null;
    if (detail?.detail) throw new Refused(detail.detail);
    if (r.status !== 403) throw new Refused("refused, with no reason given");
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}
