# Shared Python image for Mendel and Wiener APIs and workers.
# The builder installs the workspace; the runtime adds Git, Nextflow, and the Docker CLI.
# Compose selects each service's command; the default starts Mendel's API.

# -----------------------------------------------------------------------------
# 1. Build the Python environment
# -----------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Resolve third-party dependencies from the lock before workspace source is copied.
# Frozen mode is required here because package manifests are not present yet.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --no-dev --all-packages

# Include package metadata, licences and source together, then validate the lockfile.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages/ ./packages/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --all-packages

# -----------------------------------------------------------------------------
# 2. Assemble the runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Git supports registry commits; Java and Nextflow run gates and pipelines.
# The Docker CLI uses the host daemon socket mounted by Compose for wiener-worker.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl default-jre-headless \
      docker.io \
 && curl -fsSL https://get.nextflow.io -o /usr/local/bin/nextflow \
 && chmod +x /usr/local/bin/nextflow \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY packages/ ./packages/

# Bundle registry declarations and modules; Compose mounts a writable clone here.
COPY registry/ ./registry/
COPY examples/ ./examples/

# -----------------------------------------------------------------------------
# 3. Prepare Nextflow and the default API command
# -----------------------------------------------------------------------------
ENV NXF_HOME=/app/.nextflow
# Download the Nextflow runtime during the build, before a worker needs it.
# Its launcher writes temporary files in the working directory; run it while /app is writable.
# Cache ownership follows the runtime identity supplied by Compose at build time.
ARG RUNTIME_UID=1000
ARG RUNTIME_GID=1000
RUN nextflow -version \
 && chown -R ${RUNTIME_UID}:${RUNTIME_GID} /app/.nextflow

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "mendel_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
