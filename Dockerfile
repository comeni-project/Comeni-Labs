# Shared Python image for Mendel and Wiener APIs and workers.
# The builder installs the workspace; the runtime adds Git, Nextflow, and the Docker CLI.
# Compose selects each service's command; the default starts Mendel's API.

# -----------------------------------------------------------------------------
# 1. Build the Python environment
# -----------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Copy manifests first so source edits can reuse the dependency layer.
# Include README and LICENSE files required by package metadata.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages/comeni-core/pyproject.toml packages/comeni-core/README.md packages/comeni-core/LICENSE ./packages/comeni-core/
COPY packages/mendel-resolver/pyproject.toml packages/mendel-resolver/README.md packages/mendel-resolver/LICENSE ./packages/mendel-resolver/
COPY packages/mendel-compiler/pyproject.toml packages/mendel-compiler/README.md packages/mendel-compiler/LICENSE ./packages/mendel-compiler/
COPY packages/mendel-forge/pyproject.toml packages/mendel-forge/README.md packages/mendel-forge/LICENSE ./packages/mendel-forge/
COPY packages/comeni-ai/pyproject.toml packages/comeni-ai/README.md packages/comeni-ai/LICENSE ./packages/comeni-ai/
# Include the deprecated mendel-ai wrapper while it remains a workspace member.
COPY packages/mendel-ai/pyproject.toml packages/mendel-ai/README.md packages/mendel-ai/LICENSE ./packages/mendel-ai/
COPY packages/mendel-authoring/pyproject.toml packages/mendel-authoring/README.md packages/mendel-authoring/LICENSE ./packages/mendel-authoring/
COPY packages/mendel-api/pyproject.toml ./packages/mendel-api/
COPY packages/dag-core/pyproject.toml ./packages/dag-core/
COPY packages/wiener-core/pyproject.toml ./packages/wiener-core/
COPY packages/wiener-api/pyproject.toml ./packages/wiener-api/
COPY packages/comeni-vendor/pyproject.toml packages/comeni-vendor/README.md packages/comeni-vendor/LICENSE ./packages/comeni-vendor/
COPY packages/comeni-inspect/pyproject.toml packages/comeni-inspect/README.md packages/comeni-inspect/LICENSE ./packages/comeni-inspect/

# Install dependencies for both subsystems from the lockfile, without development tools.
RUN uv sync --frozen --no-install-project --no-dev --all-packages

# Add package sources and finish installing the workspace.
COPY packages/ ./packages/
RUN uv sync --frozen --no-dev --all-packages

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

# -----------------------------------------------------------------------------
# 3. Prepare Nextflow and the default API command
# -----------------------------------------------------------------------------
ENV NXF_HOME=/app/.nextflow
# Download the Nextflow runtime during the build, before a worker needs it.
# Its launcher writes temporary files in the working directory; run it while /app is writable.
# Cache ownership matches Compose's default UID/GID; adjust it when using another user.
RUN nextflow -version \
 && chown -R 1000:1000 /app/.nextflow

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "mendel_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
