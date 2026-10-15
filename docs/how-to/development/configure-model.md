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

Leaving `COMENI_AI_MODEL` empty is a supported way to run the forge. Sources sync, scaffolds
derive, and every open question is answered by hand.

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
