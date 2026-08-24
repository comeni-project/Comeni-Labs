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
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}

export async function post<T>(path: string, payload: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });
  if (r.status === 422) {
    const detail = ((await r.json().catch(() => null)) as { detail?: ParamRefusal } | null)
      ?.detail;
    if (detail?.message) {
      throw new Refused(detail.message, detail.declared, detail.unknown, detail.missing);
    }
    throw new Refused("refused, with no reason given");
  }
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return (await r.json()) as T;
}
