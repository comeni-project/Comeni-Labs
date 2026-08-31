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
# The four that arrived with Wiener on 2026-08-24. `dag-core` is not optional for
# `mendel-api`: `mendel-compiler` depends on it, so a missing line here fails the
# build with `Distribution not found`, which is how this was found.
COPY packages/dag-core/pyproject.toml ./packages/dag-core/
COPY packages/wiener-core/pyproject.toml ./packages/wiener-core/
COPY packages/wiener-api/pyproject.toml ./packages/wiener-api/
# Plan 5A, 2026-08-31. **The third time a missing line here failed the build**, after
# `dag-core` and before it `mendel-ai` — a hand-maintained list of every workspace member,
# with nothing checking it against the directory. `tests/test_dockerfile.py` checks it now.
COPY packages/comeni-vendor/pyproject.toml packages/comeni-vendor/README.md packages/comeni-vendor/LICENSE ./packages/comeni-vendor/

# **`--package mendel-api`, not the root project.** The root depends on `mendel-ai`, and the
# served API cannot reach the model path — invariant 3's three runtime AI points are all
# unbuilt. Syncing the subset skips litellm and its stack, measured at 152MB.
# **`--all-packages`, not `--package mendel-api`.** One image serves both halves —
# mendel-api, its worker, wiener-api, wiener-ingest and wiener-worker — because the
# operator's constraint is that the whole stack comes up with one compose command,
# and a second Dockerfile is a second place to keep a dependency pin honest.
#
# It was `--package mendel-api` and every Wiener container died on
# `ModuleNotFoundError: No module named 'wiener_api'` — the compose file said
# `build: .` and got an image that did not contain what it was asked to run.
RUN uv sync --frozen --no-install-project --no-dev --all-packages

COPY packages/ ./packages/
RUN uv sync --frozen --no-dev --all-packages


FROM python:3.12-slim-bookworm AS runtime

# `git` because accepting a drift is a commit — `mendel_forge.land` shells out to it. Without
# it the refusal ladder cannot reach its own refusals, and MF0107 would be a traceback.
#
# `default-jre-headless` and `nextflow` because a GATE is a `nextflow run`, and the worker is
# where one belongs: `run_gate` blocks for up to 3600s and this image's worker docstring
# already named that as the thing ARQ exists for.
#
# **LINT and PREVIEW only, in this image.** STUB and TEST pass `-profile ...,docker` and need a
# Docker daemon; giving this container one means mounting the host's socket, which is
# root-equivalent access to the host. That is a real decision and it is deliberately NOT taken
# here — `docs/design/execution-boundary.md` §8 leaves it to Wiener, the component that has to
# solve isolation anyway. `run_gate` already degrades honestly when a tool is absent, which is
# why nothing noticed this image had no Nextflow at all.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl default-jre-headless \
      docker.io \
 && curl -fsSL https://get.nextflow.io -o /usr/local/bin/nextflow \
 && chmod +x /usr/local/bin/nextflow \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY packages/ ./packages/

# **The declared data is part of what this serves.** `settings.registry_root` is read by the
# queue, the contracts list, the drift report and the source catalogue — about a megabyte, so
# baking it removes a whole class of "works on my host" failure for the price of nothing. Both
# compose files mount a writable registry CLONE over this one, because a copy of files cannot
# take a commit.
#
# **One COPY since Plan 5A, where there were two.** `vendor/` held the module code the
# registry's contracts describe, in this repository, on a different release cadence. An image
# that has the layer now has everything, and there is no way to bake one without the other.
COPY registry/ ./registry/

# **Created and chowned, because the worker does not run as root.** `docker-compose.yml` sets
# `user: "${DOCKER_UID:-1000}:${DOCKER_GID:-1000}"` and nothing here chowns `/app`, so a
# root-owned NXF_HOME is permission-denied on the very first gate — Nextflow writes there
# before it does anything else, because it downloads its plugins on first run. The failure
# would read as a Nextflow bug rather than as a Dockerfile one.
#
# That first run also needs the network. Legitimate — `mendel-api` is an impure package and
# invariant 1 constrains the other three — but an air-gapped installation must pre-seed this
# directory, and nothing else in the stack has that property.
#
# `1000:1000` is hardcoded while DOCKER_UID is not. If a machine overrides it, the first gate
# fails with a permission error on this path.
ENV NXF_HOME=/app/.nextflow
# **`nextflow -version` at build time, and it is not a smoke test.** `get.nextflow.io` installs
# a *launcher script*, not Nextflow: the real jar is downloaded on first run into NXF_HOME. Left
# to run time that download happens inside the first gate — as a non-root user, against a
# root-owned NXF_HOME, needing the network, with the failure arriving as a confusing gate
# result. Running it here bakes the jar into the image, so the container is self-contained and
# an air-gapped installation works.
#
# The launcher also writes a temp file into its WORKING DIRECTORY while downloading, so this
# must run before the chown and while `/app` is still root-writable. At run time the working
# directory is the draft's own directory on a writable volume, so that need does not recur.
RUN nextflow -version \
 && chown -R 1000:1000 /app/.nextflow

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "mendel_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
