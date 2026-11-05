# Configure a model

<!--
Serves: all four steps.
-->

Start the [development stack](local-stack.md) before configuring its AI worker.
`make dev` does not download model weights. Choose a local server or a hosted provider.

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

Leaving `COMENI_AI_MODEL` empty is a supported way to run Comeni. Every deterministic step
still works, and every open question is answered by a person.

## Use a ChatGPT subscription

A ChatGPT plan that includes Codex can answer model calls through LiteLLM's `chatgpt/`
provider, with no API key. Calls count against the plan's usage limits.

1. In ChatGPT's security settings, turn on device code login.
2. Sign in once. The command prints a link and a code; approve it in the browser:

   ```bash
   docker exec mendel-ai-worker python -u -c "import litellm; print(litellm.completion(model='chatgpt/gpt-6.1-sol', messages=[{'role': 'user', 'content': 'say ok'}]).choices[0].message.content)"
   ```

   The sign-in is kept in `.run/chatgpt/auth.json`, which the API and the AI worker share as
   `CHATGPT_TOKEN_DIR`. It lasts about ten days. When calls start failing, sign in again.
3. In **Settings → Models**, add a connection with the server **A hosted provider**, and no
   endpoint or key.
4. For a purpose, choose **Other…**, that connection and a model such as
   `chatgpt/gpt-6.1-sol`. A plan accepts only some models; the call says which it refuses.
5. Open the purpose's **Call settings** and set **Temperature** to 1. A reasoning model
   refuses any other temperature unless its reasoning effort is `none`.

## Tune a purpose's calls

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
