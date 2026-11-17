/** Setup presets only. Model names always come from discovery or an explicit choice. */
export const PROVIDERS = [
  { id: "ollama", name: "Ollama", category: "Local server", mark: "Ol", server: "ollama", endpoint: "http://ollama:11434", prefix: "ollama_chat/", detail: "Models on your machine or network", docs: "https://docs.ollama.com/", keyUrl: "" },
  { id: "lmstudio", name: "LM Studio", category: "Local server", mark: "LM", server: "openai_compatible", endpoint: "http://host.docker.internal:1234/v1", prefix: "openai/", detail: "Connect a running local server", docs: "https://lmstudio.ai/docs/developer/core/server", keyUrl: "" },
  { id: "openai", name: "OpenAI API", category: "API key", mark: "O", server: "hosted", endpoint: "https://api.openai.com/v1", prefix: "openai/", detail: "Connect with an OpenAI API key", docs: "https://developers.openai.com/api/docs/quickstart", keyUrl: "https://platform.openai.com/api-keys" },
  { id: "anthropic", name: "Anthropic API", category: "API key", mark: "A", server: "hosted", endpoint: "https://api.anthropic.com", prefix: "anthropic/", detail: "Claude models through the API", docs: "https://platform.claude.com/docs/en/get-api-key", keyUrl: "https://platform.claude.com/settings/keys" },
  { id: "gemini", name: "Google Gemini", category: "API key", mark: "G", server: "hosted", endpoint: "https://generativelanguage.googleapis.com/v1beta/openai", prefix: "openai/", detail: "Connect with a Google AI Studio key", docs: "https://ai.google.dev/gemini-api/docs/openai", keyUrl: "https://aistudio.google.com/apikey" },
  { id: "openrouter", name: "OpenRouter", category: "API key", mark: "OR", server: "hosted", endpoint: "https://openrouter.ai/api/v1", prefix: "openai/", detail: "Multiple providers through one API", docs: "https://openrouter.ai/docs/quickstart", keyUrl: "https://openrouter.ai/settings/keys" },
  { id: "chatgpt", name: "ChatGPT subscription", category: "Subscription", mark: "C", server: "hosted", endpoint: "", prefix: "chatgpt/", detail: "Use the installation’s ChatGPT sign-in", docs: "https://docs.litellm.ai/docs/providers/chatgpt", keyUrl: "" },
  { id: "custom", name: "Custom server", category: "Local server", mark: "<>", server: "openai_compatible", endpoint: "", prefix: "openai/", detail: "vLLM or another OpenAI-compatible API", docs: "https://docs.litellm.ai/docs/providers/openai_compatible", keyUrl: "" },
] as const;

export type Provider = typeof PROVIDERS[number];
export type Connection = { name: string; provider?: string; server?: string; endpoint?: string;
  key?: { set: boolean; last4: string | null } | string | null; locked?: boolean };

export function providerOf(connection: Connection): Provider {
  return PROVIDERS.find((p) => p.id === connection.provider)
    ?? PROVIDERS.find((p) => p.endpoint && p.endpoint === connection.endpoint)
    ?? PROVIDERS.find((p) => p.id === (connection.server === "ollama" ? "ollama" : "custom"))!;
}

export const setupField = "connection-field";
export const secondaryButton = "connection-button";
export const primaryButton = "connection-button connection-primary";
