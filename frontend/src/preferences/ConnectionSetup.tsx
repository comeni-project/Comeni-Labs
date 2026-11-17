import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { post } from "../api/client";
import { ChatgptSignin } from "./ChatgptSignin";
import { PROVIDERS, primaryButton, providerOf, secondaryButton, setupField, type Connection, type Provider } from "./providers";
import { listModels, type ActionResult } from "./useAction";

export type SetupResult = { connection: Connection; model: string; useDefault: boolean };
type Step = "provider" | "connect" | "model" | "review";
type Detected = { endpoint: string; models: string[] };
const STEPS: Step[] = ["provider", "connect", "model", "review"];
const LABELS = ["Provider", "Connect", "Model", "Finish"];

/** Each step asks for one decision. URLs and provider prefixes stay behind the choices. */
export function ConnectionSetup({ initial, names, defaultAllowed, suggestDefault, pending, error, onSave, onCancel }: {
  initial?: Connection; names: string[]; defaultAllowed: boolean; suggestDefault: boolean;
  pending: boolean; error: string | null; onSave: (result: SetupResult) => void; onCancel: () => void;
}) {
  const needsProvider = initial?.server === "hosted" && (!initial.provider || initial.provider === "custom");
  const [step, setStep] = useState<Step>(initial && !needsProvider ? "connect" : "provider");
  const [provider, setProvider] = useState<Provider | null>(initial && !needsProvider ? providerOf(initial) : null);
  const [name, setName] = useState(initial?.name ?? "");
  const [endpoint, setEndpoint] = useState(initial?.endpoint ?? "");
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [model, setModel] = useState("");
  const [search, setSearch] = useState("");
  const [manual, setManual] = useState(false);
  const [useDefault, setUseDefault] = useState(suggestDefault);
  const [signedIn, setSignedIn] = useState(false);
  const [category, setCategory] = useState("All");
  const revision = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [step]);
  const subscription = provider?.id === "chatgpt";
  const cloud = provider?.category === "API key";
  const discover = useMutation({ mutationFn: (draft: { server: string; provider: string; endpoint: string; key: string | null }) =>
    post<ActionResult>("/settings/models/discover", draft) });
  const detect = useMutation({ mutationFn: (id: string) => post<Detected[]>("/settings/models/detect", { provider: id }) });
  const subscriptionModels = useQuery({ queryKey: ["subscription-models"],
    queryFn: () => post<ActionResult>("/settings/models/chatgpt/models", {}),
    enabled: !!subscription && signedIn && step === "model", retry: false,
    staleTime: 60_000, refetchOnMount: "always", refetchOnWindowFocus: true,
    refetchInterval: 5 * 60_000 });
  const markReady = useCallback(() => { setSignedIn(true); setStep("model"); }, []);
  const changed = () => { revision.current++; setResult(null); discover.reset(); detect.reset(); setModel(""); };
  const detectLocal = async (next: Provider) => {
    const at = revision.current;
    try {
      const found = await detect.mutateAsync(next.id);
      if (at !== revision.current) return;
      if (found.length) {
        setEndpoint(found[0].endpoint);
        setResult({ ok: true, says: `Found ${next.name}.`, values: found[0].models });
        setStep("model");
      }
    } catch { /* The connect step keeps retry and manual address controls available. */ }
  };
  const chooseProvider = (next: Provider) => {
    changed(); setProvider(next); setEndpoint(next.endpoint); setKey(""); setManual(false); setSignedIn(false); setSearch("");
    let candidate: string = next.name;
    for (let n = 2; names.some((existing) => existing.toLowerCase() === candidate.toLowerCase()); n++) candidate = `${next.name} ${n}`;
    setName(initial?.name ?? candidate); setStep("connect");
    if (next.id === "ollama" || next.id === "lmstudio") void detectLocal(next);
  };
  const validUrl = (() => { try { return ["http:", "https:"].includes(new URL(endpoint).protocol); } catch { return false; } })();
  const duplicate = names.some((n) => n.toLowerCase() === name.trim().toLowerCase() && n !== initial?.name);
  const sameScope = !!initial && initial.endpoint === endpoint && providerOf(initial).id === provider?.id;
  const hasSavedKey = sameScope && typeof initial?.key === "object" && initial.key?.set;
  const canReuseKey = sameScope && !key;
  const listed = (subscription ? subscriptionModels.data?.values : result?.values) ?? [];
  const filtered = listed.filter((m) => m.toLowerCase().includes(search.toLowerCase()));
  const normalize = (id: string) => !provider || id.startsWith(provider.prefix) || provider.id === "custom" && id.includes("/") ? id : provider.prefix + id;
  const check = async () => {
    if (!provider) return;
    const at = revision.current;
    try {
      const response = canReuseKey ? await listModels("models.connections", initial.name)
        : await discover.mutateAsync({ server: provider.server, provider: provider.id, endpoint: endpoint.trim(), key: key.trim() || null });
      if (at === revision.current) { setResult(response); if (response.ok) setStep("model"); }
    } catch { /* Render a concise error without provider response bodies or credentials. */ }
  };
  const selected = (id: string) => { setModel(normalize(id)); setStep("review"); };
  const busy = discover.isPending || detect.isPending;
  const progress = STEPS.indexOf(step);
  const ready = provider && name.trim() && !duplicate && (subscription ? signedIn : validUrl)
    && (!cloud || !!key.trim() || hasSavedKey) && (!useDefault || !!model.trim());

  return (
    <section aria-label={initial ? "Edit model connection" : "Add model connection"} className="connection-setup">
      <div className="flex items-center justify-between gap-4">
        <h3 className="m-0 text-heading font-semibold">{initial ? "Edit connection" : "Connect a model"}</h3>
        <button type="button" onClick={onCancel} disabled={pending} className={secondaryButton}>Cancel</button>
      </div>
      <ol aria-label="Connection setup progress" className="connection-steps">
        {STEPS.map((s, i) => <li key={s} aria-current={s === step ? "step" : undefined} className={i <= progress ? "is-active" : ""}>
          <span aria-hidden>{i < progress ? "✓" : i + 1}</span>{LABELS[i]}
        </li>)}
      </ol>
      <div className="flex flex-col gap-2">
        <h4 ref={heading} tabIndex={-1} className="m-0 text-heading font-semibold outline-none">
          {step === "provider" ? "Where do you want to connect?" : step === "connect" ? `Connect to ${provider?.name}` : step === "model" ? "Pick your model" : "Ready to connect"}
        </h4>
        <p className="m-0 text-secondary text-ink-3">{step === "provider" ? "Choose a provider. Comeni handles the connection details."
          : step === "connect" ? subscription ? "Authorize access on OpenAI’s sign-in page." : cloud ? "Paste your key. We’ll check access and find your models." : "Comeni looks for a running server so you don’t have to type an address."
          : step === "model" ? "Choose one of the models returned by your connection." : "Your connection will be saved on this Comeni installation."}</p>
      </div>
      {step === "provider" && <>
        <div className="connection-categories" aria-label="Provider categories">
          {["All", "Local server", "API key", "Subscription"].map((c) => <button type="button" key={c} aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}
        </div>
        <div className="provider-grid">
          {PROVIDERS.filter((p) => category === "All" || category === p.category).map((p) => <button type="button" key={p.id} onClick={() => chooseProvider(p)} className="provider-card">
            <span className="provider-monogram" aria-hidden>{p.mark}</span><span className="text-label text-ink-3">{p.category}</span>
            <strong className="text-body text-ink">{p.name}</strong><span className="text-secondary text-ink-3">{p.detail}</span>
            <span className="provider-card-arrow" aria-hidden>↗</span>
          </button>)}
        </div>
      </>}
      {step === "connect" && provider && <>
        {subscription ? <ChatgptSignin onReady={markReady} /> : <>
          {cloud && <div className="connection-input-group">
            <div className="flex items-center justify-between gap-3"><label htmlFor="setup-key">API key</label><a href={provider.keyUrl} target="_blank" rel="noreferrer" className="text-now-ink text-secondary">Get an API key ↗</a></div>
            <div className="flex gap-2"><input id="setup-key" type={showKey ? "text" : "password"} autoComplete="off" value={key}
              placeholder={hasSavedKey ? "Saved key kept unless replaced" : "Paste your API key"} onChange={(e) => { changed(); setKey(e.target.value); }} className={setupField} />
              <button type="button" aria-pressed={showKey} onClick={() => setShowKey(!showKey)} className={secondaryButton}>{showKey ? "Hide" : "Show"}</button></div>
            <p className="m-0 text-label text-ink-3">API usage is billed by the provider, separately from chat subscriptions.</p>
          </div>}
          {detect.isPending && <div className="connection-scanning" role="status"><span className="connection-scan-dot" /> Looking for {provider.name} and installed models…</div>}
          {detect.isSuccess && !detect.data.length && <p role="status" className="connection-notice text-ink-2">No running server found at the usual addresses. Start {provider.name} and retry, or enter its address below.</p>}
          {provider.id === "custom" && <div className="connection-input-group"><label htmlFor="setup-custom-endpoint">Server address</label>
            <input id="setup-custom-endpoint" type="url" value={endpoint} onChange={(e) => { changed(); setEndpoint(e.target.value); }} placeholder="http://server:port/v1" className={setupField} /></div>}
          <details className="text-secondary text-ink-2">
            <summary className="cursor-pointer">{cloud ? "Advanced connection settings" : "Use a different address or API key"}</summary>
            <div className="connection-input-group mt-3">
              {provider.id !== "custom" && <><label htmlFor="setup-endpoint">{cloud ? "API base URL" : "Server address"}</label>
                <input id="setup-endpoint" type="url" value={endpoint} onChange={(e) => { changed(); setEndpoint(e.target.value); }} className={setupField} /></>}
              {!cloud && <><label htmlFor="setup-key">API key (optional)</label><input id="setup-key" type="password" autoComplete="off" value={key} onChange={(e) => { changed(); setKey(e.target.value); }} className={setupField} />
                <p className="m-0 text-label text-ink-3">The address must be reachable from Comeni’s server. In Docker, localhost points to the container.</p></>}
            </div>
          </details>
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" disabled={busy || (!validUrl || cloud && !key.trim() && !canReuseKey)} className={primaryButton} onClick={check}>{busy ? "Checking…" : "Connect & find models"}</button>
            {(provider.id === "ollama" || provider.id === "lmstudio") && <button type="button" disabled={busy} className={secondaryButton} onClick={() => { changed(); void detectLocal(provider); }}>Detect again</button>}
            <a href={provider.docs} target="_blank" rel="noreferrer" className="text-secondary text-now-ink">Setup help ↗</a>
          </div>
          {result?.ok === false && <p role="alert" className="connection-notice text-needs-you-ink">{result.says}</p>}
          {(discover.error || detect.error) && <p role="alert" className="m-0 text-secondary text-needs-you-ink">Could not reach this connection. Check the address and try again.</p>}
          <p className="m-0 text-label text-ink-3">Connection checks only list models. No prompt is sent.</p>
          <button type="button" className="connection-text-button" onClick={() => { setManual(true); setStep("model"); }}>My provider doesn’t list models</button>
        </>}
      </>}
      {step === "model" && provider && <>
        {subscriptionModels.isFetching && subscription && <p role="status" className="connection-scanning">Loading models from your subscription…</p>}
        {(subscriptionModels.error || subscription && subscriptionModels.data?.ok === false) && <div className="connection-notice text-needs-you-ink">
          <p className="m-0 text-secondary">Could not load subscription models.</p><button type="button" className={secondaryButton} onClick={() => void subscriptionModels.refetch()}>Retry</button>
        </div>}
        {listed.length > 0 && <>
          {subscription && <button type="button" disabled={subscriptionModels.isFetching} className="connection-text-button" onClick={() => void subscriptionModels.refetch()}>{subscriptionModels.isFetching ? "Refreshing models…" : "Refresh subscription models"}</button>}
          <div className="connection-input-group"><label htmlFor="setup-model-search">Search {listed.length} models</label>
            <input id="setup-model-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a model…" className={setupField} /></div>
          <div className="connection-model-grid" aria-label="Available models">
            {filtered.map((m) => <button type="button" key={m} onClick={() => selected(m)} className="connection-model-card"><span aria-hidden className="connection-model-dot" /><span className="min-w-0 break-all">{m.startsWith(provider.prefix) ? m.slice(provider.prefix.length) : m}</span><span aria-hidden className="ml-auto">→</span></button>)}
          </div>
          {!filtered.length && <p role="status" className="m-0 text-secondary text-ink-3">No models match this search.</p>}
        </>}
        {!listed.length && !subscriptionModels.isFetching && <p role="status" className="m-0 text-secondary text-ink-3">No models were returned. You can refresh the connection or enter a model ID.</p>}
        <details open={manual} onToggle={(e) => setManual(e.currentTarget.open)} className="text-secondary text-ink-2">
          <summary className="cursor-pointer">Enter a model ID manually</summary>
          <div className="flex gap-2 mt-3"><input aria-label="Model ID" value={model} onChange={(e) => setModel(e.target.value)} placeholder="Model ID from your provider" className={setupField} />
            <button type="button" disabled={!model.trim()} onClick={() => selected(model.trim())} className={secondaryButton}>Use model</button></div>
        </details>
        <button type="button" className="connection-text-button" onClick={() => { setUseDefault(false); setModel(""); setStep("review"); }}>Choose a model later</button>
      </>}
      {step === "review" && provider && <>
        <div className="connection-review">
          <span className="provider-monogram" aria-hidden>{provider.mark}</span><div className="min-w-0"><strong className="text-body">{name}</strong>
            <p className="m-0 text-secondary text-ink-2 break-all">{model ? model.startsWith(provider.prefix) ? model.slice(provider.prefix.length) : model : "Model will be chosen later"}</p>
            <p className="m-0 text-label text-ink-3">{subscription ? "ChatGPT sign-in" : cloud ? "API key" : endpoint}</p></div><span aria-hidden className="text-done-ink ml-auto">✓</span>
        </div>
        {defaultAllowed && model && <div className="connection-categories" aria-label="How to use this model">
          <button type="button" aria-pressed={useDefault} onClick={() => setUseDefault(true)}>Use as my default</button>
          <button type="button" aria-pressed={!useDefault} onClick={() => setUseDefault(false)}>Assign later</button>
        </div>}
        <p className="m-0 text-secondary text-ink-3">{useDefault ? "Analyses will use this model unless a purpose has its own choice." : "Save the connection and choose where to use it in the settings below."}</p>
        <details className="text-secondary text-ink-2"><summary className="cursor-pointer">Customize connection name</summary>
          <div className="connection-input-group mt-3"><label htmlFor="setup-name">Connection name</label><input id="setup-name" value={name} onChange={(e) => setName(e.target.value)} className={setupField} readOnly={!!initial} aria-invalid={duplicate} />
            {duplicate && <p role="alert" className="m-0 text-label text-needs-you-ink">That name is already in use. Choose another.</p>}</div>
        </details>
        {error && <p role="alert" className="m-0 text-secondary text-needs-you-ink">{error}</p>}
      </>}
      {step !== "provider" && <div className="connection-setup-footer">
        <button type="button" onClick={() => {
          if (step === "connect") { changed(); setProvider(null); setStep("provider"); }
          else setStep(step === "review" ? "model" : "connect");
        }} disabled={pending} className={secondaryButton}>← Back</button>
        {step === "review" && provider && <button type="button" disabled={!ready || pending} className={primaryButton} onClick={() => {
          if (ready) onSave({ connection: { name: name.trim(), provider: provider.id, server: provider.server, endpoint: subscription ? "" : endpoint.trim(), key: key.trim() || null }, model, useDefault });
        }}>{pending ? "Saving…" : "Finish setup"}</button>}
      </div>}
    </section>
  );
}
