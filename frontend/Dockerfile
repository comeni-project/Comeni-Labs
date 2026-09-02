# The SPA, built and then served by nginx.
#
# **nginx rather than FastAPI, and it is forced rather than chosen.** Serving static files from
# the API needs `app.mount`, and phase 6's `test_the_served_surface_is_the_openapi_document`
# refuses that — measured: the mount appears in `app.routes` and the guard fails. The rule it
# holds is that the served surface is exactly the OpenAPI document, and a directory of files is
# precisely a surface that is not in it.
#
# **The build context is the repository root**, not `frontend/`, because `ops/nginx/default.conf`
# lives with the rest of the deployment config — it describes how the API and the SPA share one
# origin, which is not a frontend detail. Docker cannot COPY above its context, so the context
# moves rather than the file. It sat in a top-level `nginx/` until 2026-09-02; `ops/` is where
# the collector config and the Grafana provisioning already were, and this is the same kind of
# thing — a file a container mounts, not a file a developer runs.
FROM node:22-alpine AS builder
WORKDIR /app
# The lockfile first, so editing a component does not reinstall the world.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ops/nginx/default.conf /etc/nginx/conf.d/default.conf
