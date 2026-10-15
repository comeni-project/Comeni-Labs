/** Wiener HTTP wrapper. Callers supply complete /api paths.
 * Requests carry the browser-held bearer token; write responses preserve parameter details
 * and server refusal sentences. The development proxy reaches Wiener through nginx. */
/** Signals a missing or rejected token so callers can offer the shared token-entry UI. */
export class Unauthorized extends Error {}

/** A submission refusal, including declared, unknown and missing parameter keys. */
export class Refused extends Error {

  // Explicit fields and assignments comply with the project's erasableSyntaxOnly setting.
  declared: string[];
  unknownKeys: string[];
  missing: string[];

  constructor(message: string, declared: string[] = [], unknownKeys: string[] = [],
              missing: string[] = []) {
    super(message);
    this.declared = declared;
    this.unknownKeys = unknownKeys;
    this.missing = missing;
  }
}

type ParamRefusal = {
  message: string;
  declared: string[];
  unknown: string[];
  missing: string[];
};

const TOKEN_KEY = "wiener.token";

/** Read the token from local storage; return null when storage is unavailable.
 * The credential is supplied at runtime, rather than embedded in the browser bundle. */
export function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Store or clear the token. If storage is unavailable, later requests can still prompt on 401. */
export function setToken(value: string | null): void {
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {

  }
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const held = token();
  return held ? { ...extra, Authorization: `Bearer ${held}` } : extra;
}

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: headers() });
  if (r.status === 401) throw new Unauthorized("this Wiener wants a token");
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}

/** A file, as `multipart/form-data`. The artifact upload is the only one.
 *
 * **No `Content-Type` header.** The browser sets it, and the boundary it appends is what makes
 * the body parseable — a hand-written `multipart/form-data` header omits the boundary and the
 * server answers 422 for a body it cannot split.
 */
/** `fields` carries what travels *beside* the file — the pipeline's name, today.
 *
 *  **A multipart form rather than a query string**, because the name is free text somebody
 *  typed and a URL is the one place this repository has a rule about: invariant 15's shape,
 *  and the privacy rule that personal data never goes in a query string. A name is not
 *  personal data, but the habit is the guard. */
/** Upload a file and accompanying fields as multipart data.
 * Let the browser supply Content-Type and its boundary. Names travel in the body. */
export async function upload<T>(path: string, field: string, file: Blob,
                                filename: string,
                                fields: Record<string, string> = {}): Promise<T> {
  const form = new FormData();
  form.append(field, file, filename);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  const r = await fetch(path, { method: "POST", headers: headers(), body: form });
  if (r.status === 401) throw new Unauthorized("this Wiener wants a token");
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}

export async function post<T>(path: string, payload: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (r.status === 401) throw new Unauthorized("this Wiener wants a token");
  if (r.status === 422) {
    const detail = ((await r.json().catch(() => null)) as { detail?: ParamRefusal } | null)
      ?.detail;
    if (detail?.message) {
      throw new Refused(detail.message, detail.declared, detail.unknown, detail.missing);
    }
    throw new Refused("refused, with no reason given");
  }
  if (r.status === 409) {
    // **A refusal's whole value is its sentence.** `cancel` answers *this run is already
    // succeeded* or *this run was launched on another host*, and a reader who sees
    // `/api/runs/…/cancel → 409` learns nothing they can act on. Found in the browser: the
    // server said the useful thing and this function threw it away.
    const detail = ((await r.json().catch(() => null)) as { detail?: string } | null)?.detail;
    throw new Error(detail || `${path} → 409`);
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}

/** `DELETE` (Part H): a finished run. A 409 is the server's sentence — *cancel it first* — and
 *  a 204 answers nothing. */
/** Delete a resource, accepting an empty 204 response and preserving 409/422 explanations. */
export async function remove(path: string): Promise<void> {
  const r = await fetch(path, { method: "DELETE", headers: headers() });
  if (r.status === 401) throw new Unauthorized("this Wiener wants a token");
  if (r.status === 204) return;
  if (r.status === 409 || r.status === 422) {
    const detail = ((await r.json().catch(() => null)) as { detail?: string } | null)?.detail;
    throw new Error(detail || `${path} → ${r.status}`);
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
}

/** `PUT` (Part H): one of Wiener's own settings. Its refusals are sentences, as `remove`'s. */
/** Replace a setting or resource, preserving the server's 409/422 explanation. */
export async function put<T>(path: string, payload: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "PUT",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (r.status === 401) throw new Unauthorized("this Wiener wants a token");
  if (r.status === 409 || r.status === 422) {
    const detail = ((await r.json().catch(() => null)) as { detail?: string } | null)?.detail;
    throw new Error(detail || `${path} → ${r.status}`);
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}
