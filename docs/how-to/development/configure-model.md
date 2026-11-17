# Configure a model

<!--
Serves: all four steps.
-->

Start the [development stack](local-stack.md) before configuring its AI worker.
`make dev` does not download model weights. Choose a local server or a hosted provider.

## Connect from Settings

Open **Settings → Models → Add connection**. Setup walks through four choices:

1. Choose a provider card: Ollama, LM Studio, OpenAI API, Anthropic API, Google Gemini,
   OpenRouter, ChatGPT subscription, or a custom OpenAI-compatible server.
2. For Ollama and LM Studio, Comeni checks the usual local addresses automatically. For an API
   provider, paste its API key and click **Connect & find models**. The provider's address is
   filled in; custom addresses and optional local authentication live under advanced settings.
3. Click a returned model card. Search filters the list. If a provider does not publish a model
   list, the manual model ID option remains available.
4. Choose **Use as my default** or **Assign later**, then **Finish setup**. Connection names are
   suggested automatically. Existing `.env` pins remain in control.

Connection checks list models without sending a prompt. Draft keys are not saved until setup
finishes; stored keys remain sealed and are returned only as a last-four-character mask. Editing
an existing connection can reuse its saved key. Model choices below the connection list have
searchable pickers and per-purpose call settings.

Local detection checks the Compose Ollama service, the Docker host address, and loopback;
it does not install a server or download model weights. A server on another machine needs its
address entered under **Use a different address or API key**.

## Configure the local stack from the terminal

```bash
make ai-up                            # start Ollama; may download its container image
make ai-pull MODEL=qwen2.5-coder:14b     # download model weights into a named volume
```

`make ai-up` prints the two lines to add to `.env`:

```
COMENI_AI_MODEL=ollama_chat/qwen2.5-coder:14b
COMENI_AI_BASE_URL=http://ollama:11434
```

Then restart the AI worker so it reads them:

```bash
docker compose up -d --force-recreate ai-worker
```

Use `http://ollama:11434`, not `http://localhost:11434`. The worker reaches the model server
over the compose network; `localhost` there is the worker's own container.

To use a hosted model instead, set `COMENI_AI_MODEL` and `COMENI_AI_API_KEY` and leave
`COMENI_AI_BASE_URL` empty. Nothing else changes — the same worker, the same prompts, the same
registry.

Leaving both Settings and `COMENI_AI_MODEL` without a model is supported. Every deterministic step
still works, and every open question is answered by a person.

## Use a ChatGPT subscription

A ChatGPT plan that includes Codex can answer model calls through LiteLLM's `chatgpt/`
provider, with no API key. Calls count against the plan's usage limits.

1. In ChatGPT's security settings, enable device code login if your account requires it.
2. Open **Settings → Models → Add connection → ChatGPT subscription**.
3. Click **Continue with ChatGPT**, copy the displayed code, and open the sign-in page.
   Approve access there. Comeni waits for approval and then shows the subscription's model
   catalogue. An existing saved sign-in is reused.
4. Click a model, choose whether to use it as the default, and click **Finish setup**.

The sign-in is kept in `.run/chatgpt/auth.json`, shared by the API and AI worker as
`CHATGPT_TOKEN_DIR`. Access and refresh tokens never enter the browser. Pending device codes
expire after fifteen minutes; the UI offers a fresh sign-in when they expire. The provider
controls model availability and plan limits. If catalogue access is unavailable, retry or use
the manual model ID option. New subscription defaults use temperature 1, matching the existing
subscription transport; per-purpose **Call settings** can override it.

API keys and subscription access are separate choices. The ChatGPT option uses Comeni's
existing LiteLLM subscription transport, rather than treating a chat subscription as an API key.
Claude subscriptions are not connected by this flow; Anthropic setup uses an API key.

The subscription route does not cache prompts: the builder agent resends its prompt and tool
definitions on every round of a turn, and each is billed in full against the plan. A provider that
caches (the OpenAI API caches on its own; Claude models are sent the system prompt marked for
caching) bills that repeated part at a fraction. Cached input shows in a session's call list.

## Tune a purpose's calls

Subscription model discovery follows the account's current catalogue. The server refreshes
the Codex client version from public npm release metadata every six hours, without installing
software or sending credentials to npm. If that lookup fails, it keeps the last known version
and retries after ten minutes. The setup picker refreshes on opening, on returning to the
window, and every five minutes while the model selection step is open. Existing model choices
stay unchanged until you select another model.

Each purpose's **Call settings** can set its own temperature, reasoning effort and timeout.
An empty field keeps the installation's value: `COMENI_AI_TEMPERATURE` (0 when unset) and
`COMENI_AI_TIMEOUT_SECONDS` (60 when unset). Reasoning effort is sent only when chosen, because
models without reasoning refuse it. Choosing another model clears its call settings.

## Tune the local server

The Docker stack keeps the model loaded for an hour after its last request and serves one
request at a time (`OLLAMA_KEEP_ALIVE=1h`, `OLLAMA_NUM_PARALLEL=1`, both overridable in `.env`).
Keeping the model loaded avoids reloads between requests. These are Compose defaults;
a separately managed model server needs its own configuration.

## When nothing is generating

```bash
curl -s localhost:8000/api/health/ai
```

| Field | What to do about it |
|---|---|
| `configured: false` | no model is set. Add the two lines above, or leave it — this is a supported mode |
| `model_available: false` | the endpoint is not answering. `make ai-up`, and check `make ai-logs` |
| `model_available: null` | a hosted model, which is not probed |
| `worker_available: false` | no AI worker is running. `docker compose up -d ai-worker` |
| `queue_depth` | how many jobs are waiting. A number that only grows with a worker running means jobs are failing — `make ai-logs` |

`make ai-down` stops the model server. Downloaded models stay.
