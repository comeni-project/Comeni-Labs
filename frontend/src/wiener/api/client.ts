/** Wiener's typed fetch wrapper.
 *
 * Separate from `../../api/client` because the **refusal shape differs**: Mendel answers 422
 * with a coded `Refusal` string, and Wiener's submit answers with the parameters an artifact
 * declares and which of them are unknown or missing (§12). One wrapper trying to be both would
 * turn the useful half of that into "refused, with no reason given".
 *
 * The paths are the API's own — `/api/runs`, `/api/artifacts` — and the dev proxy sends exactly
 * those to 8001.
 */

/** A 401 from Wiener: the token is missing or wrong.
 *
 * **A distinct class rather than a status number in a message string**, because two screens
 * have to react to it — the board and the builder's submit panel — and both must offer the
 * same thing: a field to paste the token into. Matching on `"→ 401"` in a message is how one
 * of them stops recognising it.
 */
export class Unauthorized extends Error {}

export class Refused extends Error {
  // Plain fields and an explicit assignment: `readonly` parameter properties are
  // constructor-side syntax, and this project builds with `erasableSyntaxOnly`.
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

/** The bearer token, held in the browser rather than baked into the bundle.
 *
 * **A build-time env var would put the credential in a JavaScript file** served to anyone who
 * asks for the page, which is a worse place for it than a request header. This is deliberately
 * the smallest thing that works for one deployment and one token — §12.1's check is real, and
 * OAuth is issue #83.
 */
export function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;   // a private window, or storage the browser refuses
  }
}

export function setToken(value: string | null): void {
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to do: the request will 401 and the page will ask again */
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
