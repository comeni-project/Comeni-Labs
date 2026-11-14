# Tool calling on the subscription route

Checked on 2026-11-14 for the builder agent (`docs/superpowers/plans/2026-11-14-builder-agent.md`,
Task 1), live from the `ai-worker` container on the dev stack.

**Result: `NATIVE`.** LiteLLM 1.105's `tools=` works through the ChatGPT subscription route
(`chatgpt/gpt-6.1-sol`, the builder's configured model for every purpose).

- One `add` tool and "What is 2+2? Use the add tool." came back with `finish_reason:
  tool_calls`, `content: None` and one call: name `add`, arguments `{"a":2,"b":2}` (a JSON
  string), an id of the form `call_<hex>`.
- Sending that call back as an `assistant` message with `tool_calls`, then a `tool` message
  with `tool_call_id` and content `4`, came back with `finish_reason: stop` and the text
  "2 + 2 = 4.". Usage was reported (1711 prompt tokens, 12 completion tokens).

So the agent loop uses the provider's own tool calls; the JSON action fallback is not built.
The model is reached by purpose: `model_access("builder", "chat")`. With no purpose,
`model_access("builder")` falls back to the default model, a local Ollama here.
