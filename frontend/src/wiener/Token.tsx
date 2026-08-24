/** Where a person puts the token Wiener asks for.
 *
 * **The smallest real thing** — §12.1: one shared bearer token, no user table, no session, no
 * reset flow, and issue #83 is per-person identity. It lives in `localStorage` rather than in
 * the bundle, because a build-time variable would put the credential in a JavaScript file
 * served to anyone who asks for the page.
 *
 * It appears **only when a request has actually been refused**, never as a field on a page
 * that is working. An unconfigured Wiener accepts every request and says so in its own logs;
 * asking for a token nobody set would be the page inventing a requirement.
 */
import { useState } from "react";

import { setToken, Unauthorized } from "./api/client";

export function isUnauthorized(error: unknown): boolean {
  return error instanceof Unauthorized;
}

export function TokenPrompt({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState("");

  return (
    <form
      data-testid="token-prompt"
      className="flex flex-col gap-2 p-4 rounded-r bg-surface-2 border border-line max-w-lg"
      onSubmit={(event) => {
        event.preventDefault();
        setToken(value.trim() || null);
        onSaved();
      }}
    >
      <span className="text-body font-semibold">This Wiener wants a token</span>
      <p className="text-secondary text-ink-3">
        It is the value of <code className="font-data">WIENER_API_TOKEN</code> in the{" "}
        <code className="font-data">.env</code> beside the compose file. It is kept in this
        browser and sent as a header — never built into the page.
      </p>
      <div className="flex gap-2">
        <input
          data-testid="token-input"
          type="password"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="paste the token"
          className="flex-1 px-2 py-1 rounded-r bg-surface border border-line font-data
                     text-body text-ink"
        />
        <button
          type="submit"
          data-testid="token-save"
          className="px-3 py-1 rounded-r text-body font-semibold bg-pea text-[var(--on-pea)]
                     border-0"
        >
          Save
        </button>
      </div>
    </form>
  );
}
