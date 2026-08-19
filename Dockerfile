# One image, two commands: the API serves and the worker consumes. They import the same
# packages and read the same declared data; only the command differs, so two images would be
# two places to keep one dependency pin honest.
#
# **No BuildKit cache mounts.** `docker buildx` is not installed on the machine this was built
# on, and `DOCKER_BUILDKIT=1` answers "BuildKit is enabled but the buildx component is missing"
# — so a `--mount=type=cache` Dockerfile would not build here at all. Layer ordering does the
# work instead: measured 53s cold and 8.3s after a source edit.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# The workspace's SHAPE first, so editing a module does not re-resolve the lock.
#
# **`README.md` and `LICENSE` are build inputs, not documentation.** The root pyproject
# declares `readme =` and `license-files =`, and `uv sync` fails without them. Each package
# carries its own pair, which these copies bring.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages/comeni-core/pyproject.toml packages/comeni-core/README.md packages/comeni-core/LICENSE ./packages/comeni-core/
COPY packages/mendel-resolver/pyproject.toml packages/mendel-resolver/README.md packages/mendel-resolver/LICENSE ./packages/mendel-resolver/
COPY packages/mendel-compiler/pyproject.toml packages/mendel-compiler/README.md packages/mendel-compiler/LICENSE ./packages/mendel-compiler/
COPY packages/mendel-forge/pyproject.toml packages/mendel-forge/README.md packages/mendel-forge/LICENSE ./packages/mendel-forge/
COPY packages/mendel-ai/pyproject.toml packages/mendel-ai/README.md packages/mendel-ai/LICENSE ./packages/mendel-ai/
COPY packages/mendel-api/pyproject.toml ./packages/mendel-api/

# **`--package mendel-api`, not the root project.** The root depends on `mendel-ai`, and the
# served API cannot reach the model path — invariant 3's three runtime AI points are all
# unbuilt. Syncing the subset skips litellm and its stack, measured at 152MB.
RUN uv sync --frozen --no-install-project --no-dev --package mendel-api

COPY packages/ ./packages/
RUN uv sync --frozen --no-dev --package mendel-api


FROM python:3.12-slim-bookworm AS runtime

# `git` because accepting a drift is a commit — `mendel_forge.land` shells out to it. Without
# it the refusal ladder cannot reach its own refusals, and MF0107 would be a traceback.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY packages/ ./packages/

# **The declared data is part of what this serves.** `settings.registry_root` and `source_root`
# are read by the queue, the contracts list, the drift report and the source catalogue —
# measured at 224K and 788K, so baking them costs a megabyte and removes a whole class of
# "works on my host" failure. Both compose files mount a writable registry CLONE over this
# one, because a copy of files cannot take a commit.
COPY registry/ ./registry/
COPY vendor/ ./vendor/

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "mendel_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
