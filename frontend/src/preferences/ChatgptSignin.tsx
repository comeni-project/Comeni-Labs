import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { primaryButton, secondaryButton } from "./providers";

type Device = { session: string; user_code: string; verification_url: string; interval: number; expires_at: number };

/** These routes return sanitized, actionable errors, including failures to store a sign-in. */
async function signInRequest<T>(path: string, method = "GET"): Promise<T> {
  const response = await fetch(`/api/settings/models/chatgpt${path}`, {
    method,
    ...(method === "POST" && { headers: { "Content-Type": "application/json" }, body: "{}" }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail
    : "Could not reach Comeni’s sign-in service. Check that the server is running and try again.");
  return body as T;
}

/** Uses the installation's shared LiteLLM sign-in. Credentials never enter the browser. */
export function ChatgptSignin({ onReady }: { onReady: () => void }) {
  const [device, setDevice] = useState<Device | null>(null);
  const [copied, setCopied] = useState(false);
  const status = useQuery({ queryKey: ["chatgpt-signin"],
    queryFn: () => signInRequest<{ signed_in: boolean }>(""), retry: false });
  const start = useMutation({ mutationFn: () => signInRequest<Device>("/sign-in", "POST"),
    onSuccess: (next) => { setDevice(next); setCopied(false); } });
  const progress = useQuery({
    queryKey: ["chatgpt-signin", device?.session],
    queryFn: () => signInRequest<{ state: "pending" | "connected" | "expired" }>(`/sign-in/${device!.session}`, "POST"),
    enabled: !!device,
    retry: false,
    refetchInterval: (query) => query.state.data?.state === "connected" || query.state.data?.state === "expired"
      || Date.now() / 1000 > (device?.expires_at ?? 0) ? false : (device?.interval ?? 5) * 1000,
  });
  const ready = progress.data?.state === "connected" || status.data?.signed_in;
  useEffect(() => { if (ready) onReady(); }, [ready, onReady]);

  if (ready) return <p role="status" className="connection-notice text-done-ink">Sign-in saved on this installation. Choose a model below.</p>;
  const expired = progress.data?.state === "expired" || (device && Date.now() / 1000 > device.expires_at);
  const failure = start.error ?? progress.error ?? (device ? null : status.error);
  return (
    <div className="connection-signin">
      <p className="m-0 text-secondary text-ink-2">Sign in on OpenAI’s website to authorize the subscription connection. This sign-in is shared by this Comeni installation.</p>
      {status.isPending && <p role="status" className="m-0 text-secondary text-ink-3">Checking saved sign-in…</p>}
      {(!device || expired) && <button type="button" onClick={() => start.mutate()} disabled={start.isPending || status.isPending}
        className={primaryButton}>{start.isPending ? "Starting sign-in…" : expired ? "Start a new sign-in" : "Continue with ChatGPT"}</button>}
      {device && !expired && <>
        <div className="flex flex-wrap items-center gap-3">
          <code className="connection-device-code">{device.user_code}</code>
          <button type="button" className={secondaryButton} onClick={async () => {
            try { await navigator.clipboard.writeText(device.user_code); setCopied(true); } catch { setCopied(false); }
          }}>{copied ? "Copied" : "Copy code"}</button>
          <a className={primaryButton} href={device.verification_url} target="_blank" rel="noreferrer">Open sign-in page ↗</a>
        </div>
        <p role="status" className="m-0 text-secondary text-ink-3">Enter this code on the sign-in page. Waiting for approval…</p>
      </>}
      {expired && <p role="status" className="m-0 text-secondary text-needs-you-ink">This code expired. Start a new sign-in.</p>}
      {failure && <p role="alert" className="m-0 text-secondary text-needs-you-ink">
        {failure.message}
      </p>}
    </div>
  );
}
