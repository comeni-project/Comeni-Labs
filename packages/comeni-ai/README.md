# comeni-ai

`comeni-ai` is the shared model-provider boundary for Comeni Labs. It sends prompts through
one configurable transport and validates every reply against a caller-supplied Pydantic model
before returning it. The package does not expose an unchecked free-text generation API.

Use `Client.generate()` for a single request, `Client.chat()` for a split system/user prompt,
and `converse()` for a caller-bounded conversation history. `choose_one()` and `choose_many()`
add closed-choice membership checks. `PromptTemplate` loads, renders, and identifies committed
prompt files owned by the calling package. `RecordedTransport` replays fixtures without network
access.

Provider access is configured with `ModelAccess` or these environment variables:

- `COMENI_AI_MODEL` selects the model.
- `COMENI_AI_API_KEY` supplies an optional provider credential.
- `COMENI_AI_BASE_URL` selects a local or self-hosted compatible endpoint.
- `COMENI_AI_TIMEOUT_SECONDS` and `COMENI_AI_TEMPERATURE` override call defaults.

The package owns provider configuration, transport, reply formats, response validation, generic
choice/chat helpers, and prompt-file mechanics. Domain prompts, domain reply models, persistence,
queues, and retry policy remain with callers. See the
[package responsibility map](../../docs/explanation/package-boundaries.md) and
[AI ownership guide](../../docs/explanation/mendel-ai-ownership.md) for those boundaries.

Network access is intentionally isolated here. Tests inject fakes or use committed recordings;
`tests/guards/test_no_live_model.py` prevents test code from naming a live transport.
