# mendel-ai compatibility package

`mendel-ai` is deprecated. Use [`comeni-ai`](../comeni-ai/) for model access, validated replies,
prompt templates, conversations, and choice helpers.

## Migrate

1. Replace the `mendel-ai` dependency with `comeni-ai`.
2. Replace `mendel_ai` imports with `comeni_ai`.
3. Prefer the current environment variables:
   `COMENI_AI_MODEL`, `COMENI_AI_API_KEY`, `COMENI_AI_BASE_URL`,
   `COMENI_AI_TIMEOUT_SECONDS`, and `COMENI_AI_TEMPERATURE`.

The corresponding `MENDEL_*` variables remain fallback inputs during the compatibility window.

## Compatibility contract

The package contains no model implementation. Importing `mendel_ai` emits a
`DeprecationWarning` and re-exports the original public objects from `comeni_ai` by identity.
Newer `comeni_ai` names are intentionally absent, so new code does not acquire a dependency on
the deprecated package.

Repository tests also reject new in-repository `mendel_ai` imports. Existing external consumers
can continue to import the historical surface while they migrate.
