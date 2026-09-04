# mendel-ai — deprecated

This package moved to [`comeni-ai`](../comeni-ai/) on 2026-09-04. Import `comeni_ai`.

`mendel_ai` re-exports the names it used to implement and holds no code of its own. It exists
for released consumers that pinned `mendel-ai` at `0.1.0`; every caller inside this repository
has moved, and a test refuses a new one.

The environment variables moved with it — `COMENI_AI_MODEL`, `COMENI_AI_API_KEY`,
`COMENI_AI_BASE_URL`, `COMENI_AI_TIMEOUT_SECONDS`, `COMENI_AI_TEMPERATURE`. The `MENDEL_*`
spellings are read as a fallback for the compatibility window.

**Why the rename.** A second consumer appeared. The Forge, the builder and Wiener's agents
would otherwise have grown three model clients, and an engine-specific prefix on shared
configuration — `MENDEL_MODEL` setting up a Wiener agent — is a lie in a `.env` file.
